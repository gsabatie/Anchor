import { useState } from 'react'
import AudioCapture from './components/AudioCapture'
import ExposureImage from './components/ExposureImage'
import AnxietyMeter from './components/AnxietyMeter'
import ERPTimer from './components/ERPTimer'
import SessionHistory from './components/SessionHistory'
import { useWebSocket } from './hooks/useWebSocket'
import './App.css'

function App() {
  const [sessionActive, setSessionActive] = useState(false)
  const { status, exposureImage, timerData, send } = useWebSocket()

  return (
    <div className="app">
      <header>
        <h1>⚓ Anchor</h1>
        <p>Compagnon ERP</p>
      </header>

      <main>
        {!sessionActive ? (
          <button className="start-btn" onClick={() => setSessionActive(true)}>
            Commencer une séance
          </button>
        ) : (
          <div className="session">
            <AudioCapture onAudioData={send} />
            <ExposureImage src={exposureImage} />
            <AnxietyMeter onReport={(level) => send({ type: 'anxiety', level })} />
            <ERPTimer data={timerData} />
          </div>
        )}

        <SessionHistory />
      </main>
    </div>
  )
}

export default App
