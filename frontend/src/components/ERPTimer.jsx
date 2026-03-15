import { useState, useEffect, useRef, useMemo } from 'react'
import { useTranslation } from 'react-i18next'
import './ERPTimer.css'

const PHASE_LABELS = {
  opening: 'timerPhaseOpening',
  rising: 'timerPhaseRising',
  peak: 'timerPhasePeak',
  falling: 'timerPhaseFalling',
  closing: 'timerPhaseClosing',
}

const PHASE_COLORS = {
  opening: '#7DBCA8',
  rising: '#E8B86B',
  peak: '#E8836B',
  falling: '#7DBCA8',
  closing: '#5FA68E',
}

function formatTime(seconds) {
  const m = Math.floor(seconds / 60)
  const s = seconds % 60
  return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
}

function getCurrentPhase(elapsed, duration) {
  const fraction = duration > 0 ? elapsed / duration : 0
  if (fraction < 0.10) return 'opening'
  if (fraction < 0.40) return 'rising'
  if (fraction < 0.70) return 'peak'
  if (fraction < 0.90) return 'falling'
  return 'closing'
}

const RING_RADIUS = 54
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS

export default function ERPTimer({ data }) {
  const { t } = useTranslation()
  const [elapsed, setElapsed] = useState(0)
  const [activeMessage, setActiveMessage] = useState(null)
  const [messageVisible, setMessageVisible] = useState(false)
  const timerIdRef = useRef(null)
  const shownMessagesRef = useRef(new Set())

  const duration = data?.duration_seconds ?? 0
  const schedule = useMemo(() => data?.coaching_schedule ?? [], [data?.coaching_schedule])

  // Reset state when a new timer starts
  useEffect(() => {
    if (!data?.timer_id || data.timer_id === timerIdRef.current) return
    timerIdRef.current = data.timer_id
    shownMessagesRef.current = new Set()
    setElapsed(0)
    setActiveMessage(null)
    setMessageVisible(false)
  }, [data?.timer_id])

  // Tick every second
  useEffect(() => {
    if (!data?.started_at || !duration) return

    const tick = () => {
      const now = Date.now() / 1000
      const secs = Math.floor(now - data.started_at)
      setElapsed(Math.min(secs, duration))
    }

    tick()
    const id = setInterval(tick, 1000)
    return () => clearInterval(id)
  }, [data?.started_at, duration])

  // Show coaching messages at the right time
  useEffect(() => {
    if (!schedule.length) return

    for (const item of schedule) {
      if (
        elapsed >= item.offset_seconds &&
        !shownMessagesRef.current.has(item.offset_seconds)
      ) {
        shownMessagesRef.current.add(item.offset_seconds)
        // Fade out old, then fade in new
        setMessageVisible(false)
        setTimeout(() => {
          setActiveMessage(item)
          setMessageVisible(true)
        }, 300)
      }
    }
  }, [elapsed, schedule])

  if (!data) return null

  const remaining = Math.max(0, duration - elapsed)
  const finished = remaining === 0 && duration > 0
  const progress = duration > 0 ? elapsed / duration : 0
  const strokeOffset = RING_CIRCUMFERENCE * (1 - progress)
  const phase = getCurrentPhase(elapsed, duration)
  const phaseColor = PHASE_COLORS[phase]

  return (
    <div className={`erp-timer ${finished ? 'erp-timer--finished' : ''}`}>
      <div className="erp-timer__header">
        <span className="erp-timer__title">{t('timerTitle')}</span>
        {data.level != null && (
          <span className="erp-timer__level">
            {t('exposureLevel', { level: data.level })}
          </span>
        )}
      </div>

      <div className="erp-timer__ring-container">
        <svg
          className="erp-timer__ring"
          viewBox="0 0 120 120"
          aria-hidden="true"
        >
          <circle
            className="erp-timer__ring-bg"
            cx="60"
            cy="60"
            r={RING_RADIUS}
          />
          <circle
            className="erp-timer__ring-progress"
            cx="60"
            cy="60"
            r={RING_RADIUS}
            style={{
              strokeDasharray: RING_CIRCUMFERENCE,
              strokeDashoffset: strokeOffset,
              stroke: phaseColor,
            }}
          />
        </svg>
        <div className="erp-timer__time">
          <span className="erp-timer__countdown">
            {finished ? t('timerDone') : formatTime(remaining)}
          </span>
          {!finished && (
            <span
              className={`erp-timer__phase${phase === 'peak' ? ' erp-timer__phase--peak' : ''}`}
              style={{ color: phaseColor }}
            >
              {t(PHASE_LABELS[phase])}
            </span>
          )}
        </div>
      </div>

      {activeMessage && (
        <div
          className={`erp-timer__coaching ${messageVisible ? 'visible' : ''}`}
        >
          <p className="erp-timer__coaching-text">
            {activeMessage.message}
          </p>
        </div>
      )}

      <div className="erp-timer__progress-bar">
        <div
          className="erp-timer__progress-fill"
          style={{ width: `${progress * 100}%`, background: phaseColor }}
        />
        {/* Phase markers */}
        <span className="erp-timer__marker" style={{ left: '10%' }} />
        <span className="erp-timer__marker" style={{ left: '40%' }} />
        <span className="erp-timer__marker" style={{ left: '70%' }} />
        <span className="erp-timer__marker" style={{ left: '90%' }} />
      </div>
    </div>
  )
}
