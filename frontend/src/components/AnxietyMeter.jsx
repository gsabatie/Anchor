import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'

const LEVELS = Array.from({ length: 11 }, (_, i) => i)

// Green → Yellow → Orange → Red
function levelColor(level) {
  if (level <= 3) return '#6bcf7f'
  if (level <= 5) return '#ffd93d'
  if (level <= 7) return '#ff9a4d'
  return '#ff5252'
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
