import { useTranslation } from 'react-i18next'

export default function ERPTimer({ data }) {
  const { t } = useTranslation()
  if (!data) return null

  return (
    <div className="erp-timer">
      <p>{t('timerActive')}</p>
    </div>
  )
}
