"""
Minimal test: Try `media=` instead of `audio=` for send_realtime_input,
and also try sending text after audio to force a response.
"""
import os
import asyncio
import math
import struct
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

client = genai.Client(
    api_key=os.environ.get("GEMINI_API_KEY"),
    http_options=types.HttpOptions(api_version="v1alpha")
)

MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

def gen_audio(duration=2.0, rate=16000):
    pcm = bytearray()
    for i in range(int(duration * rate)):
        t = i / rate
        val = 0.5 * math.sin(2 * math.pi * 440 * t)
        pcm += struct.pack('<h', int(val * 32767))
    return bytes(pcm)

async def test_media_param():
    """Test using media= instead of audio= for send_realtime_input."""
    print("\n--- Test A: send_realtime_input(media=Blob) ---")
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(parts=[types.Part.from_text(
            text="Say 'I heard you' when you hear audio."
        )]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
    
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("[OK] Connected")
            
            audio = gen_audio(2.0)
            chunk_size = 3200
            chunks = 0
            for i in range(0, len(audio), chunk_size):
                chunk = audio[i:i+chunk_size]
                # Use `media=` not `audio=`
                await session.send_realtime_input(
                    media=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                )
                chunks += 1
            print(f"[OK] Sent {chunks} chunks via media= param")
            
            print("[RECV] Waiting 15s for response...")
            try:
                async def recv():
                    async for resp in session.receive():
                        sc = resp.server_content
                        if sc:
                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if part.inline_data:
                                        print(f"[OK] Audio response! ({len(part.inline_data.data)} bytes)")
                                        return True
                                    if part.text:
                                        print(f"[OK] Text: '{part.text[:150]}'")
                            if sc.turn_complete:
                                print("[OK] Turn complete")
                                return True
                        if hasattr(resp, 'input_transcription') and resp.input_transcription:
                            if hasattr(resp.input_transcription, 'text') and resp.input_transcription.text:
                                print(f"[OK] Input transcribed: '{resp.input_transcription.text}'")
                        if hasattr(resp, 'output_transcription') and resp.output_transcription:
                            if hasattr(resp.output_transcription, 'text') and resp.output_transcription.text:
                                print(f"[OK] Output transcribed: '{resp.output_transcription.text}'")
                    return False
                result = await asyncio.wait_for(recv(), timeout=15.0)
                print(f"{'✅ PASS' if result else '❌ FAIL'}")
                return result
            except asyncio.TimeoutError:
                print("❌ FAIL (timeout)")
    except Exception as e:
        print(f"[ERROR] {e}")
    return False

async def test_audio_then_text():
    """Test: send audio, then immediately send text forcing the model to respond."""
    print("\n--- Test B: Audio + follow-up text prompt ---")
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(parts=[types.Part.from_text(
            text="You are a speech coach. Analyze any audio you hear and give pronunciation feedback."
        )]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
    
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("[OK] Connected")
            
            # Send audio first
            audio = gen_audio(2.0)
            chunk_size = 3200
            for i in range(0, len(audio), chunk_size):
                await session.send_realtime_input(
                    media=types.Blob(data=audio[i:i+chunk_size], mime_type="audio/pcm;rate=16000")
                )
            print("[OK] Sent audio")
            
            # Wait a moment, then send text to force a response
            await asyncio.sleep(1)
            print("[SEND] Sending text to force response...")
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="What did you hear? Please describe the audio you just received.")]
                ),
                turn_complete=True
            )
            
            print("[RECV] Waiting 15s for response...")
            try:
                async def recv():
                    async for resp in session.receive():
                        sc = resp.server_content
                        if sc:
                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if part.inline_data:
                                        print(f"[OK] Audio response! ({len(part.inline_data.data)} bytes)")
                                    if part.text:
                                        print(f"[OK] Text: '{part.text[:200]}'")
                            if sc.turn_complete:
                                print("[OK] Turn complete")
                                return True
                        if hasattr(resp, 'output_transcription') and resp.output_transcription:
                            if hasattr(resp.output_transcription, 'text') and resp.output_transcription.text:
                                print(f"[OK] Output: '{resp.output_transcription.text}'")
                    return False
                result = await asyncio.wait_for(recv(), timeout=15.0)
                print(f"{'✅ PASS' if result else '❌ FAIL'}")
                return result
            except asyncio.TimeoutError:
                print("❌ FAIL (timeout)")
    except Exception as e:
        print(f"[ERROR] {e}")
    return False

async def test_text_only():
    """Control test: just text, verify models works at all."""
    print("\n--- Test C: Text only (control) ---")
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(parts=[types.Part.from_text(
            text="Say 'hello' briefly."
        )]),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
    
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("[OK] Connected")
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="Say hello")]
                ),
                turn_complete=True
            )
            
            try:
                async def recv():
                    async for resp in session.receive():
                        sc = resp.server_content
                        if sc:
                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if part.inline_data:
                                        print(f"[OK] Audio! ({len(part.inline_data.data)} bytes)")
                                    if part.text:
                                        print(f"[OK] Text: '{part.text[:150]}'")
                            if sc.turn_complete:
                                print("[OK] Turn complete")
                                return True
                        if hasattr(resp, 'output_transcription') and resp.output_transcription:
                            if hasattr(resp.output_transcription, 'text') and resp.output_transcription.text:
                                print(f"[OK] Output: '{resp.output_transcription.text}'")
                    return False
                result = await asyncio.wait_for(recv(), timeout=10.0)
                print(f"{'✅ PASS' if result else '❌ FAIL'}")
                return result
            except asyncio.TimeoutError:
                print("❌ FAIL (timeout)")
    except Exception as e:
        print(f"[ERROR] {e}")
    return False

async def main():
    print("Gemini Live API — Targeted Audio Tests")
    print("=" * 60)
    
    rc = await test_text_only()
    ra = await test_media_param()
    rb = await test_audio_then_text()
    
    print(f"\n{'='*60}")
    print(f"Test C (text only / control): {'✅' if rc else '❌'}")
    print(f"Test A (media= param):        {'✅' if ra else '❌'}")
    print(f"Test B (audio + text):        {'✅' if rb else '❌'}")

asyncio.run(main())
