from fastapi import APIRouter, WebSocket, WebSocketDisconnect

ws_router = APIRouter()


@ws_router.websocket("/ws/session")
async def session_ws(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            # TODO: pipe audio to Gemini Live API and stream responses back
            await websocket.send_json({"type": "ack"})
    except WebSocketDisconnect:
        pass
