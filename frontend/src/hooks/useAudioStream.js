import { useState, useRef, useCallback } from 'react'

/**
 * Convert Float32 PCM samples to Int16 PCM bytes.
 * Gemini Live expects PCM16 at 16kHz mono.
 */
function float32ToInt16(float32Array) {
  const int16 = new Int16Array(float32Array.length)
  for (let i = 0; i < float32Array.length; i++) {
    const s = Math.max(-1, Math.min(1, float32Array[i]))
    int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
  }
  return int16.buffer
}

export function useAudioStream(onAudioData) {
  const [recording, setRecording] = useState(false)
  const mediaStreamRef = useRef(null)
  const processorRef = useRef(null)
  const contextRef = useRef(null)

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        sampleRate: 16000,
        channelCount: 1,
        echoCancellation: true,
        noiseSuppression: true,
      }
    })
    mediaStreamRef.current = stream

    const context = new AudioContext({ sampleRate: 16000 })
    contextRef.current = context

    const source = context.createMediaStreamSource(stream)
    const processor = context.createScriptProcessor(4096, 1, 1)
    processorRef.current = processor

    processor.onaudioprocess = (e) => {
      const float32 = e.inputBuffer.getChannelData(0)
      // Convert to Int16 PCM for Gemini Live
      const pcm16 = float32ToInt16(float32)
      onAudioData(pcm16)
    }

    source.connect(processor)
    processor.connect(context.destination)
    setRecording(true)
  }, [onAudioData])

  const stop = useCallback(() => {
    processorRef.current?.disconnect()
    contextRef.current?.close()
    mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
    setRecording(false)
  }, [])

  return { recording, start, stop }
}
