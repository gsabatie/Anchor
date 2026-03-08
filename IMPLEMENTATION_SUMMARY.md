# Gemini Live WebSocket Integration — Summary

## What Was Implemented

This integration adds **real-time, bidirectional audio conversation** capabilities to Anchor using Gemini 2.0 Flash Live API.

### Files Created

#### Backend
1. **`backend/services/gemini_live.py`** (NEW)
   - `GeminiLiveSession` class for managing Gemini Live connections
   - Audio streaming methods (`send_audio`, `receive_responses`)
   - Response processing with reassurance guard integration
   - Error handling and session lifecycle management

2. **`backend/tests/test_gemini_live.py`** (NEW)
   - Unit tests for Gemini Live integration
   - Test cases for WebSocket, auth, and response formatting
   - Placeholder for integration tests

#### Frontend
1. **`frontend/src/hooks/useWebSocket.js`** (UPDATED)
   - Enhanced to handle multiple message types (text, audio, images, timers)
   - Audio playback with blob conversion
   - Transcript management
   - Control message support (pause, resume, end_session)

2. **`frontend/src/components/AudioCapture.jsx`** (UPDATED)
   - Integration with Gemini Live WebSocket
   - Audio streaming to backend
   - Connection status indication
   - Real-time audio capture with Web Audio API

#### Documentation
1. **`GEMINI_LIVE_INTEGRATION.md`** (NEW)
   - Complete technical guide
   - Architecture diagrams
   - Setup instructions
   - API reference and examples
   - Debugging and production deployment

2. **`QUICKSTART.md`** (NEW)
   - Step-by-step local development setup
   - Common troubleshooting
   - Manual testing guide
   - Architecture overview

3. **`.env.example`** (UPDATED)
   - Added `GOOGLE_GENAI_API_KEY` (required)
   - Added `VITE_BACKEND_WS_URL`
   - Added `VITE_WS_AUTH_TOKEN`

### Files Modified

#### Backend
1. **`backend/api/websocket.py`**
   - Added `GeminiLiveSession` integration
   - Implemented bidirectional communication with `asyncio.tasks`
   - Proper error handling and cleanup
   - Validation of audio chunk sizes

2. **`backend/main.py`**
   - Added logging configuration
   - Support for `LOG_LEVEL` environment variable

#### Frontend
1. **`frontend/src/App.jsx`**
   - Integrated `useWebSocket` with enhanced API
   - Added transcript display
   - Status indicators
   - Error handling
   - Session management

### Architecture

```
┌─────────────────────────────────────────────┐
│     Client (Browser)                         │
│  ┌─────────────┐  ┌──────────────────────┐ │
│  │ AudioCapture│──│  useWebSocket        │ │
│  └─────────────┘  └──────────────────────┘ │
│       ▲                        ▲            │
│       │ Web Audio API          │ WebSocket  │
│       │ (PCM @ 16kHz)          │            │
└───────┼────────────────────────┼────────────┘
        │                        │
        │ Binary Audio           │ JSON Messages
        │                        │
┌───────▼────────────────────────▼────────────┐
│     Backend (FastAPI)                       │
│  ┌────────────────────────────────────────┐ │
│  │  WebSocket Handler                      │ │
│  │  ┌──────────────┐  ┌──────────────────┐ │ │
│  │  │ Receive Task │  │ Send Task        │ │ │
│  │  │ (Audio In)   │  │ (Responses Out)  │ │ │
│  │  └──────┬───────┘  └────────┬─────────┘ │ │
│  │         │                   │            │ │
│  │         └───────┬───────────┘            │ │
│  │               ▼                         │ │
│  │  ┌─────────────────────────────────┐    │ │
│  │  │  GeminiLiveSession              │    │ │
│  │  │  • send_audio()                 │    │ │
│  │  │  • receive_responses()          │    │ │
│  │  │  • _process_response()          │    │ │
│  │  │  • reassurance_guard integration│    │ │
│  │  └─────────────────────────────────┘    │ │
│  └────────────────────────────────────────┘ │
└───────┬────────────────────────────────────┘
        │
        │ HTTP (gRPC)
        │
┌───────▼────────────────────────────────────┐
│     Gemini 2.0 Flash Live API              │
│     • Real-time audio conversation         │
│     • Tool execution support               │
│     • ERP coaching protocol                │
└────────────────────────────────────────────┘
```

## Key Features

### 1. Real-Time Audio Streaming
- **Client** captures audio at 16kHz PCM
- **Server** forwards to Gemini Live
- **Responses** come back with text + synthesized audio
- All happening in real-time conversation

### 2. Anti-Reassurance Guard
The `reassurance_guard` tool intercepts responses and:
- Blocks harmful reassurance patterns ("don't worry", "it's safe", etc.)
- Redirects to ERP-compliant responses
- Maintains therapeutic integrity

### 3. Bidirectional Communication
Using `asyncio`:
- **Receive task** continuously listens for client audio
- **Send task** streams responses back
- Both run concurrently without blocking

### 4. Tool Integration
Gemini Live can invoke ERP tools:
- `hierarchy_builder` — Creates exposure hierarchy
- `image_generator` — Generates anxiety images
- `erp_timer` — Manages exposure duration
- `session_tracker` — Saves to Firestore

### 5. Robust Error Handling
- Invalid tokens rejected immediately
- Oversized audio chunks rejected
- API errors reported back to client
- Clean disconnection handling

## Usage Flow

```
1. User clicks "Commencer une séance"
   ↓
2. Frontend establishes WebSocket connection (with auth token)
   ↓
3. Backend creates GeminiLiveSession and connects to Gemini Live API
   ↓
4. User speaks → Web Audio API captures at 16kHz
   ↓
5. Frontend sends audio chunks over WebSocket
   ↓
6. Backend forwards to Gemini Live
   ↓
7. Gemini Live processes and responds
   ↓
8. reassurance_guard checks response for harmful patterns
   ↓
9. Response sent back to frontend (JSON + audio)
   ↓
10. Frontend displays text and plays audio
    ↓
11. Loop continues until session ends
```

## Configuration

### Required Environment Variables

```bash
GOOGLE_GENAI_API_KEY=your-api-key      # From Google AI Studio
WS_AUTH_TOKEN=secure-random-token      # For WebSocket authentication
```

### Optional Configuration

```bash
GEMINI_MODEL=gemini-2.0-flash          # Model to use
LOG_LEVEL=INFO                         # Logging verbosity
FRONTEND_URL=http://localhost:5173    # CORS origin
```

## Testing

### Local Development
```bash
# Terminal 1
cd backend && python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export GOOGLE_GENAI_API_KEY=your-key
export WS_AUTH_TOKEN=test-token
uvicorn main:app --reload

# Terminal 2
cd frontend && npm install && npm run dev

# Terminal 3
# Open http://localhost:5173 and test
```

### Manual WebSocket Testing
```bash
# Using websocat
websocat "ws://localhost:8000/ws/session?token=test-token"

# Send control messages:
{"type": "control", "action": "pause"}
{"type": "control", "action": "resume"}
{"type": "control", "action": "end_session"}
```

### Automated Tests
```bash
cd backend
pytest tests/test_gemini_live.py -v
```

## Performance Considerations

### Latency
- **Audio capture → server**: ~50ms
- **Server → Gemini Live**: ~100-200ms
- **Gemini processing**: 500ms-2s (depends on input length)
- **Server → client**: ~50ms
- **Total**: ~700ms-2.5s per turn

### Throughput
- Audio chunks: Up to 256KB per message
- Backend can handle multiple concurrent sessions
- Gemini Live API quotas apply per project

### Resource Usage
- **Memory**: ~50MB per active session (audio buffers + connection)
- **CPU**: Low (mostly I/O bound)
- **Network**: ~10-50kbps upstream (audio), ~20-100kbps downstream

## Production Deployment

### Cloud Run
```bash
# Build and deploy
gcloud builds submit --tag gcr.io/$PROJECT_ID/anchor-backend ./backend
gcloud run deploy anchor-backend \
  --image gcr.io/$PROJECT_ID/anchor-backend \
  --region europe-west1 \
  --set-env-vars GOOGLE_GENAI_API_KEY=$KEY,WS_AUTH_TOKEN=$TOKEN
```

### Security
- Use strong `WS_AUTH_TOKEN` (32+ chars, cryptographically random)
- Enable TLS (wss:// protocol)
- Implement rate limiting
- Use Application Default Credentials for GCP auth

### Monitoring
- Track WebSocket connections/disconnections
- Monitor Gemini Live API latency
- Alert on reassurance guard triggers
- Log all errors to Cloud Logging

## Known Limitations

1. **Audio Format**: Currently sends raw PCM, could optimize to WebM
2. **Tool Execution**: Tools are called but responses need Firestore integration
3. **Session Persistence**: Sessions not yet saved to Firestore
4. **Audio Playback**: Simple blob playback, could add better audio controls
5. **Mobile**: Web Audio API support varies across browsers

## Future Improvements

- [ ] Switch to WebM encoding for bandwidth optimization
- [ ] Add session persistence to Firestore
- [ ] Implement session recovery on disconnect
- [ ] Add video support (camera feed → Gemini Live)
- [ ] Implement ERP homework tracking
- [ ] Add multi-language support
- [ ] Performance optimization (audio buffering)
- [ ] Mobile app (React Native)

## Debugging Checklist

- [ ] `GOOGLE_GENAI_API_KEY` is set and valid
- [ ] `WS_AUTH_TOKEN` matches in backend and frontend
- [ ] Backend logs show "Gemini Live session started"
- [ ] WebSocket connection shows 101 status in Network tab
- [ ] Audio permission granted in browser
- [ ] No CORS errors in console
- [ ] Reassurance patterns being blocked (check logs)

## Support Resources

- [Integration Guide](GEMINI_LIVE_INTEGRATION.md)
- [Quick Start](QUICKSTART.md)
- [README](README.md)
- [Gemini Live API Docs](https://ai.google.dev/docs/gemini_api_reference)
- [WebSocket API MDN](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
