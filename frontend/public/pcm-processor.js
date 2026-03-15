/**
 * AudioWorklet processor for PCM16 capture at 16kHz.
 * Runs on the audio rendering thread — no DOM, no imports.
 *
 * Handles the Safari/iOS case where AudioContext ignores the requested
 * sampleRate and creates at native rate (44100/48000).  When that happens,
 * we downsample to 16kHz before emitting PCM.
 *
 * Posts two message types to the main thread:
 *   { type: 'pcm', buffer: ArrayBuffer }  — Int16 PCM chunk (Transferable)
 *   { type: 'level', value: number }       — RMS level 0.0–1.0
 *
 * Receives from the main thread:
 *   { type: 'flush' }  — flush remaining samples on stop
 */
class PcmProcessor extends AudioWorkletProcessor {
  constructor() {
    super()
    this._buffer = new Float32Array(2048)
    this._offset = 0
    // sampleRate is a global in AudioWorkletGlobalScope
    this._ratio = sampleRate / 16000
    this._resample = Math.abs(this._ratio - 1.0) > 0.01
    // Fractional accumulator for non-integer ratios (e.g. 44100/16000 = 2.75625)
    this._resampleAccum = 0

    this._stopped = false

    this.port.onmessage = (e) => {
      if (e.data.type === 'flush') {
        this._flush()
        this._stopped = true
      }
    }
  }

  process(inputs) {
    if (this._stopped) return false

    const input = inputs[0]
    if (!input || !input[0]) return true

    const raw = input[0]
    let samples

    if (this._resample) {
      // Downsample from native rate to 16kHz using linear interpolation
      samples = this._downsample(raw)
    } else {
      samples = raw
    }

    for (let i = 0; i < samples.length; i++) {
      this._buffer[this._offset++] = samples[i]

      if (this._offset >= this._buffer.length) {
        this._flush()
      }
    }

    // Post RMS level every process() call (~128 samples) for smooth metering
    let sumSq = 0
    for (let i = 0; i < raw.length; i++) {
      sumSq += raw[i] * raw[i]
    }
    const rms = Math.sqrt(sumSq / raw.length)
    this.port.postMessage({ type: 'level', value: Math.min(1, rms * 3) })

    return true
  }

  /**
   * Downsample a Float32 chunk from native sample rate to 16kHz.
   * Uses linear interpolation for fractional ratios.
   */
  _downsample(input) {
    const ratio = this._ratio
    const output = []
    let accum = this._resampleAccum

    while (accum < input.length) {
      const idx = Math.floor(accum)
      const frac = accum - idx
      const a = input[idx]
      const b = idx + 1 < input.length ? input[idx + 1] : a
      output.push(a + (b - a) * frac)
      accum += ratio
    }
    // Carry fractional position to next call for seamless chunks
    this._resampleAccum = accum - input.length

    return output
  }

  _flush() {
    if (this._offset === 0) return

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
