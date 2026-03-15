import { useState, useCallback, useEffect, useRef } from 'react'
import { useTranslation } from 'react-i18next'
import AudioCapture from './components/AudioCapture'
import ExposureImage from './components/ExposureImage'
import AnxietyMeter from './components/AnxietyMeter'
import ERPTimer from './components/ERPTimer'
import SessionHistory from './components/SessionHistory'
import { useWebSocket } from './hooks/useWebSocket'
import './App.css'

const STATUS_KEYS = {
  disconnected: 'statusDisconnected',
  connecting: 'statusConnecting',
  connected: 'statusConnected',
  reconnecting: 'statusReconnecting',
}

function App() {
  const { t } = useTranslation()
  const [sessionActive, setSessionActive] = useState(false)
  const [showEndConfirm, setShowEndConfirm] = useState(false)
  const transcriptEndRef = useRef(null)
  const token = import.meta.env.VITE_WS_AUTH_TOKEN || ''

  const {
    status,
    exposureImage,
    timerData,
    transcript,
    error,
    sendMessage,
    sendControl,
    sendAudio,
    isThinking,
    crisisAlert,
    reassuranceViolation,
    ensureAudioResumed,
  } = useWebSocket(sessionActive ? token : null)

  // P4 — Auto-scroll transcript when new messages arrive
  useEffect(() => {
    transcriptEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [transcript, isThinking])

  // P5 — Escape key closes the confirm dialog
  useEffect(() => {
    if (!showEndConfirm) return
    const handleKey = (e) => {
      if (e.key === 'Escape') setShowEndConfirm(false)
    }
    window.addEventListener('keydown', handleKey)
    return () => window.removeEventListener('keydown', handleKey)
  }, [showEndConfirm])

  const handleStartSession = useCallback(() => {
    ensureAudioResumed()
    setSessionActive(true)
  }, [ensureAudioResumed])

  const handleEndSession = useCallback(() => {
    setShowEndConfirm(true)
  }, [])

  const confirmEndSession = useCallback(() => {
    sendControl('end_session')
    setSessionActive(false)
    setShowEndConfirm(false)
  }, [sendControl])

  const cancelEndSession = useCallback(() => {
    setShowEndConfirm(false)
  }, [])

  const handleAnxietyReport = useCallback((level) => {
    sendMessage(t('anxietyReport', { level }))
  }, [sendMessage, t])

  const roleLabel = (role) => {
    if (role === 'user') return t('you')
    if (role === 'system') return t('system')
    return t('anchor')
  }

  return (
    <div className="app">
      <header>
        <h1>{t('title')}</h1>
        <p>{t('subtitle')}</p>
        <div className="status-indicator">
          <span className={`status-dot ${status}`} />
          <span className="status-text">
            {t(STATUS_KEYS[status] || 'statusDisconnected')}
          </span>
        </div>
      </header>

      <main>
        {crisisAlert && (
          <div className="crisis-banner" role="alert" aria-live="assertive">
            <span className="crisis-banner__icon" aria-hidden="true">&#x1F198;</span>
            <p>{crisisAlert.redirect}</p>
          </div>
        )}

        {reassuranceViolation && (
          <div className="reassurance-banner" role="status" aria-live="polite">
            {reassuranceViolation.replacement}
          </div>
        )}

        {error && (
          <div className="error-banner" role="alert" aria-live="assertive">
            {error}
          </div>
        )}

        {!sessionActive ? (
          <div className="welcome">
            <h2 className="welcome__heading">{t('welcomeHeading')}</h2>
            <p className="welcome__body">{t('welcomeBody')}</p>
            <button className="start-btn" onClick={handleStartSession}>
              {t('startSession')}
            </button>
            <p className="welcome__note">{t('welcomeNote')}</p>
          </div>
        ) : (
          <div className="session">
            <ExposureImage data={exposureImage} />
            <ERPTimer data={timerData} />
            <AnxietyMeter onReport={handleAnxietyReport} />
            <AudioCapture sendAudio={sendAudio} />

            <div className="transcript-panel" aria-live="polite">
              {transcript && transcript.length > 0 ? (
                transcript.map((msg, idx) => (
                  <div key={idx} className={`message ${msg.role}`}>
                    <span className="role">{roleLabel(msg.role)}</span>
                    <p>{msg.content}</p>
                  </div>
                ))
              ) : (
                <div className="message assistant">
                  <span className="role">{t('anchor')}</span>
                  <p>{t('connecting')}</p>
                </div>
              )}
              {isThinking && (
                <div className="message assistant thinking">
                  <span className="role">{t('anchor')}</span>
                  <div className="thinking-dots">
                    <span /><span /><span />
                  </div>
                </div>
              )}
              <div ref={transcriptEndRef} />
            </div>

            <button className="end-btn" onClick={handleEndSession}>
              {t('endSession')}
            </button>
          </div>
        )}

        <SessionHistory />
      </main>

      {showEndConfirm && (
        <div className="confirm-overlay" onClick={cancelEndSession}>
          <div
            className="confirm-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="confirm-title"
            onClick={e => e.stopPropagation()}
          >
            <h2 id="confirm-title">{t('endSessionConfirmTitle')}</h2>
            <p>{t('endSessionConfirmBody')}</p>
            <div className="confirm-dialog__actions">
              <button className="confirm-dialog__cancel" onClick={cancelEndSession}>
                {t('endSessionCancel')}
              </button>
              <button className="confirm-dialog__confirm" onClick={confirmEndSession} autoFocus>
                {t('endSessionConfirm')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}

export default App
