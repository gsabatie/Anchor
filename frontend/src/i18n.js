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
        exposureLevel: 'Level {{level}}/10',
        exposureLoading: 'Generating exposure image...',
        tapToSpeak: 'Tap to speak',
        tapToStop: 'Tap to stop',
        requestingMic: 'Requesting microphone...',
        micPermissionDenied: 'Microphone access denied. Please allow mic access in browser settings.',
        micNotFound: 'No microphone found. Please connect a microphone.',
        micError: 'Microphone error. Please try again.',
      },
    },
  },
  interpolation: {
    escapeValue: false,
  },
})

export default i18n
