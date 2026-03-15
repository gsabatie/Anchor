import { useCallback, useRef, useEffect } from 'react'
import { useTranslation } from 'react-i18next'
import { useAudioStream } from '../hooks/useAudioStream'
import './AudioCapture.css'

function MicIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M12 14c1.66 0 3-1.34 3-3V5c0-1.66-1.34-3-3-3S9 3.34 9 5v6c0 1.66 1.34 3 3 3zm-1-9c0-.55.45-1 1-1s1 .45 1 1v6c0 .55-.45 1-1 1s-1-.45-1-1V5z" />
      <path d="M17 11c0 2.76-2.24 5-5 5s-5-2.24-5-5H5c0 3.53 2.61 6.43 6 6.92V21h2v-3.08c3.39-.49 6-3.39 6-6.92h-2z" />
    </svg>
  )
}

function StopIcon() {
  return (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <rect x="6" y="6" width="12" height="12" rx="2" />
    </svg>
  )
}

export default function AudioCapture({ sendAudio, muted }) {
  const { t } = useTranslation()
  const canvasRef = useRef(null)
  const rafRef = useRef(null)

  const mutedRef = useRef(muted)
  mutedRef.current = muted

  const handleAudioData = useCallback(
    (pcm16Buffer) => {
      // Suppress mic input while Anchor is speaking to prevent echo feedback
      if (mutedRef.current) return
      sendAudio?.(pcm16Buffer)
    },
    [sendAudio],
  )

  const { status, level: levelRef, start, stop, error } = useAudioStream(handleAudioData)

  // Canvas level meter animation loop
  useEffect(() => {
    if (status !== 'recording') {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
      return
    }

    const canvas = canvasRef.current
    if (!canvas) return
    const ctx = canvas.getContext('2d')
    const w = canvas.width
    const h = canvas.height

    function draw() {
      ctx.clearRect(0, 0, w, h)

      const level = levelRef.current
      const barWidth = level * w

      if (barWidth > 0) {
        const gradient = ctx.createLinearGradient(0, 0, w, 0)
        gradient.addColorStop(0, '#7DBCA8')
        gradient.addColorStop(0.6, '#E8B86B')
        gradient.addColorStop(1, '#E8836B')

        ctx.fillStyle = gradient
        ctx.beginPath()
        ctx.roundRect(0, 0, barWidth, h, h / 2)
        ctx.fill()
      }

      rafRef.current = requestAnimationFrame(draw)
    }

    rafRef.current = requestAnimationFrame(draw)

    return () => {
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current)
        rafRef.current = null
      }
    }
  }, [status, levelRef])

  const toggle = useCallback(async () => {
    if (status === 'recording') {
      stop()
    } else if (status === 'idle' || status === 'error') {
      await start()
    }
  }, [status, start, stop])

  const isDisabled = !sendAudio || status === 'requesting'

  const btnClass = [
    'audio-capture__btn',
    status === 'requesting' && 'audio-capture__btn--requesting',
    status === 'recording' && 'audio-capture__btn--recording',
  ]
    .filter(Boolean)
    .join(' ')

  const label =
    status === 'recording'
      ? t('tapToStop')
      : status === 'requesting'
        ? t('requestingMic')
        : t('tapToSpeak')

  return (
    <div className="audio-capture">
      <div
        className={`audio-capture__visualizer ${status === 'recording' ? 'audio-capture__visualizer--active' : ''}`}
      >
        <canvas ref={canvasRef} width={200} height={8} />
      </div>

      <button
        className={btnClass}
        onClick={toggle}
        disabled={isDisabled}
        aria-label={label}
      >
        {status === 'recording' ? <StopIcon /> : <MicIcon />}
      </button>

      <span className="audio-capture__label">{label}</span>

      {error && (
        <div className="audio-capture__error" role="alert">
          {t(error)}
        </div>
      )}
    </div>
  )
}
