"""
Test 2: More thorough test of Gemini Live API audio input.
Tests multiple approaches to sending audio, including manual activity signals.
"""
import os
import asyncio
import math
import struct
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

API_KEY = os.environ.get("GEMINI_API_KEY")
client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(api_version="v1alpha")
)

MODEL = "gemini-2.5-flash-native-audio-preview-12-2025"

def generate_pcm_audio(duration_s=2.0, sample_rate=16000):
    """Generate a 440Hz tone as PCM16."""
    num_samples = int(duration_s * sample_rate)
    pcm = bytearray()
    for i in range(num_samples):
        t = i / sample_rate
        val = 0.5 * math.sin(2 * math.pi * 440 * t)
        pcm += struct.pack('<h', int(val * 32767))
    return bytes(pcm)

async def test_approach_1():
    """Approach 1: send_realtime_input with activity_start/activity_end signals."""
    print("\n--- Test 1: send_realtime_input + activity signals ---")
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(parts=[types.Part.from_text(
            text="When you hear audio, say 'I heard you!'"
        )]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=True,  # Disable auto VAD, we'll signal manually
            )
        ),
    )
    
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("[OK] Connected")
            
            # Wait for setup
            async for resp in session.receive():
                if resp.setup_complete is not None:
                    print("[OK] Setup complete")
                    break
            
            # Signal activity start
            print("[SEND] Signaling activity_start...")
            await session.send_realtime_input(activity_start=types.ActivityStart())
            
            # Send audio
            audio = generate_pcm_audio(2.0)
            chunk_size = 3200
            for i in range(0, len(audio), chunk_size):
                await session.send_realtime_input(
                    audio=types.Blob(data=audio[i:i+chunk_size], mime_type="audio/pcm;rate=16000")
                )
            print(f"[OK] Sent {len(audio)} bytes of audio")
            
            # Signal activity end
            print("[SEND] Signaling activity_end...")
            await session.send_realtime_input(activity_end=types.ActivityEnd())
            
            # Wait for response
            print("[RECV] Waiting 10s for response...")
            try:
                got_response = False
                async def receive():
                    nonlocal got_response
                    async for resp in session.receive():
                        sc = resp.server_content
                        if sc:
                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if part.inline_data:
                                        print(f"[OK] Got audio! ({len(part.inline_data.data)} bytes)")
                                        got_response = True
                                    if part.text:
                                        print(f"[OK] Got text: '{part.text[:200]}'")
                                        got_response = True
                            if sc.turn_complete:
                                print("[OK] Turn complete")
                                return
                        if hasattr(resp, 'input_transcription') and resp.input_transcription:
                            if hasattr(resp.input_transcription, 'text') and resp.input_transcription.text:
                                print(f"[OK] Input transcription: '{resp.input_transcription.text}'")
                        if hasattr(resp, 'output_transcription') and resp.output_transcription:
                            if hasattr(resp.output_transcription, 'text') and resp.output_transcription.text:
                                print(f"[OK] Output transcription: '{resp.output_transcription.text}'")
                
                await asyncio.wait_for(receive(), timeout=10.0)
                if got_response:
                    print("✅ Test 1 PASSED")
                    return True
            except asyncio.TimeoutError:
                print("❌ Test 1 FAILED (timeout)")
    except Exception as e:
        print(f"[ERROR] {e}")
    return False

async def test_approach_2():
    """Approach 2: Use send_client_content with audio part."""
    print("\n--- Test 2: send_client_content with audio blob ---")
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(parts=[types.Part.from_text(
            text="When you hear audio, say 'I heard you!'"
        )]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
    
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("[OK] Connected")
            
            # Wait for setup
            async for resp in session.receive():
                if resp.setup_complete is not None:
                    print("[OK] Setup complete")
                    break
            
            # Send audio as content
            audio = generate_pcm_audio(2.0)
            print(f"[SEND] Sending {len(audio)} bytes as Content...")
            
            import base64
            audio_b64 = base64.b64encode(audio).decode('utf-8')
            
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(inline_data=types.Blob(
                        data=audio,
                        mime_type="audio/pcm;rate=16000"
                    ))]
                ),
                turn_complete=True
            )
            print("[OK] Sent audio content")
            
            # Wait for response
            print("[RECV] Waiting 10s for response...")
            try:
                got_response = False
                async def receive():
                    nonlocal got_response
                    async for resp in session.receive():
                        sc = resp.server_content
                        if sc:
                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if part.inline_data:
                                        print(f"[OK] Got audio! ({len(part.inline_data.data)} bytes)")
                                        got_response = True
                                    if part.text:
                                        print(f"[OK] Got text: '{part.text[:200]}'")
                                        got_response = True
                            if sc.turn_complete:
                                print("[OK] Turn complete")
                                return
                        if hasattr(resp, 'input_transcription') and resp.input_transcription:
                            if hasattr(resp.input_transcription, 'text') and resp.input_transcription.text:
                                print(f"[OK] Input transcription: '{resp.input_transcription.text}'")
                        if hasattr(resp, 'output_transcription') and resp.output_transcription:
                            if hasattr(resp.output_transcription, 'text') and resp.output_transcription.text:
                                print(f"[OK] Output transcription: '{resp.output_transcription.text}'")
                
                await asyncio.wait_for(receive(), timeout=10.0)
                if got_response:
                    print("✅ Test 2 PASSED")
                    return True
            except asyncio.TimeoutError:
                print("❌ Test 2 FAILED (timeout)")
    except Exception as e:
        print(f"[ERROR] {e}")
    return False

async def test_approach_3():
    """Approach 3: send_realtime_input with auto VAD, September model."""
    print("\n--- Test 3: September 2025 model ---")
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(parts=[types.Part.from_text(
            text="When you hear audio, say 'I heard you!'"
        )]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
    )
    
    try:
        async with client.aio.live.connect(
            model="gemini-2.5-flash-native-audio-preview-09-2025", 
            config=config
        ) as session:
            print("[OK] Connected to September model")
            
            async for resp in session.receive():
                if resp.setup_complete is not None:
                    print("[OK] Setup complete")
                    break
            
            audio = generate_pcm_audio(2.0)
            chunk_size = 3200
            for i in range(0, len(audio), chunk_size):
                await session.send_realtime_input(
                    audio=types.Blob(data=audio[i:i+chunk_size], mime_type="audio/pcm;rate=16000")
                )
            print(f"[OK] Sent {len(audio)} bytes")
            
            print("[RECV] Waiting 10s for response...")
            try:
                got_response = False
                async def receive():
                    nonlocal got_response
                    async for resp in session.receive():
                        sc = resp.server_content
                        if sc:
                            if sc.model_turn:
                                for part in sc.model_turn.parts:
                                    if part.inline_data:
                                        print(f"[OK] Got audio! ({len(part.inline_data.data)} bytes)")
                                        got_response = True
                                    if part.text:
                                        print(f"[OK] Got text: '{part.text[:200]}'")
                                        got_response = True
                            if sc.turn_complete:
                                print("[OK] Turn complete")
                                return
                        if hasattr(resp, 'input_transcription') and resp.input_transcription:
                            if hasattr(resp.input_transcription, 'text') and resp.input_transcription.text:
                                print(f"[OK] Input transcription: '{resp.input_transcription.text}'")
                
                await asyncio.wait_for(receive(), timeout=10.0)
                if got_response:
                    print("✅ Test 3 PASSED")
                    return True
            except asyncio.TimeoutError:
                print("❌ Test 3 FAILED (timeout)")
    except Exception as e:
        print(f"[ERROR] {e}")
    return False

async def main():
    print("Gemini Live API Audio Input — Comprehensive Test")
    print("=" * 60)
    
    r1 = await test_approach_1()
    r2 = await test_approach_2()
    r3 = await test_approach_3()
    
    print(f"\n\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    print(f"Test 1 (manual activity signals):  {'✅ PASS' if r1 else '❌ FAIL'}")
    print(f"Test 2 (audio as Content):         {'✅ PASS' if r2 else '❌ FAIL'}")
    print(f"Test 3 (September 2025 model):     {'✅ PASS' if r3 else '❌ FAIL'}")

asyncio.run(main())
