import { useEffect, useRef, useState, useCallback } from 'react'

const WS_URL = `${import.meta.env.VITE_BACKEND_WS_URL || 'ws://localhost:8000'}/ws/session`

export function useWebSocket() {
  const wsRef = useRef(null)
  const [status, setStatus] = useState('disconnected')
  const [exposureImage, setExposureImage] = useState(null)
  const [timerData, setTimerData] = useState(null)

  useEffect(() => {
    const ws = new WebSocket(WS_URL)
    wsRef.current = ws

    ws.onopen = () => setStatus('connected')
    ws.onclose = () => setStatus('disconnected')
    ws.onerror = () => setStatus('error')

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data)
      if (msg.type === 'exposure_image') {
        setExposureImage(msg.url)
      } else if (msg.type === 'timer') {
        setTimerData(msg)
      }
    }

    return () => ws.close()
  }, [])

  const send = useCallback((data) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      if (data instanceof ArrayBuffer || data instanceof Blob) {
        wsRef.current.send(data)
      } else {
        wsRef.current.send(JSON.stringify(data))
      }
    }
  }, [])

  return { status, exposureImage, timerData, send }
}
