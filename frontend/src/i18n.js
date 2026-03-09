import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'

i18n.use(initReactI18next).init({
  lng: 'en',
  resources: {
    en: {
      translation: {
        title: 'Anchor',
        subtitle: 'ERP Companion',
        startSession: 'Start a session',
        endSession: 'End session',
        connecting: 'Connecting...',
        you: 'You',
        anchor: 'Anchor',
        anxietyLevel: 'Anxiety level: {{level}}/10',
        anxietyReport: 'My anxiety level is at {{level}}/10',
        timerActive: 'ERP Timer active',
        stopRecording: 'Stop',
        startRecording: 'Speak',
        exposureAlt: 'Exposure scene',
      },
    },
  },
  interpolation: {
    escapeValue: false,
  },
})

export default i18n
