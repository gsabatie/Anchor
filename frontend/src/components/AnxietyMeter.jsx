import { useState } from 'react'
import { useTranslation } from 'react-i18next'

export default function AnxietyMeter({ onReport }) {
  const { t } = useTranslation()
  const [level, setLevel] = useState(5)

  const handleChange = (e) => {
    const value = Number(e.target.value)
    setLevel(value)
    onReport(value)
  }

  return (
    <div className="anxiety-meter">
      <label>{t('anxietyLevel', { level })}</label>
      <input type="range" min="0" max="10" value={level} onChange={handleChange} />
    </div>
  )
}
