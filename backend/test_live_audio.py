"""
Minimal test script to verify Gemini Live API audio input works.
This generates a sine wave tone and sends it to the API to test if VAD triggers.
"""
import os
import asyncio
import math
import struct
import base64
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

API_KEY = os.environ.get("GEMINI_API_KEY")
if not API_KEY:
    print("ERROR: GEMINI_API_KEY not set in .env")
    exit(1)

client = genai.Client(
    api_key=API_KEY,
    http_options=types.HttpOptions(api_version="v1alpha")
)

# Try multiple models to find one that works
MODELS_TO_TRY = [
    "gemini-2.0-flash-live-preview-04-09",
    "gemini-live-2.5-flash-preview",
    "gemini-2.5-flash-native-audio-preview-12-2025",
]

def generate_speech_like_audio(duration_s=2.0, sample_rate=16000):
    """Generate a simple tone that should trigger VAD."""
    num_samples = int(duration_s * sample_rate)
    samples = []
    for i in range(num_samples):
        t = i / sample_rate
        # Mix of frequencies to sound speech-like
        val = 0.3 * math.sin(2 * math.pi * 200 * t)  # fundamental
        val += 0.2 * math.sin(2 * math.pi * 400 * t)  # harmonic
        val += 0.1 * math.sin(2 * math.pi * 800 * t)  # harmonic
        # Add some variation
        val *= 0.5 + 0.5 * math.sin(2 * math.pi * 3 * t)  # envelope
        samples.append(val)
    
    # Convert to PCM16
    pcm_bytes = b''
    for s in samples:
        s = max(-1.0, min(1.0, s))
        pcm_bytes += struct.pack('<h', int(s * 32767))
    return pcm_bytes

async def test_model(model_id):
    print(f"\n{'='*60}")
    print(f"Testing model: {model_id}")
    print(f"{'='*60}")
    
    config = types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=types.Content(parts=[types.Part.from_text(
            text="You are a speech coach. When you hear someone speak, respond immediately with feedback."
        )]),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
    )
    
    try:
        async with client.aio.live.connect(model=model_id, config=config) as session:
            print(f"[OK] Connected to {model_id}")
            
            # Step 1: Send text to trigger initial response
            print("[SEND] Sending text prompt...")
            await session.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part.from_text(text="Say hello briefly.")]
                ),
                turn_complete=True
            )
            
            # Step 2: Receive initial response
            got_audio = False
            got_text = False
            response_count = 0
            
            print("[RECV] Waiting for initial response...")
            async for response in session.receive():
                response_count += 1
                
                if response.setup_complete is not None:
                    print(f"[OK] Setup complete")
                    continue
                
                sc = response.server_content
                if sc:
                    if sc.model_turn:
                        for part in sc.model_turn.parts:
                            if part.inline_data:
                                if not got_audio:
                                    print(f"[OK] Got audio output ({len(part.inline_data.data)} bytes)")
                                    got_audio = True
                            if part.text:
                                print(f"[OK] Got text: '{part.text[:100]}'")
                                got_text = True
                    
                    if sc.turn_complete:
                        print(f"[OK] Turn complete after {response_count} responses")
                        break
                
                if hasattr(response, 'output_transcription') and response.output_transcription:
                    if hasattr(response.output_transcription, 'text') and response.output_transcription.text:
                        print(f"[OK] Output transcription: '{response.output_transcription.text}'")
            
            # Step 3: Send audio
            print("\n[SEND] Sending 2 seconds of generated audio...")
            audio_data = generate_speech_like_audio(duration_s=2.0, sample_rate=16000)
            
            # Send in chunks of ~100ms (1600 samples = 3200 bytes)
            chunk_size = 3200
            chunks_sent = 0
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i+chunk_size]
                await session.send_realtime_input(
                    audio=types.Blob(data=chunk, mime_type="audio/pcm;rate=16000")
                )
                chunks_sent += 1
            print(f"[OK] Sent {chunks_sent} audio chunks ({len(audio_data)} bytes total)")
            
            # Step 4: Wait for response to audio
            print("[RECV] Waiting for audio response (10s timeout)...")
            got_audio_response = False
            try:
                response_task = asyncio.create_task(_receive_responses(session))
                got_audio_response = await asyncio.wait_for(response_task, timeout=10.0)
            except asyncio.TimeoutError:
                print("[FAIL] No response after 10 seconds — VAD did not trigger")
            
            if got_audio_response:
                print(f"\n✅ SUCCESS: Model {model_id} responds to audio input!")
            else:
                print(f"\n❌ FAIL: Model {model_id} does NOT respond to audio input")
            
            return got_audio_response
            
    except Exception as e:
        print(f"[ERROR] {e}")
        return False

async def _receive_responses(session):
    """Receive responses from Gemini, return True if we get audio back."""
    async for response in session.receive():
        sc = response.server_content
        if sc:
            if sc.model_turn:
                for part in sc.model_turn.parts:
                    if part.inline_data:
                        print(f"[OK] Got audio response! ({len(part.inline_data.data)} bytes)")
                        return True
                    if part.text:
                        print(f"[OK] Got text response: '{part.text[:100]}'")
            if sc.turn_complete:
                print(f"[OK] Turn complete")
                return True
        
        if hasattr(response, 'input_transcription') and response.input_transcription:
            if hasattr(response.input_transcription, 'text') and response.input_transcription.text:
                print(f"[OK] Input transcription: '{response.input_transcription.text}'")
        
        if hasattr(response, 'output_transcription') and response.output_transcription:
            if hasattr(response.output_transcription, 'text') and response.output_transcription.text:
                print(f"[OK] Output transcription: '{response.output_transcription.text}'")
    
    return False

async def main():
    print("Gemini Live API Audio Test")
    print("=" * 60)
    
    working_models = []
    for model_id in MODELS_TO_TRY:
        try:
            result = await test_model(model_id)
            if result:
                working_models.append(model_id)
        except Exception as e:
            print(f"[SKIP] {model_id}: {e}")
    
    print(f"\n\n{'='*60}")
    print(f"RESULTS")
    print(f"{'='*60}")
    if working_models:
        print(f"✅ Working models: {working_models}")
    else:
        print(f"❌ No models responded to audio input")

if __name__ == "__main__":
    asyncio.run(main())
