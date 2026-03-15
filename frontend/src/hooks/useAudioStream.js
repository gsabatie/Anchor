import { useState, useRef, useCallback, useEffect } from 'react'

/**
 * ScriptProcessorNode fallback for browsers without AudioWorklet support.
 * Deprecated but functional on older Safari/Firefox.
 */
function createScriptProcessorFallback(ctx, onAudioDataRef) {
  const bufferSize = 2048
  const processor = ctx.createScriptProcessor(bufferSize, 1, 1)
  const ratio = ctx.sampleRate / 16000
  const needsResample = Math.abs(ratio - 1.0) > 0.01
  let resampleAccum = 0

  processor.onaudioprocess = (e) => {
    const raw = e.inputBuffer.getChannelData(0)

    let samples = raw
    if (needsResample) {
      const out = []
      while (resampleAccum < raw.length) {
        const idx = Math.floor(resampleAccum)
        const frac = resampleAccum - idx
        const a = raw[idx]
        const b = idx + 1 < raw.length ? raw[idx + 1] : a
        out.push(a + (b - a) * frac)
        resampleAccum += ratio
      }
      resampleAccum -= raw.length
      samples = out
    }

    const int16 = new Int16Array(samples.length)
    for (let i = 0; i < samples.length; i++) {
      const s = Math.max(-1, Math.min(1, samples[i]))
      int16[i] = s < 0 ? s * 0x8000 : s * 0x7fff
    }
    onAudioDataRef.current?.(int16.buffer)

    // Compute RMS for level metering
    let sumSq = 0
    for (let i = 0; i < raw.length; i++) sumSq += raw[i] * raw[i]
    // Store on the processor node for the level ref
    processor._lastLevel = Math.min(1, Math.sqrt(sumSq / raw.length) * 3)

    // Output silence to keep the graph alive
    const output = e.outputBuffer.getChannelData(0)
    output.fill(0)
  }
  processor._lastLevel = 0
  return processor
}

export function useAudioStream(onAudioData) {
  const [status, setStatus] = useState('idle')
  const [error, setError] = useState(null)
  const levelRef = useRef(0)

  const mediaStreamRef = useRef(null)
  const audioContextRef = useRef(null)
  const workletNodeRef = useRef(null)
  const processorNodeRef = useRef(null) // ScriptProcessor fallback
  const usingWorklet = useRef(false)

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

      // Safari iOS may silently create at native rate instead of 16kHz.
      // The PCM processor handles resampling, but log the discrepancy.
      if (ctx.sampleRate !== 16000) {
        console.warn(
          `AudioContext created at ${ctx.sampleRate}Hz instead of 16000Hz — PCM processor will resample`
        )
      }

      const source = ctx.createMediaStreamSource(stream)

      // Try AudioWorklet first, fall back to ScriptProcessor
      const hasWorklet = typeof ctx.audioWorklet !== 'undefined'

      if (hasWorklet) {
        try {
          await ctx.audioWorklet.addModule('/pcm-processor.js')

          const workletNode = new AudioWorkletNode(ctx, 'pcm-processor')
          workletNodeRef.current = workletNode
          usingWorklet.current = true

          workletNode.port.onmessage = (e) => {
            if (e.data.type === 'pcm') {
              onAudioDataRef.current?.(e.data.buffer)
            } else if (e.data.type === 'level') {
              levelRef.current = e.data.value
            }
          }

          source.connect(workletNode)
          workletNode.connect(ctx.destination)
          setStatus('recording')
          return
        } catch (workletErr) {
          console.warn('AudioWorklet setup failed, falling back to ScriptProcessor:', workletErr)
        }
      }

      // Fallback: ScriptProcessorNode (deprecated but widely supported)
      const processor = createScriptProcessorFallback(ctx, onAudioDataRef)
      processorNodeRef.current = processor
      usingWorklet.current = false

      source.connect(processor)
      processor.connect(ctx.destination)

      // Poll level from ScriptProcessor for metering
      const levelInterval = setInterval(() => {
        levelRef.current = processor._lastLevel || 0
      }, 50)
      processor._levelInterval = levelInterval

      setStatus('recording')
    } catch (err) {
      console.error('Audio setup failed:', err)
      stream.getTracks().forEach((t) => t.stop())
      setError('micError')
      setStatus('error')
    }
  }, [])

  const stop = useCallback(() => {
    // Flush remaining samples from the worklet before disconnecting
    if (usingWorklet.current && workletNodeRef.current) {
      workletNodeRef.current.port.postMessage({ type: 'flush' })
      // Give the worklet a moment to flush, then disconnect
      setTimeout(() => {
        workletNodeRef.current?.disconnect()
        workletNodeRef.current = null
      }, 50)
    } else {
      workletNodeRef.current?.disconnect()
      workletNodeRef.current = null
    }

    if (processorNodeRef.current) {
      if (processorNodeRef.current._levelInterval) {
        clearInterval(processorNodeRef.current._levelInterval)
      }
      processorNodeRef.current.disconnect()
      processorNodeRef.current = null
    }

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
      if (processorNodeRef.current) {
        if (processorNodeRef.current._levelInterval) {
          clearInterval(processorNodeRef.current._levelInterval)
        }
        processorNodeRef.current.disconnect()
      }
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
