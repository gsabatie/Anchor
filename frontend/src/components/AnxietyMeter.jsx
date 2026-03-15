import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'

const LEVELS = Array.from({ length: 11 }, (_, i) => i)

// Fond Marin palette: calm sea green → seagrass → warm sand → coral peak
function levelColor(level) {
  if (level <= 3) return '#7DBCA8'
  if (level <= 5) return '#A8C98F'
  if (level <= 7) return '#E8B86B'
  return '#E8836B'
}

export default function AnxietyMeter({ onReport }) {
  const { t } = useTranslation()
  const [level, setLevel] = useState(5)
  const [confirmed, setConfirmed] = useState(false)

  const handleChange = (e) => {
    setLevel(Number(e.target.value))
    setConfirmed(false)
  }

  const handleConfirm = useCallback(() => {
    setConfirmed(true)
    onReport(level)
  }, [level, onReport])

  const color = levelColor(level)

  return (
    <div className="anxiety-meter">
      <div className="anxiety-meter__header">
        <span className="anxiety-meter__label">{t('anxietyLevel', { level })}</span>
        <span className="anxiety-meter__value" style={{ color }}>
          {level}
        </span>
      </div>

      <div className="anxiety-meter__track-wrapper">
        <input
          className="anxiety-meter__slider"
          type="range"
          min="0"
          max="10"
          step="1"
          value={level}
          onChange={handleChange}
          style={{
            '--meter-color': color,
            '--meter-pct': `${level * 10}%`,
          }}
        />
        <div className="anxiety-meter__ticks">
          {LEVELS.map((n) => (
            <span key={n} className="anxiety-meter__tick">{n}</span>
          ))}
        </div>
      </div>

      <button
        className={`anxiety-meter__btn ${confirmed ? 'confirmed' : ''}`}
        onClick={handleConfirm}
        disabled={confirmed}
      >
        {confirmed ? t('anxietyReported') : t('anxietyReport_btn')}
      </button>
    </div>
  )
}
