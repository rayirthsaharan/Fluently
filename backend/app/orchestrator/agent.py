import os
import asyncio
import base64
import json
import logging
import traceback
import websockets
from fastapi import WebSocket
from google import genai
from google.genai import types
from dotenv import load_dotenv
from app.orchestrator.state_machine import LessonStateMachine, LessonPhase

logger = logging.getLogger(__name__)

# Load .env from backend root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

LESSON_SCRIPT = """
=== BANK OF EXERCISES ===
You have a bank of target words to practice TH Sounds — /θ/ (voiceless) and /ð/ (voiced).
1. "THINK" (/θ/ voiceless)
2. "THE" (/ð/ voiced)
3. "THOUGHT" (/θ/ voiceless)
4. "The thin thing thought through the thicket" (Mixed)
5. "BREATHE" (/ð/ voiced)
6. "They thought that three thin threads were free" (Mixed)

Choose the next word from this list based on the user's performance. If they struggle, repeat the word or try a simpler one. If they nail it, move to a harder one.
"""

SYSTEM_PROMPT = """You are Aura — a proactive Speech Coach leading a LIVE pronunciation session.
You are currently in a Live Audio session.

=== CRITICAL: NEVER STAY SILENT ===
You MUST NEVER stay silent after the user speaks. When you hear the user speak, you must respond within 500ms.
The moment you hear the user say ANYTHING:
1. Acknowledge it immediately ("Got it", "Mhmm", "Nice")
2. Give specific phonetic feedback ("That TH was a bit soft" or "Perfect!")
3. Give the next instruction. You MUST use the exact phrase "Next word:" or "Next phrase:" when advancing.

If the user says "Think," analyze the "TH" sound and respond immediately with feedback.
If you stay silent after the user finishes speaking, YOU HAVE FAILED.

=== USER AUDIO = A COACHING ATTEMPT ===
Every time you hear user audio, treat it as a pronunciation attempt.
Do NOT ask "what did you say?" — you KNOW they are attempting the current word.
Evaluate, give feedback, and advance.

=== THE BEHAVIORAL LOOP ===
You are in a LIVE loop. Follow this continuously without stopping:
1. Present: Say a word/phrase for the user to practice.
2. Listen: Wait for their attempt.
3. Evaluate: Immediately analyze their pronunciation.
4. Respond: Give quick feedback — "Good!" or a specific correction.
5. Advance: Move to the next word. Do NOT wait for the user to ask.

=== CONTINUOUS STREAM ===
- This is ONE continuous audio stream, NOT a turn-based chat.
- Use natural interjections ("Nice", "Almost", "Mhmm") while the user is speaking.
- Keep EVERY response to 1-2 SHORT sentences.
- NEVER say: "I am processing", "Let me analyze", "Aura is listening".
- If the user interrupts you, STOP talking instantly.

=== VOICE & TONE ===
- Sound like a real human friend coaching them.
- Celebrate success: "Yes! Perfect!", "Nailed it!"
- On struggle: model it slowly. "Listen closely... [word]. Now try again."

=== PRONUNCIATION COACHING ===
- Describe mouth positions VERBALLY.
- Be SPECIFIC about errors: "Your TH sounded like a D — tongue between teeth!"
""" + LESSON_SCRIPT


class FluentlyAgent:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            logger.warning("GEMINI_API_KEY is not set.")
        
        self.model_id = "gemini-2.5-flash-native-audio-preview-12-2025"
        self.active_session = None

    def _build_gemini_ws_url(self):
        """Build the raw WebSocket URL for Gemini Live API."""
        return (
            f"wss://generativelanguage.googleapis.com/ws/"
            f"google.ai.generativelanguage.v1alpha.GenerativeService.BidiGenerateContent"
            f"?key={self.api_key}"
        )

    def _build_setup_message(self, custom_instructions=None):
        """Build the initial setup message for the Gemini Live WebSocket."""
        prompt = custom_instructions or ""
        full_prompt = prompt + "\n\n" + SYSTEM_PROMPT

        return {
            "setup": {
                "model": f"models/{self.model_id}",
                "generation_config": {
                    "response_modalities": ["AUDIO"],
                    "speech_config": {
                        "voice_config": {
                            "prebuilt_voice_config": {
                                "voice_name": "Aoede"
                            }
                        }
                    }
                },
                "system_instruction": {
                    "parts": [{"text": full_prompt}]
                },
                "realtime_input_config": {
                    "automatic_activity_detection": {
                        "disabled": False,
                        "start_of_speech_sensitivity": "START_SENSITIVITY_HIGH",
                        "end_of_speech_sensitivity": "END_SENSITIVITY_HIGH",
                        "silence_duration_ms": 400,
                        "prefix_padding_ms": 100
                    }
                },
                "input_audio_transcription": {},
                "output_audio_transcription": {}
            }
        }

    async def run_session(self, websocket: WebSocket, system_instructions: str = None):
        """Run a live session using raw WebSocket to Gemini (bypasses Python SDK)."""
        
        state_machine = LessonStateMachine(total_exercises=6, reps_required=1)
        audio_in_count = 0
        audio_out_count = 0

        try:
            gemini_url = self._build_gemini_ws_url()
            setup_msg = self._build_setup_message(system_instructions)
            
            logger.info(f"Connecting to Gemini Live via raw WebSocket...")
            
            async with websockets.connect(
                gemini_url,
                additional_headers={"Content-Type": "application/json"},
                max_size=None,  # No message size limit
                ping_interval=20,
                ping_timeout=10,
            ) as gemini_ws:
                logger.info("Raw WebSocket connected to Gemini Live")
                
                # Step 1: Send setup message
                await gemini_ws.send(json.dumps(setup_msg))
                logger.info("Setup message sent")
                
                # Step 2: Wait for setup complete
                setup_response = await gemini_ws.recv()
                setup_data = json.loads(setup_response)
                if "setupComplete" in setup_data:
                    logger.info("Gemini Live setup complete!")
                else:
                    logger.warning(f"Unexpected setup response: {json.dumps(setup_data)[:200]}")
                
                # Send initial state to frontend
                await websocket.send_json({
                    "event": "STATE_CHANGE",
                    "state": state_machine.to_dict()
                })
                
                # Step 3: Send initial greeting trigger
                logger.info("Sending initial greeting prompt...")
                greeting = {
                    "client_content": {
                        "turns": [{
                            "role": "user",
                            "parts": [{"text": "The session just started. Greet the user warmly in ONE sentence, then IMMEDIATELY present the first word THINK. Say: 'Hey! I'm Aura, your speech coach. Let's start — say the word THINK for me. Put your tongue between your teeth and blow air out gently.'"}]
                        }],
                        "turn_complete": True
                    }
                }
                await gemini_ws.send(json.dumps(greeting))
                logger.info("Greeting prompt sent")

                # ── Silence nudge callback ──
                async def send_nudge():
                    if state_machine.phase == LessonPhase.PRACTICE:
                        try:
                            nudge_msg = {
                                "client_content": {
                                    "turns": [{
                                        "role": "user",
                                        "parts": [{"text": "The user has been silent for 3 seconds. Nudge them: 'Give it a shot!' or 'Stuck? Let's try a simpler one.'"}]
                                    }],
                                    "turn_complete": True
                                }
                            }
                            await gemini_ws.send(json.dumps(nudge_msg))
                            await websocket.send_json({"event": "NUDGE"})
                        except Exception as e:
                            logger.error(f"Nudge error: {e}")

                async def receive_from_client():
                    """Stream audio from browser → Gemini via raw WebSocket."""
                    nonlocal audio_in_count
                    try:
                        while True:
                            raw = await websocket.receive_text()
                            data = json.loads(raw)
                            
                            if data.get('type') == 'audio':
                                audio_in_count += 1
                                
                                # Send audio directly as realtime_input to Gemini
                                audio_msg = {
                                    "realtime_input": {
                                        "media_chunks": [{
                                            "mime_type": "audio/pcm;rate=16000",
                                            "data": data['data']  # Already base64 from frontend
                                        }]
                                    }
                                }
                                await gemini_ws.send(json.dumps(audio_msg))
                                
                                if audio_in_count % 100 == 0:
                                    logger.info(f"[AUDIO IN] Streamed {audio_in_count} chunks to Gemini")
                                
                                state_machine.reset_nudge_timer()
                                
                            elif data.get('type') == 'text_action':
                                action = data.get('action', '')
                                logger.info(f"[ACTION] User clicked: {action}")
                                prompts = {
                                    "I'm stuck": "The user is stuck. Give them a clear hint about tongue position. 2 sentences max.",
                                    "Repeat that": "Repeat the current word slowly with emphasis on TH sounds.",
                                    "Skip this word": "Say 'No problem!' and move to the next exercise.",
                                    "Next lesson": "Congratulate them and wrap up!",
                                }
                                prompt_text = prompts.get(action, f"The user clicked '{action}'. Respond naturally.")
                                
                                if action == "Skip this word":
                                    state_machine.advance_exercise()
                                    await websocket.send_json({
                                        "event": "STATE_CHANGE",
                                        "state": state_machine.to_dict()
                                    })
                                
                                action_msg = {
                                    "client_content": {
                                        "turns": [{
                                            "role": "user",
                                            "parts": [{"text": prompt_text}]
                                        }],
                                        "turn_complete": True
                                    }
                                }
                                await gemini_ws.send(json.dumps(action_msg))
                                
                            elif data.get('type') == 'system_instructions':
                                logger.info("[SYSTEM] System instructions already applied at setup")
                                
                    except Exception as e:
                        logger.error(f"Client receive error: {e}")
                        logger.error(traceback.format_exc())

                async def receive_from_gemini():
                    """Stream responses from Gemini → browser."""
                    nonlocal audio_out_count
                    try:
                        async for raw_msg in gemini_ws:
                            try:
                                msg = json.loads(raw_msg)
                            except json.JSONDecodeError:
                                logger.warning(f"Non-JSON from Gemini: {str(raw_msg)[:100]}")
                                continue
                            
                            # ── Server content (audio, text, turn signals) ──
                            server_content = msg.get("serverContent")
                            if server_content:
                                # Interrupted (barge-in)
                                if server_content.get("interrupted"):
                                    logger.info("[GEMINI] Barge-in detected")
                                    await websocket.send_json({"event": "INTERRUPTED"})
                                
                                # Model turn (audio/text output)
                                model_turn = server_content.get("modelTurn")
                                if model_turn:
                                    for part in model_turn.get("parts", []):
                                        # Audio output
                                        inline_data = part.get("inlineData")
                                        if inline_data:
                                            audio_out_count += 1
                                            b64_audio = inline_data.get("data", "")
                                            await websocket.send_json({"audio": b64_audio})
                                            if audio_out_count <= 3 or audio_out_count % 50 == 0:
                                                logger.info(f"[GEMINI AUDIO OUT] Chunk #{audio_out_count}")
                                        
                                        # Text output (thinking/transcription from model_turn)
                                        text = part.get("text")
                                        if text:
                                            logger.info(f"[GEMINI TEXT] {text[:150]}")
                                            await websocket.send_json({
                                                "event": "TRANSCRIPTION",
                                                "source": "model",
                                                "text": text
                                            })
                                            
                                            text_lower = text.lower().strip()
                                            # State machine transitions
                                            if state_machine.phase == LessonPhase.INTRO:
                                                if any(kw in text_lower for kw in ["first word", "your turn", "think", "say the word"]):
                                                    state_machine.start_practice()
                                                    state_machine.start_nudge_timer(send_nudge)
                                                    await websocket.send_json({
                                                        "event": "STATE_CHANGE",
                                                        "state": state_machine.to_dict()
                                                    })
                                                    logger.info("[STATE] INTRO → PRACTICE")
                                            elif state_machine.phase == LessonPhase.PRACTICE:
                                                advanced_this_turn = False
                                                
                                                # 1. Check for success praise FIRST
                                                if any(kw in text_lower for kw in ["perfect", "nailed it", "awesome", "great job", "got it", "well done", "good job"]):
                                                    result = state_machine.record_success()
                                                    await websocket.send_json({"event": "SUCCESS"})
                                                    if result["advance"]:
                                                        state_machine.advance_exercise()
                                                        advanced_this_turn = True
                                                        
                                                # 2. Check for manual advance IF we haven't already advanced this turn
                                                if not advanced_this_turn and any(kw in text_lower for kw in ["next up", "next word", "next phrase", "moving on", "let's try", "now try"]):
                                                    state_machine.advance_exercise()
                                                
                                                # 3. Always broadcast the new state and reset the nudge timer
                                                state_machine.start_nudge_timer(send_nudge)
                                                await websocket.send_json({
                                                    "event": "STATE_CHANGE",
                                                    "state": state_machine.to_dict()
                                                })
                                
                                # Turn complete
                                if server_content.get("turnComplete"):
                                    logger.info(f"[GEMINI] Turn complete (audio out: {audio_out_count})")
                                    await websocket.send_json({"event": "TURN_COMPLETE"})
                                    if state_machine.phase == LessonPhase.PRACTICE:
                                        state_machine.start_nudge_timer(send_nudge)
                            
                            # ── Input transcription ──
                            input_transcription = msg.get("inputTranscription")
                            if input_transcription:
                                text = input_transcription.get("text", "")
                                if text:
                                    logger.info(f"[USER SPEECH] '{text}'")
                                    await websocket.send_json({
                                        "event": "TRANSCRIPTION",
                                        "source": "user",
                                        "text": text
                                    })
                            
                            # ── Output transcription ──
                            output_transcription = msg.get("outputTranscription")
                            if output_transcription:
                                text = output_transcription.get("text", "")
                                if text:
                                    logger.info(f"[AURA SPEECH] '{text}'")
                                    await websocket.send_json({
                                        "event": "TRANSCRIPTION",
                                        "source": "model",
                                        "text": text
                                    })
                                    
                    except websockets.exceptions.ConnectionClosed as e:
                        logger.error(f"Gemini WebSocket closed: {e}")
                    except Exception as e:
                        logger.error(f"Gemini receive error: {e}")
                        logger.error(traceback.format_exc())

                # Run both streams concurrently
                logger.info("Starting bidirectional audio streams...")
                results = await asyncio.gather(
                    receive_from_client(),
                    receive_from_gemini(),
                    return_exceptions=True
                )
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Stream {i} failed: {result}")

        except Exception as e:
            logger.error(f"CRITICAL: Gemini Live error: {e}")
            logger.error(traceback.format_exc())
            try:
                await websocket.send_json({"error": str(e)})
            except:
                pass
        finally:
            state_machine.cancel_nudge_timer()
            self.active_session = None
            logger.info(f"Session ended. Audio in: {audio_in_count}, Audio out: {audio_out_count}")
