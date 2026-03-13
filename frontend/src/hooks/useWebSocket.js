import { useEffect, useRef, useState, useCallback } from 'react'

const WS_BASE = import.meta.env.VITE_BACKEND_WS_URL
  || (import.meta.env.DEV ? 'ws://localhost:8000' : `wss://${window.location.host}`)
const WS_URL = `${WS_BASE}/ws/session`

// Gemini Live outputs PCM16 at 24kHz
const PLAYBACK_SAMPLE_RATE = 24000

export function useWebSocket(token) {
  const wsRef = useRef(null)
  const audioCtxRef = useRef(null)
  const nextPlayTimeRef = useRef(0)
  const [status, setStatus] = useState('disconnected')
  const [exposureImage, setExposureImage] = useState(null)
  const [timerData, setTimerData] = useState(null)
  const [transcript, setTranscript] = useState([])
  const [error, setError] = useState(null)

  const getAudioContext = useCallback(() => {
    if (!audioCtxRef.current || audioCtxRef.current.state === 'closed') {
      audioCtxRef.current = new AudioContext({ sampleRate: PLAYBACK_SAMPLE_RATE })
      nextPlayTimeRef.current = 0
    }
    return audioCtxRef.current
  }, [])

  const playPcmAudio = useCallback((base64Data) => {
    try {
      const ctx = getAudioContext()
      if (ctx.state === 'suspended') {
        ctx.resume()
      }

      // Decode base64 to Int16 PCM bytes
      const binaryStr = atob(base64Data)
      const bytes = new Uint8Array(binaryStr.length)
      for (let i = 0; i < binaryStr.length; i++) {
        bytes[i] = binaryStr.charCodeAt(i)
      }

      // Convert Int16 PCM to Float32 for Web Audio API
      const int16 = new Int16Array(bytes.buffer)
      const float32 = new Float32Array(int16.length)
      for (let i = 0; i < int16.length; i++) {
        float32[i] = int16[i] / 32768
      }

      // Create audio buffer and schedule playback
      const audioBuffer = ctx.createBuffer(1, float32.length, PLAYBACK_SAMPLE_RATE)
      audioBuffer.getChannelData(0).set(float32)

      const source = ctx.createBufferSource()
      source.buffer = audioBuffer

      source.connect(ctx.destination)

      // Schedule seamless playback
      const now = ctx.currentTime
      const startTime = Math.max(now, nextPlayTimeRef.current)
      source.start(startTime)
      nextPlayTimeRef.current = startTime + audioBuffer.duration
    } catch (err) {
      console.error('Error playing PCM audio:', err)
    }
  }, [getAudioContext])

  useEffect(() => {
    if (!token) return

    const url = `${WS_URL}?token=${encodeURIComponent(token)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      setStatus('connected')
      setError(null)
    }

    ws.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason)
      setStatus('disconnected')
    }

    ws.onerror = () => {
      setError('WebSocket connection error')
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        switch (msg.type) {
          case 'connection':
            setTranscript([{ role: 'assistant', content: msg.message }])
            break

          case 'text':
            setTranscript(prev => [
              ...prev,
              { role: 'assistant', content: msg.content }
            ])
            break

          case 'audio':
            if (msg.data) {
              playPcmAudio(msg.data)
            }
            break

          case 'exposure_image':
            setExposureImage({
              src: msg.image_base64,
              level: msg.level,
              prompt: msg.prompt_used,
              timestamp: Date.now(),
            })
            break

          case 'timer':
            setTimerData(msg)
            break

          case 'error':
            console.error('Server error:', msg.message)
            setError(msg.message)
            break

          default:
            console.debug('Unknown message type:', msg.type)
        }
      } catch (err) {
        console.warn('Failed to parse WebSocket message:', err)
      }
    }

    return () => {
      ws.close()
      if (audioCtxRef.current) {
        audioCtxRef.current.close()
        audioCtxRef.current = null
      }
    }
  }, [token, playPcmAudio])

  const sendAudio = useCallback((audioBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      // Send raw PCM16 bytes directly as binary
      wsRef.current.send(audioBuffer)
    }
  }, [])

  const sendMessage = useCallback((text) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setTranscript(prev => [
        ...prev,
        { role: 'user', content: text }
      ])
      wsRef.current.send(JSON.stringify({
        type: 'text',
        content: text,
      }))
    }
  }, [])

  const sendControl = useCallback((action) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({
        type: 'control',
        action
      }))
    }
  }, [])

  return {
    status,
    exposureImage,
    timerData,
    transcript,
    error,
    sendAudio,
    sendMessage,
    sendControl,
    ws: wsRef.current
  }
}
