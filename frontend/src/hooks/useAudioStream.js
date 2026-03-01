import { useState, useRef, useCallback } from 'react'

export function useAudioStream(onAudioData) {
  const [recording, setRecording] = useState(false)
  const mediaStreamRef = useRef(null)
  const processorRef = useRef(null)
  const contextRef = useRef(null)

  const start = useCallback(async () => {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    mediaStreamRef.current = stream

    const context = new AudioContext({ sampleRate: 16000 })
    contextRef.current = context

    const source = context.createMediaStreamSource(stream)
    const processor = context.createScriptProcessor(4096, 1, 1)
    processorRef.current = processor

    processor.onaudioprocess = (e) => {
      const pcm = e.inputBuffer.getChannelData(0)
      onAudioData(pcm.buffer.slice(0))
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
