const ALLOWED_URL_PREFIXES = [
  'https://storage.googleapis.com/',
  'http://localhost:',
]

function isAllowedUrl(url) {
  return ALLOWED_URL_PREFIXES.some((prefix) => url.startsWith(prefix))
}

export default function ExposureImage({ src }) {
  if (!src || !isAllowedUrl(src)) return null

  return (
    <div className="exposure-image">
      <img src={src} alt="Scène d'exposition" />
    </div>
  )
}
