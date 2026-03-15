import asyncio
import json
import logging
import os

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from services.gemini_live import GeminiLiveSession

logger = logging.getLogger(__name__)

ws_router = APIRouter()

MAX_AUDIO_CHUNK_SIZE = 256 * 1024  # 256 KB per message


def _validate_token(token: str | None) -> bool:
    """Validate the session token."""
    if not token:
        return False
    expected = os.getenv("WS_AUTH_TOKEN")
    if not expected:
        logger.warning("WS_AUTH_TOKEN not configured — rejecting all connections")
        return False
    return token == expected


@ws_router.websocket("/ws/session")
async def session_ws(websocket: WebSocket):
    """WebSocket endpoint for real-time audio conversation with Gemini Live."""
    token = websocket.query_params.get("token")
    if not _validate_token(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    await websocket.accept()
    gemini_session = None
    keepalive_task = None

    async def _keepalive(ws: WebSocket) -> None:
        """Send a ping every 30 seconds to prevent proxy timeouts."""
        try:
            while True:
                await asyncio.sleep(30)
                await ws.send_json({"type": "ping"})
        except Exception:
            pass

    try:
        # Initialize and connect Gemini Live session
        gemini_api_key = os.getenv("GOOGLE_GENAI_API_KEY")
        if not gemini_api_key:
            await websocket.send_json({
                "type": "error",
                "message": "GOOGLE_GENAI_API_KEY not configured on server",
            })
            await websocket.close(code=status.WS_1011_INTERNAL_ERROR)
            return
        gemini_session = GeminiLiveSession(gemini_api_key=gemini_api_key)
        await gemini_session.connect()

        # Send initial greeting
        await websocket.send_json({
            "type": "connection",
            "status": "connected",
            "message": "Hi, I'm Anchor. I'm here with you. How are you feeling right now?",
        })

        # Start keepalive background task
        keepalive_task = asyncio.create_task(_keepalive(websocket))

        # Create tasks for bidirectional communication
        receive_task = asyncio.create_task(
            _receive_from_client(websocket, gemini_session)
        )
        send_task = asyncio.create_task(
            _send_to_client(websocket, gemini_session)
        )

        # Wait for either task to complete (error or disconnect)
        done, pending = await asyncio.wait(
            [receive_task, send_task],
            return_when=asyncio.FIRST_EXCEPTION,
        )

        # Re-raise any exceptions from completed tasks
        for task in done:
            if task.exception():
                raise task.exception()

        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

    except WebSocketDisconnect:
        logger.info("Client disconnected from WebSocket")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": str(e)})
        except Exception:
            pass
    finally:
        if keepalive_task is not None:
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass
        if gemini_session:
            await gemini_session.disconnect()


async def _receive_from_client(
    websocket: WebSocket, gemini_session: GeminiLiveSession
) -> None:
    """Receive audio/text from client and forward to Gemini Live."""
    try:
        while True:
            message = await websocket.receive()

            # Binary data = raw PCM16 audio
            if "bytes" in message and message["bytes"]:
                data = message["bytes"]
                if len(data) > MAX_AUDIO_CHUNK_SIZE:
                    await websocket.send_json({
                        "type": "error",
                        "message": "Audio chunk too large",
                    })
                    continue

                try:
                    await gemini_session.send_audio(data)
                except Exception as e:
                    logger.error(f"Error sending audio to Gemini: {e}")

            # Text data = JSON control/text messages
            elif "text" in message and message["text"]:
                try:
                    msg = json.loads(message["text"])
                except json.JSONDecodeError:
                    continue

                msg_type = msg.get("type")

                if msg_type == "text":
                    # Text input from user
                    text = msg.get("content", "")
                    if text:
                        await gemini_session.send_text(text)

                elif msg_type == "control":
                    action = msg.get("action")
                    logger.debug(f"Control message: {action}")
                    # Handle control actions (end_session, pause, etc.)

    except WebSocketDisconnect:
        logger.info("Client disconnected (receive task)")
        raise


async def _send_to_client(
    websocket: WebSocket, gemini_session: GeminiLiveSession
) -> None:
    """Stream responses from Gemini Live back to client."""
    try:
        async for response in gemini_session.receive_responses():
            try:
                await websocket.send_json(response)
            except Exception as e:
                logger.error(f"Error sending to client: {e}")
                raise
    except WebSocketDisconnect:
        logger.info("Client disconnected (send task)")
        raise
    except Exception as e:
        logger.error(f"Error in response stream: {e}")
        raise
