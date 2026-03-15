import { useEffect, useRef, useState, useCallback } from 'react'

const WS_BASE = import.meta.env.VITE_BACKEND_WS_URL
  || (import.meta.env.DEV ? 'ws://localhost:8000' : `wss://${window.location.host}`)
const WS_URL = `${WS_BASE}/ws/session`

// Gemini Live outputs PCM16 at 24kHz
const PLAYBACK_SAMPLE_RATE = 24000

const MAX_RECONNECT_ATTEMPTS = 3

export function useWebSocket(token) {
  const wsRef = useRef(null)
  const audioCtxRef = useRef(null)
  const nextPlayTimeRef = useRef(0)
  const reconnectAttemptsRef = useRef(0)
  const reconnectTimerRef = useRef(null)
  const intentionalDisconnectRef = useRef(false)
  const [status, setStatus] = useState('disconnected')
  const [exposureImage, setExposureImage] = useState(null)
  const [timerData, setTimerData] = useState(null)
  const [transcript, setTranscript] = useState([])
  const [error, setError] = useState(null)
  const [isThinking, setIsThinking] = useState(false)
  const [crisisAlert, setCrisisAlert] = useState(null)
  const [reassuranceViolation, setReassuranceViolation] = useState(null)

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

  const connect = useCallback((connectToken) => {
    if (!connectToken) return

    // Mark this as an intentional new connection attempt
    intentionalDisconnectRef.current = false
    reconnectAttemptsRef.current = 0

    const url = `${WS_URL}?token=${encodeURIComponent(connectToken)}`
    const ws = new WebSocket(url)
    wsRef.current = ws

    ws.binaryType = 'arraybuffer'

    ws.onopen = () => {
      reconnectAttemptsRef.current = 0
      setStatus('connected')
      setError(null)
    }

    ws.onclose = (event) => {
      console.log('WebSocket disconnected:', event.code, event.reason)
      setIsThinking(false)

      if (
        !intentionalDisconnectRef.current &&
        reconnectAttemptsRef.current < MAX_RECONNECT_ATTEMPTS
      ) {
        const delay = Math.pow(2, reconnectAttemptsRef.current) * 1000
        reconnectAttemptsRef.current += 1
        console.log(
          `Reconnecting in ${delay}ms (attempt ${reconnectAttemptsRef.current}/${MAX_RECONNECT_ATTEMPTS})`
        )
        setStatus('reconnecting')
        reconnectTimerRef.current = setTimeout(() => {
          connect(connectToken)
        }, delay)
      } else {
        setStatus('disconnected')
      }
    }

    ws.onerror = () => {
      setError('WebSocket connection error')
    }

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data)

        switch (msg.type) {
          case 'ping':
            // Keepalive ping from server — no action needed
            break

          case 'connection':
            setIsThinking(false)
            setTranscript([{ role: 'assistant', content: msg.message }])
            break

          case 'text':
            setIsThinking(false)
            setTranscript(prev => [
              ...prev,
              { role: 'assistant', content: msg.content }
            ])
            break

          case 'transcript_delta':
            setIsThinking(false)
            setTranscript(prev => {
              const last = prev[prev.length - 1]
              if (last && last.role === 'assistant' && last.streaming) {
                // Append to the current streaming message
                return [
                  ...prev.slice(0, -1),
                  { ...last, content: last.content + msg.content }
                ]
              }
              // Start a new streaming message
              return [
                ...prev,
                { role: 'assistant', content: msg.content, streaming: true }
              ]
            })
            break

          case 'turn_complete':
            setIsThinking(false)
            setTranscript(prev => {
              const last = prev[prev.length - 1]
              if (last && last.streaming) {
                return [
                  ...prev.slice(0, -1),
                  { role: last.role, content: last.content }
                ]
              }
              return prev
            })
            break

          case 'audio':
            setIsThinking(false)
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

          case 'crisis_alert':
            // Safety-critical: user expressed crisis language
            setCrisisAlert({
              redirect: msg.redirect,
              timestamp: Date.now(),
            })
            setTranscript(prev => [
              ...prev,
              { role: 'system', content: msg.redirect, crisis: true }
            ])
            break

          case 'reassurance_violation':
            // Model spoke reassurance in audio — show correction
            setReassuranceViolation({
              replacement: msg.replacement,
              timestamp: Date.now(),
            })
            setTranscript(prev => [
              ...prev,
              { role: 'system', content: msg.replacement, correction: true }
            ])
            break

          case 'user_transcript':
            // Input transcription is used for crisis_guard on the backend.
            // Not displayed — native-audio transcription is too noisy for UI.
            break

          case 'reconnecting':
            // Gemini backend is reconnecting — show a transient status
            setIsThinking(false)
            setStatus('reconnecting')
            break

          case 'reconnected':
            setStatus('connected')
            setError(null)
            break

          case 'error':
            setIsThinking(false)
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
  }, [playPcmAudio])

  const disconnect = useCallback(() => {
    intentionalDisconnectRef.current = true
    if (reconnectTimerRef.current) {
      clearTimeout(reconnectTimerRef.current)
      reconnectTimerRef.current = null
    }
    if (wsRef.current) {
      wsRef.current.close()
      wsRef.current = null
    }
    setStatus('disconnected')
  }, [])

  useEffect(() => {
    if (!token) return

    connect(token)

    return () => {
      intentionalDisconnectRef.current = true
      if (reconnectTimerRef.current) {
        clearTimeout(reconnectTimerRef.current)
        reconnectTimerRef.current = null
      }
      if (wsRef.current) {
        wsRef.current.close()
        wsRef.current = null
      }
      if (audioCtxRef.current) {
        audioCtxRef.current.close()
        audioCtxRef.current = null
      }
    }
  }, [token, connect])

  const sendAudio = useCallback((audioBuffer) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setIsThinking(true)
      // Send raw PCM16 bytes directly as binary
      wsRef.current.send(audioBuffer)
    }
  }, [])

  const sendMessage = useCallback((text) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      setIsThinking(true)
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
    isThinking,
    crisisAlert,
    reassuranceViolation,
    connect,
    disconnect,
    sendAudio,
    sendMessage,
    sendControl,
    ws: wsRef.current
  }
}
