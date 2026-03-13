/**
 * AudioWorklet processor for PCM16 capture.
 * Runs on the audio rendering thread — no DOM, no imports.
 *
 * Posts two message types to the main thread:
 *   { type: 'pcm', buffer: ArrayBuffer }  — Int16 PCM chunk (Transferable)
 *   { type: 'level', value: number }       — RMS level 0.0–1.0
 */
class PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._buffer = new Float32Array(2048)
    this._offset = 0
  }

  process(inputs) {
    const input = inputs[0]
    if (!input || !input[0]) return true

    const samples = input[0]

    for (let i = 0; i < samples.length; i++) {
      this._buffer[this._offset++] = samples[i]

      if (this._offset >= this._buffer.length) {
        this._flush()
      }
    }

    // Post RMS level every process() call (~128 samples) for smooth metering
    let sumSq = 0
    for (let i = 0; i < samples.length; i++) {
      sumSq += samples[i] * samples[i]
    }
    const rms = Math.sqrt(sumSq / samples.length)
    this.port.postMessage({ type: 'level', value: Math.min(1, rms * 3) })

    return true
  }

  _flush() {
    const int16 = new Int16Array(this._offset)
    for (let i = 0; i < this._offset; i++) {
      const s = Math.max(-1, Math.min(1, this._buffer[i]))
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
    this.port.postMessage({ type: 'pcm', buffer: int16.buffer }, [int16.buffer])
    this._offset = 0
  }
}

registerProcessor('pcm-processor', PcmProcessor)
