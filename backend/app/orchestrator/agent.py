import os
import asyncio
import base64
import json
from fastapi import WebSocket
from google import genai
from google.genai import types
from dotenv import load_dotenv
from app.orchestrator.state_machine import LessonStateMachine, LessonPhase

# Load .env from backend root
load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), ".env"))

LESSON_SCRIPT = """
=== HARD-CODED LESSON SCRIPT ===
You MUST follow this exact sequence of exercises. Do NOT skip or reorder.

LESSON: "TH Sounds — /θ/ (voiceless) and /ð/ (voiced)"

Exercise 1: "THINK"
  - Target phoneme: /θ/ (voiceless TH)
  - Coaching tip: "Tongue between your teeth, blow air out gently — no voicing."

Exercise 2: "THE"
  - Target phoneme: /ð/ (voiced TH)
  - Coaching tip: "Same tongue position, but add your voice — feel the vibration."

Exercise 3: "THOUGHT"
  - Target phoneme: /θ/
  - Coaching tip: "Open your mouth a bit wider. Tongue out, then pull back for the 'aw' sound."

Exercise 4: "Repeat after me: The thin thing thought through the thicket"
  - Mixed /θ/ and /ð/ — full sentence
  - Coaching tip: "This is the boss level! Take it slow. Every TH is tongue-between-teeth."

Exercise 5: "BREATHE"
  - Target phoneme: /ð/ (voiced TH at end)
  - Coaching tip: "The TH at the end needs voice. Don't drop it to a plain 'D' sound."

Exercise 6: "Repeat after me: They thought that three thin threads were free"
  - Mixed — full sentence
  - Coaching tip: "Slow and deliberate. I want to see that tongue working!"

=== END LESSON SCRIPT ===

FLOW for EACH exercise:
1. Say: "Alright, exercise [N]!" then say the word/phrase clearly.
2. Say: "Your turn — let me hear it!"
3. Listen to the user's attempt.
4. Give IMMEDIATE phonetic feedback (1 sentence max): "Good!" / "Almost — your TH sounded like a D. Tongue between teeth!" / "Nailed it!"
5. If they need another attempt, say "One more time!" and listen again.
6. After 3 attempts (good or not), move on: "Great effort! Next one..."
7. If the user is silent, nudge them: "Give it a go, I'm listening!"
"""


class FluentlyAgent:
    def __init__(self):
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if not self.api_key:
            print("WARNING: GEMINI_API_KEY is not set.")
        
        self.client = genai.Client(
            api_key=self.api_key,
            http_options=types.HttpOptions(api_version="v1alpha")
        )
        self.model_id = "gemini-2.5-flash-native-audio-preview-12-2025"
        self.active_session = None
        
    def build_system_prompt(self, custom_instructions=None):
        base = custom_instructions or ""
        return f"""{base}

You are Aura — a DRILL SERGEANT for speech, not a chatbot.

=== IDENTITY ===
You are a warm but DRIVEN speech coach. Think supportive personal trainer, not customer service bot.
You NEVER wait for the user to "type" or "send" anything. This is a LIVE AUDIO session — you speak, they speak, no turns.

=== CRITICAL RULES ===
1. You ALWAYS speak first. Greet warmly, then IMMEDIATELY ask if they're ready to start.
2. Once the user says ANYTHING resembling "yes", "ready", "let's go", "sure", "okay" — IMMEDIATELY start Exercise 1. Do NOT ask again.
3. Keep EVERY response to 1-2 SHORT sentences. Be punchy and energetic.
4. NEVER say robotic phrases: "I am processing", "Please wait", "Let me analyze", "Aura is listening."
5. NEVER ask meta-questions: "How was that?", "Do you understand?", "Was that clear?"
6. After giving feedback, IMMEDIATELY move to the next step. No dead air.
7. If the user is silent for a few seconds during practice, nudge: "Give it a go, I'm listening!", "No worries, take your time!", "You got this — let me hear it!"
8. If the user interrupts you, STOP talking instantly.

=== VOICE & TONE ===
- Sound like a real human friend, not a robot.
- Use natural phrases: "Got it", "Right", "Okay", "Keep going", "Almost!", "Nailed it! 🎉", "So close!"
- When they succeed: celebrate! "Yes! Perfect!", "That was awesome!"
- When they struggle: model it slowly. "Listen closely... [word]. Now you try."
- After success, transition fast: "Great job! Next up..."

=== PRONUNCIATION COACHING ===
- Describe mouth positions VERBALLY (audio only, no visuals).
- Example: "Put your tongue between your teeth and blow air out gently."
- When you hear an error, be SPECIFIC: "Your TH sounded like a D — tongue needs to be between your teeth, not behind them."
- For repeated errors, slow down and exaggerate: "Thhhhhh-ink. Really push that tongue forward."

{LESSON_SCRIPT}"""

    async def run_session(self, websocket: WebSocket, system_instructions: str = None):
        prompt = self.build_system_prompt(system_instructions)
        
        # ── Task 1: Server-side VAD with aggressive silence detection ──
        config = types.LiveConnectConfig(
            response_modalities=[types.Modality.AUDIO],
            system_instruction=types.Content(parts=[types.Part.from_text(text=prompt)]),
            input_audio_transcription=types.AudioTranscriptionConfig(),
            output_audio_transcription=types.AudioTranscriptionConfig(),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=False,
                    start_of_speech_sensitivity=types.StartSensitivity.START_SENSITIVITY_HIGH,
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_HIGH,
                    silence_duration_ms=500,
                    prefix_padding_ms=100,
                )
            ),
        )
        
        # ── Task 3: Lesson state machine ──
        state_machine = LessonStateMachine(total_exercises=6, max_attempts=3)
        
        try:
            print(f"Connecting to Gemini Live (streaming) with model: {self.model_id}")
            async with self.client.aio.live.connect(model=self.model_id, config=config) as session:
                self.active_session = session
                print("Gemini Live session established — continuous coaching mode")
                
                # Send initial state to frontend
                await websocket.send_json({
                    "event": "STATE_CHANGE", 
                    "state": state_machine.to_dict()
                })
                
                # Proactive: Aura speaks first
                await session.send(
                    input="The session just started. Greet the user with one short, warm, energetic sentence. Then ask if they're ready to practice TH sounds. Sound human and natural — like a friend, not a robot.",
                    end_of_turn=True
                )
                
                # ── Silence nudge callback ──
                async def send_nudge():
                    """Fired when user is silent for 3s during PRACTICE phase."""
                    if state_machine.phase == LessonPhase.PRACTICE:
                        try:
                            await session.send(
                                input="The user has been silent for a few seconds. Nudge them encouragingly to try the current exercise. Say something like 'Give it a go, I'm listening!' or 'No worries, take your time!' — keep it to one short sentence.",
                                end_of_turn=True
                            )
                            await websocket.send_json({"event": "NUDGE"})
                        except Exception as e:
                            print(f"Nudge error: {e}")
                
                async def receive_from_client():
                    """Continuously stream audio from client to Gemini — mic stays hot."""
                    try:
                        while True:
                            raw = await websocket.receive_text()
                            data = json.loads(raw)
                            
                            if data.get('type') == 'audio':
                                pcm_bytes = base64.b64decode(data['data'])
                                # Stream audio directly via media_chunks — no buffering
                                await session.send(input=types.LiveClientRealtimeInput(
                                    media_chunks=[types.Blob(data=pcm_bytes, mime_type="audio/pcm;rate=16000")]
                                ))
                                # Reset nudge timer — user is active
                                state_machine.reset_nudge_timer()
                                
                            elif data.get('type') == 'text_action':
                                action = data.get('action', '')
                                prompts = {
                                    "I'm stuck": "The user is stuck and needs help. Give them a clear, encouraging hint. Say the current word slowly and clearly with coaching tips about mouth position. Keep it to 2 sentences max.",
                                    "Repeat that": "The user wants you to repeat the current exercise word/phrase. Say it again slowly, clearly, and with emphasis on the TH sounds.",
                                    "Skip this word": "The user wants to skip this exercise. Say 'No problem!' and move to the next exercise immediately.",
                                    "Next lesson": "The user completed this lesson. Congratulate them enthusiastically and wrap up.",
                                }
                                prompt_text = prompts.get(action, f"The user clicked '{action}'. Respond naturally.")
                                
                                # Handle skip → advance state
                                if action == "Skip this word":
                                    result = state_machine.advance_exercise()
                                    await websocket.send_json({
                                        "event": "STATE_CHANGE",
                                        "state": state_machine.to_dict()
                                    })
                                
                                await session.send(input=prompt_text, end_of_turn=True)
                                
                            elif data.get('type') == 'system_instructions':
                                pass  # Already handled at session creation
                                
                    except Exception as e:
                        print(f"Client receive error: {e}")

                async def receive_from_gemini():
                    """Stream audio from Gemini back to client — handle all events."""
                    try:
                        async for response in session.receive():
                            server_content = response.server_content
                            if server_content is not None:
                                # ── Barge-in: user interrupted Aura ──
                                if server_content.interrupted:
                                    await websocket.send_json({"event": "INTERRUPTED"})
                                
                                # ── Audio data from model ──
                                model_turn = server_content.model_turn
                                if model_turn is not None:
                                    for part in model_turn.parts:
                                        if part.inline_data:
                                            b64 = base64.b64encode(part.inline_data.data).decode('utf-8')
                                            await websocket.send_json({"audio": b64})

                                        # ── Handle transcription for state tracking ──
                                        if part.text:
                                            text_lower = part.text.lower().strip()
                                            await websocket.send_json({
                                                "event": "TRANSCRIPTION",
                                                "source": "model",
                                                "text": part.text
                                            })
                                            
                                            # State transitions based on model output
                                            if state_machine.phase == LessonPhase.INTRO:
                                                # Aura is in intro phase — once she presents exercise 1,
                                                # transition to practice
                                                if any(kw in text_lower for kw in ["exercise 1", "first word", "repeat after me", "your turn"]):
                                                    state_machine.start_practice()
                                                    state_machine.start_nudge_timer(send_nudge)
                                                    await websocket.send_json({
                                                        "event": "STATE_CHANGE",
                                                        "state": state_machine.to_dict()
                                                    })
                                            
                                            elif state_machine.phase == LessonPhase.PRACTICE:
                                                # Track when Aura moves to next exercise
                                                if any(kw in text_lower for kw in ["next up", "next one", "exercise", "moving on", "great effort"]):
                                                    result = state_machine.advance_exercise()
                                                    state_machine.start_nudge_timer(send_nudge)
                                                    await websocket.send_json({
                                                        "event": "STATE_CHANGE",
                                                        "state": state_machine.to_dict()
                                                    })
                                                # Track successful attempts
                                                elif any(kw in text_lower for kw in ["perfect", "nailed it", "awesome", "great job", "got it", "well done"]):
                                                    await websocket.send_json({"event": "SUCCESS"})
                                
                                # ── Turn complete ──
                                if server_content.turn_complete:
                                    await websocket.send_json({"event": "TURN_COMPLETE"})
                                    # After Aura finishes speaking in PRACTICE, start nudge timer
                                    if state_machine.phase == LessonPhase.PRACTICE:
                                        state_machine.start_nudge_timer(send_nudge)
                            
                            # ── Handle transcription of user input ──
                            if hasattr(response, 'input_transcription') and response.input_transcription:
                                if hasattr(response.input_transcription, 'text') and response.input_transcription.text:
                                    await websocket.send_json({
                                        "event": "TRANSCRIPTION",
                                        "source": "user",
                                        "text": response.input_transcription.text
                                    })

                            # ── Handle output transcription ──
                            if hasattr(response, 'output_transcription') and response.output_transcription:
                                if hasattr(response.output_transcription, 'text') and response.output_transcription.text:
                                    await websocket.send_json({
                                        "event": "TRANSCRIPTION",
                                        "source": "model",
                                        "text": response.output_transcription.text
                                    })
                                    
                            # ── Setup complete ──
                            if response.setup_complete is not None:
                                print("Gemini Live setup complete — session ready")
                                
                    except Exception as e:
                        print(f"Gemini receive error: {e}")

                # Run both streams concurrently — true bidirectional streaming
                await asyncio.gather(
                    receive_from_client(),
                    receive_from_gemini(),
                    return_exceptions=True
                )
                
        except Exception as e:
            print(f"CRITICAL: Gemini Live error: {e}")
            import traceback
            traceback.print_exc()
            try:
                await websocket.send_json({"error": str(e)})
            except:
                pass
        finally:
            state_machine.cancel_nudge_timer()
            self.active_session = None
