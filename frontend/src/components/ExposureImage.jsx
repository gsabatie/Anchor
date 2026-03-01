export default function ExposureImage({ src }) {
  if (!src) return null

  return (
    <div className="exposure-image">
      <img src={src} alt="Scène d'exposition" />
    </div>
  )
}
