import { useAudioStream } from '../hooks/useAudioStream'

export default function AudioCapture({ onAudioData }) {
  const { recording, start, stop } = useAudioStream(onAudioData)

  return (
    <div className="audio-capture">
      <button onClick={recording ? stop : start}>
        {recording ? '⏹ Arrêter' : '🎤 Parler'}
      </button>
    </div>
  )
}
