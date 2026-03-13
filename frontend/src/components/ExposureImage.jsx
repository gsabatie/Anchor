import { useState, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'

const ALLOWED_SRC_PREFIXES = [
  'data:image/',
  'https://storage.googleapis.com/',
  'http://localhost:',
]

function isAllowedSrc(src) {
  return ALLOWED_SRC_PREFIXES.some((prefix) => src.startsWith(prefix))
}

export default function ExposureImage({ data }) {
  const { t } = useTranslation()
  const [visible, setVisible] = useState(false)
  const [loaded, setLoaded] = useState(false)
  const prevTimestampRef = useRef(null)

  // Reset animation when a new image arrives
  useEffect(() => {
    if (!data || data.timestamp === prevTimestampRef.current) return
    prevTimestampRef.current = data.timestamp
    setVisible(false)
    setLoaded(false)
  }, [data])

  // Trigger fade-in once the image has loaded
  const handleLoad = () => {
    setLoaded(true)
    // Small delay so the browser paints the opacity:0 frame first
    requestAnimationFrame(() => {
      requestAnimationFrame(() => setVisible(true))
    })
  }

  if (!data?.src || !isAllowedSrc(data.src)) return null

  return (
    <div className="exposure-image">
      <div className="exposure-image__header">
        {data.level != null && (
          <span className="exposure-image__level">
            {t('exposureLevel', { level: data.level })}
          </span>
        )}
      </div>

      <div className="exposure-image__frame">
        {!loaded && (
          <div className="exposure-image__loading">
            <div className="exposure-image__spinner" />
            <span>{t('exposureLoading')}</span>
          </div>
        )}
        <img
          className={`exposure-image__img ${visible ? 'visible' : ''}`}
          src={data.src}
          alt={t('exposureAlt')}
          onLoad={handleLoad}
        />
      </div>
    </div>
  )
}
