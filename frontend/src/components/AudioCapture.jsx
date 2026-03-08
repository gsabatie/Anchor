import { useCallback, useState } from 'react'
import { useAudioStream } from '../hooks/useAudioStream'

export default function AudioCapture({ sendAudio, websocket }) {
  const [isProcessing, setIsProcessing] = useState(false)

  const handleAudioData = useCallback((pcm16Buffer) => {
    if (!sendAudio) return
    // pcm16Buffer is already an ArrayBuffer of Int16 PCM at 16kHz
    sendAudio(pcm16Buffer)
  }, [sendAudio])

  const { recording, start, stop } = useAudioStream(handleAudioData)

  const handleStartRecording = useCallback(async () => {
    setIsProcessing(true)
    try {
      await start()
    } catch (err) {
      console.error('Error starting recording:', err)
      setIsProcessing(false)
    }
  }, [start])

  const handleStopRecording = useCallback(() => {
    stop()
    setIsProcessing(false)
  }, [stop])

  const isConnected = websocket?.readyState === WebSocket.OPEN

  return (
    <div className="audio-capture">
      <button
        onClick={recording ? handleStopRecording : handleStartRecording}
        disabled={!isConnected || isProcessing}
        className={`audio-btn ${recording ? 'recording' : ''} ${!isConnected ? 'disabled' : ''}`}
      >
        {recording ? '⏹ Arrêter' : '🎤 Parler'}
      </button>
      {!isConnected && <span className="status-text">Connexion en cours...</span>}
    </div>
  )
}
