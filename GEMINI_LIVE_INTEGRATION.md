# Gemini Live WebSocket Integration Guide

## Overview

Anchor now integrates **Gemini 2.0 Flash Live API** for real-time, bidirectional audio conversations with ERP support.

## Architecture

```
Client (Audio Input)
    ↓ [PCM/WebM Audio]
WebSocket (/ws/session)
    ↓
FastAPI WebSocket Handler
    ├─ Validates auth token
    ├─ Manages bidirectional streams
    └─ Pipes to Gemini Live API
         ├─ GeminiLiveSession
         ├─ reassurance_guard (blocks unsafe responses)
         ├─ Streams responses back
         └─ Tool execution (ERP Timer, Image Gen, etc)
    ↓ [JSON + Audio Response]
WebSocket Response
    ↓
Client (Audio Output + UI Updates)
```

## Setup

### 1. Environment Variables

Add to your `.env` file:

```bash
# Required
GOOGLE_GENAI_API_KEY=your-google-genai-api-key
WS_AUTH_TOKEN=your-secure-token-here

# Optional (defaults shown)
GEMINI_MODEL=gemini-2.0-flash
VERTEX_LOCATION=europe-west1
IMAGEN_MODEL=imagegeneration@006
```

### 2. Google Cloud Setup

```bash
# Create API key for Gemini Live
gcloud services enable generativelanguage.googleapis.com
gcloud services enable aiplatform.googleapis.com

# Generate API key (if using OAuth-free approach)
# Or use Application Default Credentials
```

### 3. Install Dependencies

Backend dependencies are already in `requirements.txt`:
- `google-genai>=1.11` — Gemini Live client
- `websockets>=14` — WebSocket support
- `fastapi>=0.115` — Web framework
- `uvicorn[standard]>=0.34` — ASGI server

Frontend dependencies are standard React/Vite:
```bash
cd frontend && npm install
```

## How It Works

### Backend Flow

1. **WebSocket Connection**
   - Client connects with auth token
   - Token validated against `WS_AUTH_TOKEN`
   - `GeminiLiveSession` initialized and connected to Gemini Live API

2. **Audio Streaming (Client → Server)**
   - Client captures audio via Web Audio API (16kHz PCM)
   - Sends binary chunks via WebSocket
   - Backend forwards to Gemini Live

3. **Response Streaming (Server → Client)**
   - Gemini Live emits responses (text + audio + tool calls)
   - `reassurance_guard` intercepts and blocks harmful reassurance patterns
   - Responses converted to JSON and sent back to client
   - Audio responses base64-encoded for safe transmission

4. **Tool Execution**
   - Tools (hierarchy_builder, image_generator, erp_timer, etc.) run within Gemini context
   - Results sent back through the session
   - session_tracker saves progress to Firestore

### Frontend Flow

1. **useWebSocket Hook**
   - Establishes WebSocket connection
   - Handles incoming responses (text, audio, images, timers)
   - Maintains conversation transcript

2. **AudioCapture Component**
   - Uses Web Audio API to record user audio
   - Captures at 16kHz (PCM)
   - Streams to backend in real-time

3. **Message Types**
   - `connection` — Initial greeting
   - `text` — Text response from Anchor
   - `audio` — Audio response (base64 encoded WebM/PCM)
   - `exposure_image` — ERP image from Imagen 3
   - `timer` — ERP timer state update
   - `error` — Connection/processing errors

## Response Format

### Text Response
```json
{
  "type": "text",
  "content": "Je t'entends. Respire avec moi...",
  "timestamp": "2026-03-08T10:30:00Z"
}
```

### Audio Response
```json
{
  "type": "audio",
  "data": "base64-encoded-webm-audio",
  "timestamp": "2026-03-08T10:30:00Z"
}
```

### Control Messages (Client → Server)
```json
{
  "type": "control",
  "action": "pause" | "resume" | "end_session"
}
```

## Key Features

### 1. Anti-Reassurance Guard
The `reassurance_guard` tool blocks reassurance patterns like:
- "ça va aller" (it will be fine)
- "t'inquiète pas" (don't worry)
- "c'est propre" (it's clean)
- And replaces with ERP-compliant redirect

### 2. Real-Time Bidirectional Audio
- Client sends raw PCM audio chunks (16kHz)
- Gemini Live processes speech and generates responses
- Responses include both text and synthesized audio

### 3. Tool Integration
- **hierarchy_builder** — Creates ERP exposure hierarchy
- **image_generator** — Generates anxiety-provoking images (Imagen 3)
- **erp_timer** — Manages exposure duration
- **session_tracker** — Saves session to Firestore

### 4. Session Management
- Token-based authentication
- Clean disconnect handling
- Bidirectional task management (receive + send)

## Testing Locally

### Terminal 1 — Backend
```bash
cd backend
source .venv/bin/activate
export GOOGLE_GENAI_API_KEY=your-key
export WS_AUTH_TOKEN=test-token
uvicorn main:app --reload
```

### Terminal 2 — Frontend
```bash
cd frontend
export VITE_WS_AUTH_TOKEN=test-token
npm run dev
```

### In Browser
1. Open http://localhost:5173
2. Click "Commencer une séance"
3. Grant microphone permission
4. Start speaking

## Debugging

### Enable Verbose Logging

```bash
# Backend
export LOG_LEVEL=DEBUG
```

### Check WebSocket Connection

```javascript
// In browser console
const ws = new WebSocket('ws://localhost:8000/ws/session?token=test-token')
ws.onopen = () => console.log('Connected')
ws.onmessage = (e) => console.log('Message:', e.data)
ws.onerror = (e) => console.error('Error:', e)
```

### Monitor Gemini Live

```python
# In backend logs, look for:
# - "Gemini Live session started"
# - "Reassurance pattern blocked"
# - Error logs for API failures
```

## Production Deployment

### Security
- Use strong `WS_AUTH_TOKEN` (32+ chars, random)
- Enable TLS for WebSocket (`wss://`)
- Use Application Default Credentials for GCP auth
- Restrict API key to only required services

### Scaling
- Use Cloud Run with multiple replicas
- Implement rate limiting on `/ws/session`
- Monitor Gemini Live API quota
- Cache hierarchy_builder results per user

### Monitoring
- Log all WebSocket connects/disconnects
- Monitor API latency (Gemini Live)
- Track reassurance guard triggers
- Alert on high error rates

## Common Issues

### "GOOGLE_GENAI_API_KEY not configured"
- Set environment variable before starting backend
- Check format (should be valid Google API key)

### WebSocket disconnects after 30s
- Check backend logs for errors
- Ensure client is sending audio regularly
- Verify `WS_AUTH_TOKEN` matches

### No audio response
- Check browser console for playback errors
- Verify Gemini Live is returning audio
- Check base64 decoding in frontend

### "Reassurance pattern blocked"
- This is intentional! The system is protecting the user from false reassurance
- See `reassurance_guard.py` for patterns

## Next Steps

1. **Integration Testing** — Test full ERP workflow
2. **Finetuning** — Adjust system prompt for your use case
3. **Audio Format** — Switch from PCM to WebM for compression
4. **Monitoring** — Set up observability (logs, traces, metrics)
5. **User Testing** — Get feedback from therapists and patients

## References

- [Gemini Live API Docs](https://ai.google.dev/)
- [Web Audio API](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
- [WebSocket API](https://developer.mozilla.org/en-US/docs/Web/API/WebSocket)
- [ERP Principles](https://ocdla.org/what-is-exposure-and-response-prevention-erp)
