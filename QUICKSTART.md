# Gemini Live WebSocket — Quick Start

## 1. Setup Environment

```bash
# Clone and navigate
git clone <repo> && cd anchor

# Copy example env
cp .env.example .env

# Edit .env with your values
# CRITICAL: Add GOOGLE_GENAI_API_KEY
nano .env
```

**Required environment variables:**
```bash
GOOGLE_GENAI_API_KEY=sk-...  # Get from Google AI Studio
WS_AUTH_TOKEN=random-secure-token
ENV=development
```

## 2. Start Backend (Terminal 1)

```bash
cd backend

# Setup Python environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run server
uvicorn main:app --reload --log-level debug
```

Expected output:
```
INFO:     Uvicorn running on http://127.0.0.1:8000
INFO:     Anchor backend initialized (ENV=development)
INFO:     Waiting for application startup.
```

## 3. Start Frontend (Terminal 2)

```bash
cd frontend

# Install dependencies
npm install

# Run dev server
npm run dev
```

Expected output:
```
VITE v... ready in 123 ms

➜  Local:   http://localhost:5173/
```

## 4. Test in Browser

1. Open http://localhost:5173
2. Click "Commencer une séance"
3. Grant microphone access when prompted
4. Start speaking!

**What happens:**
- Audio → Your browser captures it via Web Audio API
- WebSocket → Sent to backend in real-time
- Gemini Live → Backend forwards to Gemini 2.0 Flash
- Response → Gemini responds with text + synthesized audio
- Guard → Reassurance patterns are blocked and redirected
- UI → Transcript updates, audio plays back

## 5. Monitor Backend Logs

```bash
# Watch for these patterns in logs:
- "Gemini Live session started" — Connection successful
- "Reassurance pattern blocked" — Guard is working
- ERROR — Something went wrong

# Enable verbose logging:
export LOG_LEVEL=DEBUG
uvicorn main:app --reload --log-level debug
```

## 6. Test WebSocket Manually

```bash
# In a new terminal, use websocat:
brew install websocat  # macOS

# Connect
websocat "ws://localhost:8000/ws/session?token=$(echo 'test-token' | base64)"

# Send binary audio (Ctrl+C to quit)
# Or for testing, send JSON:
{"type": "control", "action": "pause"}
```

## API Reference

### WebSocket Endpoint

```
ws://localhost:8000/ws/session?token=<WS_AUTH_TOKEN>
```

### Incoming Messages (Server → Client)

**Connection:**
```json
{
  "type": "connection",
  "status": "connected",
  "message": "Anchor is ready. Tell me about your experience."
}
```

**Text Response:**
```json
{
  "type": "text",
  "content": "Je t'entends. Respire avec moi...",
  "timestamp": "2026-03-08T10:30:00Z"
}
```

**Audio Response:**
```json
{
  "type": "audio",
  "data": "base64-encoded-webm-audio",
  "timestamp": "2026-03-08T10:30:00Z"
}
```

**Error:**
```json
{
  "type": "error",
  "message": "Failed to process audio"
}
```

### Outgoing Messages (Client → Server)

**Audio Chunk:**
```
Binary data (PCM or WebM format)
```

**Control Message:**
```json
{
  "type": "control",
  "action": "pause" | "resume" | "end_session"
}
```

## Troubleshooting

### "GOOGLE_GENAI_API_KEY not set"
```bash
# Check if it's set
echo $GOOGLE_GENAI_API_KEY

# Set it
export GOOGLE_GENAI_API_KEY=your-key
```

### WebSocket connects then immediately disconnects
1. Check token matches in `.env`
2. Look at backend logs for errors
3. Verify `WS_AUTH_TOKEN` in browser Network tab

### No audio playback
1. Check browser console for JS errors
2. Verify audio context is created
3. Check speaker volume

### Backend won't start
```bash
# Check Python version
python3 --version  # Should be 3.12+

# Check pip install worked
pip list | grep google-genai

# Try reinstalling
pip install --upgrade -r requirements.txt
```

### Audio keeps disconnecting after 30 seconds
- This might be a timeout issue
- Check `WS_AUTH_TOKEN` length (should be 32+ chars)
- Look at Gemini Live quota in Google Cloud Console

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                     Browser (React + Vite)                   │
│  ┌──────────┐  ┌──────────────┐  ┌─────────────────────────┐│
│  │ AudioCapture│ useWebSocket│  │     Transcript Panel     ││
│  │ (Web Audio)  │ (WebSocket)  │  │ (Conversation History) ││
│  └──────────┘  └──────────────┘  └─────────────────────────┘│
└────────────────────┬────────────────────────────────────────┘
                     │ [Audio PCM + JSON]
                     │ ws://localhost:8000/ws/session
                     ▼
┌─────────────────────────────────────────────────────────────┐
│              FastAPI WebSocket Handler                       │
│  ┌──────────────────────────────────────────────────────┐   │
│  │  Token Validation & Connection Management            │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                    │
│        ┌────────────────┼────────────────┐                   │
│        │                │                │                   │
│   [Receive]         [Process]        [Send]                  │
│   Audio from      Bidirectional      Responses               │
│   Client          Communication      to Client               │
│        │                │                │                   │
│        └────────────────┼────────────────┘                   │
│                         ▼                                    │
│  ┌──────────────────────────────────────────────────────┐   │
│  │            GeminiLiveSession                          │   │
│  │  ┌────────────────────────────────────────────────┐ │   │
│  │  │ send_audio() ←─── Audio Stream ─→ Receive     │ │   │
│  │  │ from Client              Responses from       │ │   │
│  │  │                          Gemini Live API      │ │   │
│  │  └────────────────────────────────────────────────┘ │   │
│  └──────────────────────────────────────────────────────┘   │
│                         │                                    │
│                    [Guard]                                   │
│                    reassurance_guard                         │
│                    (Block harmful text)                      │
│                         │                                    │
└─────────────────────────┼────────────────────────────────────┘
                          │
                          ▼
         ┌─────────────────────────────────┐
         │    Gemini 2.0 Flash Live        │
         │    (Google AI API)              │
         │                                 │
         │  • Audio Processing             │
         │  • Conversation History         │
         │  • Tool Execution               │
         │  • ERP Coaching                 │
         └─────────────────────────────────┘
```

## Next Steps

1. **Test ERP Workflow**
   - Describe your anxiety
   - Get exposure hierarchy
   - Practice exposure with guidance

2. **Check Backend Logs**
   - Look for "Reassurance pattern blocked"
   - Verify tool executions
   - Monitor API latency

3. **Adjust System Prompt**
   - Edit [backend/agent/prompts/system_prompt.py](backend/agent/prompts/system_prompt.py)
   - Customize Anchor's personality
   - Add specific ERP protocols

4. **Deploy to Cloud**
   - See [README.md](README.md) for Cloud Run deployment
   - Use Cloud Build for CI/CD
   - Monitor with Cloud Logging

## Support

- **Issues?** Check logs with `grep -i error backend.log`
- **WebSocket failing?** Test with `websocat` CLI
- **Audio not working?** Check browser permission settings
- **API errors?** Verify Google Cloud quotas

## Documentation

- [Full Integration Guide](GEMINI_LIVE_INTEGRATION.md)
- [README](README.md)
- [Backend Code](backend/)
- [Frontend Code](frontend/)
