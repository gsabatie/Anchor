import asyncio
import json
import logging
import os
import threading
import time
from collections import defaultdict

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, status

from services.gemini_live import GeminiLiveSession

logger = logging.getLogger(__name__)

ws_router = APIRouter()

MAX_AUDIO_CHUNK_SIZE = 256 * 1024  # 256 KB per message

# ---------------------------------------------------------------------------
# Per-IP connection limiting
# ---------------------------------------------------------------------------
_active_connections: dict[str, int] = defaultdict(int)
_connections_lock = threading.Lock()
MAX_CONNECTIONS_PER_IP = 2

# ---------------------------------------------------------------------------
# Audio chunk rate limiting
# ---------------------------------------------------------------------------
AUDIO_RATE_LIMIT = 50  # max audio chunks per second per session


def _validate_token(token: str | None) -> bool:
    """Validate the session token."""
    if not token:
        logger.debug("Token validation failed: no token provided")
        return False
    expected = os.getenv("WS_AUTH_TOKEN")
    if not expected:
        logger.warning("WS_AUTH_TOKEN not configured — rejecting all connections")
        return False
    valid = token == expected
    logger.debug("Token validation: %s", "passed" if valid else "failed (token mismatch)")
    return valid


@ws_router.websocket("/ws/session")
async def session_ws(websocket: WebSocket):
    """WebSocket endpoint for real-time audio conversation with Gemini Live."""
    token = websocket.query_params.get("token")
    if not _validate_token(token):
        await websocket.close(code=status.WS_1008_POLICY_VIOLATION)
        return

    client_ip = websocket.client.host if websocket.client else "unknown"
    with _connections_lock:
        if _active_connections[client_ip] >= MAX_CONNECTIONS_PER_IP:
            logger.warning(
                "Connection limit reached for IP %s (%d/%d)",
                client_ip,
                _active_connections[client_ip],
                MAX_CONNECTIONS_PER_IP,
            )
            await websocket.close(code=status.WS_1013_TRY_AGAIN_LATER)
            return
        _active_connections[client_ip] += 1

    logger.info("WebSocket connection accepted from IP=%s", client_ip)
    await websocket.accept()
    gemini_session = None
    keepalive_task = None

    async def _keepalive(ws: WebSocket) -> None:
        """Send a ping every 30 seconds to prevent proxy timeouts."""
        try:
            while True:
                await asyncio.sleep(30)
                logger.debug("Keepalive ping sent to IP=%s", client_ip)
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
            "message": "Bonjour, je suis Anchor. Je suis là avec toi. Comment tu te sens là, maintenant ?",
        })

        # Start keepalive background task
        keepalive_task = asyncio.create_task(_keepalive(websocket))

        # Create tasks for bidirectional communication
        receive_task = asyncio.create_task(
            _receive_from_client(websocket, gemini_session, client_ip)
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
        with _connections_lock:
            _active_connections[client_ip] -= 1
            if _active_connections[client_ip] <= 0:
                del _active_connections[client_ip]
        if keepalive_task is not None:
            keepalive_task.cancel()
            try:
                await keepalive_task
            except asyncio.CancelledError:
                pass
        if gemini_session:
            await gemini_session.disconnect()


async def _receive_from_client(
    websocket: WebSocket, gemini_session: GeminiLiveSession, client_ip: str = "unknown"
) -> None:
    """Receive audio/text from client and forward to Gemini Live."""
    # Sliding-window audio rate limiter — local to this session.
    audio_chunk_times: list[float] = []

    try:
        while True:
            message = await websocket.receive()

            # Binary data = raw PCM16 audio
            if "bytes" in message and message["bytes"]:
                data = message["bytes"]
                if len(data) > MAX_AUDIO_CHUNK_SIZE:
                    logger.warning(
                        "Audio chunk too large from IP=%s: %d bytes (max %d)",
                        client_ip,
                        len(data),
                        MAX_AUDIO_CHUNK_SIZE,
                    )
                    await websocket.send_json({
                        "type": "error",
                        "message": "Audio chunk too large",
                    })
                    continue

                # Sliding-window check: allow at most AUDIO_RATE_LIMIT chunks/s.
                now = time.monotonic()
                audio_chunk_times = [t for t in audio_chunk_times if now - t < 1.0]
                if len(audio_chunk_times) >= AUDIO_RATE_LIMIT:
                    logger.warning(
                        "Audio rate limit exceeded for client %s — dropping chunk",
                        client_ip,
                    )
                    continue
                audio_chunk_times.append(now)

                logger.debug("Received audio chunk: size=%d bytes from IP=%s", len(data), client_ip)
                try:
                    await gemini_session.send_audio(data)
                except RuntimeError as e:
                    logger.error("Gemini session dead, stopping audio forward: %s", e)
                    return
                except Exception as e:
                    # Connection dropped — wait for reconnection before retrying
                    logger.warning("Audio send failed, waiting for reconnection: %s", e)
                    try:
                        await gemini_session._wait_for_connection(timeout=15.0)
                    except RuntimeError:
                        logger.error("Gemini session not recovered, stopping audio forward")
                        return
                    continue

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
                        logger.debug("Received text message: length=%d chars from IP=%s", len(text), client_ip)
                        try:
                            await gemini_session.send_text(text)
                        except RuntimeError as e:
                            logger.error("Gemini session dead, stopping text forward: %s", e)
                            return
                        except Exception as e:
                            logger.warning("Text send failed, waiting for reconnection: %s", e)
                            try:
                                await gemini_session._wait_for_connection(timeout=15.0)
                            except RuntimeError:
                                logger.error("Gemini session not recovered, stopping text forward")
                                return
                            continue

                elif msg_type == "control":
                    action = msg.get("action")
                    logger.debug("Received control message: action=%s from IP=%s", action, client_ip)
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
                msg_type = response.get("type", "unknown")
                if msg_type == "audio":
                    logger.info("-> client: audio b64_len=%d", len(response.get("data", "")))
                elif msg_type == "exposure_image":
                    logger.info("-> client: exposure_image level=%s", response.get("level"))
                else:
                    logger.info("-> client: %s", msg_type)
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
