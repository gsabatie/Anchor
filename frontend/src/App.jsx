import { useState, useCallback } from 'react'
import AudioCapture from './components/AudioCapture'
import ExposureImage from './components/ExposureImage'
import AnxietyMeter from './components/AnxietyMeter'
import ERPTimer from './components/ERPTimer'
import SessionHistory from './components/SessionHistory'
import { useWebSocket } from './hooks/useWebSocket'
import './App.css'

function App() {
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
    sendMessage(`Mon niveau d'anxiété est à ${level}/10`)
  }, [sendMessage])

  return (
    <div className="app">
      <header>
        <h1>⚓ Anchor</h1>
        <p>Compagnon ERP</p>
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
            Commencer une séance
          </button>
        ) : (
          <div className="session">
              <div className="transcript-panel">
                {transcript && transcript.length > 0 ? (
                  transcript.map((msg, idx) => (
                    <div key={idx} className={`message ${msg.role}`}>
                      <span className="role">{msg.role === 'user' ? 'Vous' : 'Anchor'}</span>
                      <p>{msg.content}</p>
                    </div>
                  ))
                ) : (
                  <div className="message assistant">
                    <span className="role">Anchor</span>
                    <p>Connexion en cours...</p>
                  </div>
                )}
              </div>

              <AudioCapture sendAudio={sendAudio} websocket={ws} />
            <ExposureImage src={exposureImage} />
              <AnxietyMeter onReport={handleAnxietyReport} />
            <ERPTimer data={timerData} />

              <button className="end-btn" onClick={handleEndSession}>
                Terminer la séance
              </button>
          </div>
        )}

        <SessionHistory />
      </main>
    </div>
  )
}

export default App
