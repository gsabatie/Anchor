import { useState } from 'react'

export default function AnxietyMeter({ onReport }) {
  const [level, setLevel] = useState(5)

  const handleChange = (e) => {
    const value = Number(e.target.value)
    setLevel(value)
    onReport(value)
  }

  return (
    <div className="anxiety-meter">
      <label>Niveau d'anxiété : {level}/10</label>
      <input type="range" min="0" max="10" value={level} onChange={handleChange} />
    </div>
  )
}
