import { useState, useRef, useCallback, useEffect } from 'react'

export function useAudioStream(onAudioData) {
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const levelRef = useRef(0)

  const mediaStreamRef = useRef(null)
  const audioContextRef = useRef(null)
  const workletNodeRef = useRef(null)

  // Keep callback ref stable to avoid recreating worklet on callback change
  const onAudioDataRef = useRef(onAudioData)
  useEffect(() => {
    onAudioDataRef.current = onAudioData
  }, [onAudioData])

  const start = useCallback(async () => {
    setStatus('requesting')
    setError(null)

    let stream
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        audio: {
          sampleRate: 16000,
          channelCount: 1,
          echoCancellation: true,
          noiseSuppression: true,
        },
      })
    } catch (err) {
      const msg =
        err.name === 'NotAllowedError'
          ? 'micPermissionDenied'
          : err.name === 'NotFoundError' || err.name === 'OverconstrainedError'
            ? 'micNotFound'
            : 'micError'
      setError(msg)
      setStatus('error')
      return
    }

    mediaStreamRef.current = stream

    try {
      const ctx = new AudioContext({ sampleRate: 16000 })
      audioContextRef.current = ctx

      // Safari iOS may silently create at native rate instead of 16kHz
      if (ctx.sampleRate !== 16000) {
        console.warn(`AudioContext created at ${ctx.sampleRate}Hz instead of 16000Hz — audio may be distorted`)
      }

      await ctx.audioWorklet.addModule('/pcm-processor.js')

      const workletNode = new AudioWorkletNode(ctx, 'pcm-processor')
      workletNodeRef.current = workletNode

      workletNode.port.onmessage = (e) => {
        if (e.data.type === 'pcm') {
          onAudioDataRef.current?.(e.data.buffer)
        } else if (e.data.type === 'level') {
          levelRef.current = e.data.value
        }
      }

      const source = ctx.createMediaStreamSource(stream)
      source.connect(workletNode)
      // Connect to destination to keep the audio graph alive (worklet outputs silence)
      workletNode.connect(ctx.destination)

      setStatus('recording')
    } catch (err) {
      console.error('AudioWorklet setup failed:', err)
      stream.getTracks().forEach((t) => t.stop())
      setError('micError')
      setStatus('error')
    }
  }, [])

  const stop = useCallback(() => {
    workletNodeRef.current?.disconnect()
    workletNodeRef.current = null

    audioContextRef.current?.close()
    audioContextRef.current = null

    mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
    mediaStreamRef.current = null

    levelRef.current = 0
    setStatus('idle')
    setError(null)
  }, [])

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      workletNodeRef.current?.disconnect()
      audioContextRef.current?.close()
      mediaStreamRef.current?.getTracks().forEach((t) => t.stop())
    }
  }, [])

  return {
    status,
    recording: status === 'recording',
    level: levelRef,
    start,
    stop,
    error,
  }
}
