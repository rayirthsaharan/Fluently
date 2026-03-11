/**
 * AudioProcessor worklet — optimized for low-latency real-time streaming.
 * Smaller buffer = less latency but more frequent messages.
 * 512 samples at 16kHz = 32ms chunks — ideal for real-time speech.
 */
class AudioProcessor extends AudioWorkletProcessor {
  constructor() {
    super();
    this.bufferSize = 512; // 32ms at 16kHz — low latency
    this.buffer = new Float32Array(this.bufferSize);
    this.bufferIndex = 0;
  }

  process(inputs, outputs, parameters) {
    const input = inputs[0];
    if (input.length > 0) {
      const channelData = input[0];
      
      for (let i = 0; i < channelData.length; i++) {
        this.buffer[this.bufferIndex++] = channelData[i];
        
        if (this.bufferIndex >= this.bufferSize) {
          // Send Float32 chunk to main thread for PCM16 conversion
          const chunk = new Float32Array(this.buffer);
          this.port.postMessage(chunk);
          this.bufferIndex = 0;
        }
      }
    }
    return true;
  }
}

registerProcessor('audio-processor', AudioProcessor);
