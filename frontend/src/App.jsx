import { useState, useCallback } from 'react'
import { useTranslation } from 'react-i18next'
import AudioCapture from './components/AudioCapture'
import ExposureImage from './components/ExposureImage'
import AnxietyMeter from './components/AnxietyMeter'
import ERPTimer from './components/ERPTimer'
import SessionHistory from './components/SessionHistory'
import { useWebSocket } from './hooks/useWebSocket'
import './App.css'

function App() {
  const { t } = useTranslation()
  const [sessionActive, setSessionActive] = useState(false)
  const token = import.meta.env.VITE_WS_AUTH_TOKEN || ''

  console.log('🚀 App: Token from env:', token ? token.substring(0, 10) + '...' : 'NOT SET')
  const {
    status,
    exposureImage,
    timerData,
    transcript,
    error,
    sendMessage,
    sendControl,
    sendAudio,
    ws
  } = useWebSocket(sessionActive ? token : null)

  const handleStartSession = useCallback(() => {
    setSessionActive(true)
  }, [])

  const handleEndSession = useCallback(() => {
    setSessionActive(false)
    sendControl('end_session')
  }, [sendControl])

  const handleAnxietyReport = useCallback((level) => {
    sendMessage(t('anxietyReport', { level }))
  }, [sendMessage])

  return (
    <div className="app">
      <header>
        <h1>⚓ {t('title')}</h1>
        <p>{t('subtitle')}</p>
        <div className="status-indicator">
          <span className={`status-dot ${status}`}></span>
          <span className="status-text">{status}</span>
        </div>
      </header>

      <main>
        {error && (
          <div className="error-banner">
            {error}
          </div>
        )}

        {!sessionActive ? (
          <button className="start-btn" onClick={handleStartSession}>
            {t('startSession')}
          </button>
        ) : (
          <div className="session">
              <div className="transcript-panel">
                {transcript && transcript.length > 0 ? (
                  transcript.map((msg, idx) => (
                    <div key={idx} className={`message ${msg.role}`}>
                      <span className="role">{msg.role === 'user' ? t('you') : t('anchor')}</span>
                      <p>{msg.content}</p>
                    </div>
                  ))
                ) : (
                  <div className="message assistant">
                    <span className="role">{t('anchor')}</span>
                    <p>{t('connecting')}</p>
                  </div>
                )}
              </div>

              <AudioCapture sendAudio={sendAudio} websocket={ws} />
            <ExposureImage src={exposureImage} />
              <AnxietyMeter onReport={handleAnxietyReport} />
            <ERPTimer data={timerData} />

              <button className="end-btn" onClick={handleEndSession}>
                {t('endSession')}
              </button>
          </div>
        )}

        <SessionHistory />
      </main>
    </div>
  )
}

export default App
