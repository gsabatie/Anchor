const ALLOWED_URL_PREFIXES = [
  'https://storage.googleapis.com/',
  'http://localhost:',
]

import { useTranslation } from 'react-i18next'

function isAllowedUrl(url) {
  return ALLOWED_URL_PREFIXES.some((prefix) => url.startsWith(prefix))
}

export default function ExposureImage({ src }) {
  const { t } = useTranslation()
  if (!src || !isAllowedUrl(src)) return null

  return (
    <div className="exposure-image">
      <img src={src} alt={t('exposureAlt')} />
    </div>
  )
}
