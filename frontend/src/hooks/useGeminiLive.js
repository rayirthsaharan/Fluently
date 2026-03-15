import { useState, useRef, useCallback } from 'react';
import { floatTo16BitPCM, bufferToBase64, base64ToArrayBuffer } from '../utils/audio';

/**
 * useGeminiLive — Continuous bidirectional audio streaming hook.
 * 
 * Audio pipeline:
 *   Mic → AudioWorklet (32ms chunks @ 16kHz) → PCM16 → WebSocket → Backend → Gemini
 *   Gemini → Backend → WebSocket → PCM16 → Float32 → ScheduledBuffer → Speakers
 * 
 * The mic stays HOT throughout — no turn switching.
 * Server-side VAD handles speech detection automatically.
 */
export function useGeminiLive(wsUrl = 'ws://localhost:8000/ws') {
  const [isConnected, setIsConnected] = useState(false);
  const [sessionState, setSessionState] = useState('IDLE');
  const [lessonState, setLessonState] = useState(null);
  const [transcription, setTranscription] = useState({ source: '', text: '' });
  
  const wsRef = useRef(null);
  const micAudioContextRef = useRef(null);
  const playbackContextRef = useRef(null);
  const audioWorkletNodeRef = useRef(null);
  const mediaStreamRef = useRef(null);
  
  // Scheduled playback — eliminates crackle by queueing audio with precise timestamps
  const nextPlayTimeRef = useRef(0);
  const isPlayingRef = useRef(false);
  const eventHandlersRef = useRef({ 
    onSuccess: null, 
    onInterrupted: null, 
    onTurnComplete: null,
    onStateChange: null,
    onNudge: null,
    onTranscription: null,
  });

  const pcm16ToFloat32 = (arrayBuffer) => {
    const int16 = new Int16Array(arrayBuffer);
    const float32 = new Float32Array(int16.length);
    for (let i = 0; i < int16.length; i++) {
      float32[i] = int16[i] / 32768.0;
    }
    return float32;
  };

  /**
   * Schedule an audio chunk for gapless playback.
   * Uses precise scheduling to prevent gaps/crackle between chunks.
   */
  const scheduleAudioChunk = useCallback((base64Audio) => {
    const ctx = playbackContextRef.current;
    if (!ctx) return;

    try {
      const arrayBuffer = base64ToArrayBuffer(base64Audio);
      const float32Data = pcm16ToFloat32(arrayBuffer);
      
      const sampleRate = 24000;
      const audioBuffer = ctx.createBuffer(1, float32Data.length, sampleRate);
      audioBuffer.copyToChannel(float32Data, 0);
      
      const source = ctx.createBufferSource();
      source.buffer = audioBuffer;
      source.connect(ctx.destination);
      
      // Schedule precisely to prevent gaps
      const now = ctx.currentTime;
      const startTime = Math.max(now, nextPlayTimeRef.current);
      source.start(startTime);
      nextPlayTimeRef.current = startTime + audioBuffer.duration;
      isPlayingRef.current = true;

      // Track when playback finishes
      source.onended = () => {
        if (ctx.currentTime >= nextPlayTimeRef.current - 0.01) {
          isPlayingRef.current = false;
        }
      };
      
    } catch (e) {
      console.error('Audio schedule error:', e);
    }
  }, []);

  /**
   * Stop all scheduled audio immediately (for barge-in).
   * Recreate the context to kill all queued sources.
   */
  const flushAudio = useCallback(async () => {
    if (playbackContextRef.current) {
      await playbackContextRef.current.close();
    }
    playbackContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
    await playbackContextRef.current.resume();
    nextPlayTimeRef.current = 0;
    isPlayingRef.current = false;
  }, []);

  const connect = useCallback(async (systemInstructions = null) => {
    setSessionState('CONNECTING');
    wsRef.current = new WebSocket(wsUrl);
    
    wsRef.current.onopen = () => {
      console.log('Connected — continuous coaching mode');
      setIsConnected(true);
      setSessionState('ACTIVE');
      
      if (systemInstructions) {
        wsRef.current.send(JSON.stringify({ 
          type: 'system_instructions', 
          data: systemInstructions 
        }));
      }
    };
    
    wsRef.current.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        
        // ── Audio from Aura ──
        if (msg.audio) {
          scheduleAudioChunk(msg.audio);
          setSessionState('AGENT_SPEAKING');
        }
        
        // ── Turn complete: Aura finished speaking, session remains active ──
        if (msg.event === 'TURN_COMPLETE') {
          // Aura finished speaking — flush output buffer so we're ready for next input
          nextPlayTimeRef.current = 0;
          isPlayingRef.current = false;
          setSessionState('ACTIVE');
          eventHandlersRef.current.onTurnComplete?.();
        }
        
        // ── Barge-in: user spoke while Aura was talking ──
        if (msg.event === 'INTERRUPTED') {
          flushAudio(); // Kill queued audio immediately
          setSessionState('ACTIVE');
          eventHandlersRef.current.onInterrupted?.();
        }
        
        // ── Pronunciation success ──
        if (msg.event === 'SUCCESS') {
          eventHandlersRef.current.onSuccess?.();
        }
        
        // ── Lesson state machine update ──
        if (msg.event === 'STATE_CHANGE') {
          setLessonState(msg.state);
          eventHandlersRef.current.onStateChange?.(msg.state);
        }
        
        // ── Silence nudge ──
        if (msg.event === 'NUDGE') {
          setSessionState('AGENT_SPEAKING');
          eventHandlersRef.current.onNudge?.();
        }
        
        // ── Transcription (input or output) ──
        if (msg.event === 'TRANSCRIPTION') {
          const t = { source: msg.source, text: msg.text };
          setTranscription(t);
          eventHandlersRef.current.onTranscription?.(t);
        }
        
        // ── Error from backend ──
        if (msg.error) {
          console.error('Backend error:', msg.error);
        }
        
      } catch (e) {
        console.warn('WS parse error:', event.data);
      }
    };
    
    wsRef.current.onclose = () => {
      setIsConnected(false);
      setSessionState('IDLE');
      setLessonState(null);
    };
    
    wsRef.current.onerror = (e) => {
      console.error('WebSocket error:', e);
    };
    
    await startAudioCapture();
  }, [wsUrl, scheduleAudioChunk, flushAudio]);

  const startAudioCapture = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ 
        audio: {
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
          autoGainControl: true,
        }, 
        video: false
      });
      mediaStreamRef.current = stream;
      
      // Use the browser's NATIVE sample rate — do NOT force 16kHz
      // (browsers on macOS often can't run at 16kHz and silently resample incorrectly)
      micAudioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      const nativeSampleRate = micAudioContextRef.current.sampleRate;
      console.log(`[AUDIO] Mic AudioContext native sample rate: ${nativeSampleRate}Hz`);
      
      await micAudioContextRef.current.audioWorklet.addModule('/worklets/audio-processor.js');
      
      // Playback context at 24kHz (Gemini output rate)
      playbackContextRef.current = new (window.AudioContext || window.webkitAudioContext)({ sampleRate: 24000 });
      await playbackContextRef.current.resume();
      nextPlayTimeRef.current = 0;
      
      const source = micAudioContextRef.current.createMediaStreamSource(stream);
      const processor = new AudioWorkletNode(micAudioContextRef.current, 'audio-processor');
      
      // Calculate downsample ratio from native rate to 16kHz
      const targetRate = 16000;
      const downsampleRatio = nativeSampleRate / targetRate;
      let chunksSent = 0;
      
      // Mic stays HOT — continuously stream audio regardless of session state
      processor.port.onmessage = (e) => {
        if (wsRef.current?.readyState === WebSocket.OPEN) {
          const inputData = e.data; // Float32Array at native sample rate
          
          // Resample to 16kHz using linear interpolation (avoids aliasing)
          let outputData;
          if (Math.abs(downsampleRatio - 1.0) < 0.01) {
            outputData = inputData;
          } else {
            const outputLength = Math.round(inputData.length * targetRate / nativeSampleRate);
            outputData = new Float32Array(outputLength);
            for (let i = 0; i < outputLength; i++) {
              const srcIndex = i * downsampleRatio;
              const srcFloor = Math.floor(srcIndex);
              const srcCeil = Math.min(srcFloor + 1, inputData.length - 1);
              const frac = srcIndex - srcFloor;
              outputData[i] = inputData[srcFloor] * (1 - frac) + inputData[srcCeil] * frac;
            }
          }
          
          const pcm16Data = floatTo16BitPCM(outputData);
          const base64Audio = bufferToBase64(pcm16Data);
          wsRef.current.send(JSON.stringify({ type: 'audio', data: base64Audio }));
          
          chunksSent++;
          if (chunksSent <= 5) {
            // Log RMS level to verify mic is actually capturing audio
            let sumSq = 0;
            let maxAmp = 0;
            for (let i = 0; i < outputData.length; i++) {
              sumSq += outputData[i] * outputData[i];
              maxAmp = Math.max(maxAmp, Math.abs(outputData[i]));
            }
            const rms = Math.sqrt(sumSq / outputData.length);
            console.log(`[AUDIO] Chunk #${chunksSent}: ${outputData.length} samples, RMS=${rms.toFixed(4)}, maxAmp=${maxAmp.toFixed(4)}, ${pcm16Data.byteLength} bytes`);
          }
        }
      };
      
      source.connect(processor);
      audioWorkletNodeRef.current = processor;
      
    } catch (err) {
      console.error('Mic error:', err);
    }
  };

  const sendAction = useCallback((action) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: 'text_action', action }));
      setSessionState('AGENT_SPEAKING');
    }
  }, []);

  const setEventHandlers = useCallback((handlers) => {
    eventHandlersRef.current = { ...eventHandlersRef.current, ...handlers };
  }, []);

  const disconnect = useCallback(() => {
    if (wsRef.current) wsRef.current.close();
    if (mediaStreamRef.current) mediaStreamRef.current.getTracks().forEach(t => t.stop());
    if (micAudioContextRef.current) micAudioContextRef.current.close();
    if (playbackContextRef.current) playbackContextRef.current.close();
    nextPlayTimeRef.current = 0;
    isPlayingRef.current = false;
  }, []);

  return { 
    connect, disconnect, isConnected, sessionState, 
    sendAction, setEventHandlers,
    lessonState, transcription,
  };
}
