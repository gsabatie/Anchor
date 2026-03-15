"""Gemini Live WebSocket integration for real-time audio conversations."""

import asyncio
import base64
import logging
import re
from typing import AsyncGenerator

from google import genai
from google.genai import types

from config import GEMINI_LIVE_MODEL as LIVE_MODEL

from agent.prompts.system_prompt import SYSTEM_PROMPT

# Per-tool timeouts (seconds) — calibrated to expected latency
TOOL_TIMEOUTS = {
    "reassurance_guard": 2.0,
    "erp_timer": 2.0,
    "session_tracker": 5.0,
    "hierarchy_builder": 30.0,
    "image_generator": 45.0,
}
from agent.tools.reassurance_guard import reassurance_guard
from agent.tools.crisis_guard import crisis_guard
from agent.tools.hierarchy_builder import hierarchy_builder
from agent.tools.image_generator import image_generator
from agent.tools.erp_timer import erp_timer
from agent.tools.session_tracker import session_tracker

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Transcription cleaning — Gemini native-audio transcription is noisy.
# It often contains <noise> tags, stray non-Latin characters from
# mis-recognition, and very short meaningless fragments.
# ---------------------------------------------------------------------------
_NOISE_TAG_RE = re.compile(r"<[^>]*>")
# Keep Latin, common accented chars, digits, basic punctuation, whitespace
_ALLOWED_CHARS_RE = re.compile(r"[^a-zA-ZÀ-ÿ0-9\s.,;:!?'\-…\"()]+")
_WHITESPACE_RE = re.compile(r"\s+")


def _clean_transcription(text: str) -> str:
    """Clean raw Gemini input transcription for display.

    Removes noise tags, stray non-Latin characters, and collapses whitespace.
    Returns empty string if the cleaned result is too short to be meaningful.
    """
    cleaned = _NOISE_TAG_RE.sub("", text)
    cleaned = _ALLOWED_CHARS_RE.sub(" ", cleaned)
    cleaned = _WHITESPACE_RE.sub(" ", cleaned).strip()
    # Discard fragments shorter than 2 real characters (e.g. "s", " ")
    if len(cleaned) < 2:
        return ""
    return cleaned

# Map tool names to callables
TOOLS = {
    "reassurance_guard": reassurance_guard,
    "hierarchy_builder": hierarchy_builder,
    "image_generator": image_generator,
    "erp_timer": erp_timer,
    "session_tracker": session_tracker,
}

# Tool declarations for Gemini Live (function declarations)
TOOL_DECLARATIONS = [
    types.FunctionDeclaration(
        name="reassurance_guard",
        description="Validate text before speaking it. Call this to check if your planned response contains reassurance patterns that would reinforce OCD compulsions. Always call before delivering a response if you are unsure whether it contains reassurance.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "output_text": types.Schema(type="STRING", description="The text you plan to say, to be checked for reassurance patterns"),
            },
            required=["output_text"],
        ),
    ),
    types.FunctionDeclaration(
        name="hierarchy_builder",
        description=(
            "Build a personalized 10-level ERP exposure hierarchy. "
            "Call this AFTER the intake conversation, once the user has described their OCD "
            "and you have identified both the OCD type and at least one specific trigger. "
            "Do NOT call during intake. Returns existing hierarchy from Firestore if one matches."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "toc_description": types.Schema(type="STRING", description="User's detailed description of their OCD triggers and compulsions"),
                "toc_type": types.Schema(type="STRING", description="Category: contamination, checking, intrusive_thoughts, symmetry, hoarding, or other"),
            },
            required=["toc_description", "toc_type"],
        ),
    ),
    types.FunctionDeclaration(
        name="image_generator",
        description=(
            "Generate an exposure image for a specific hierarchy level using Imagen 3. "
            "Call this at the moment the user agrees to begin a specific exposure level, "
            "BEFORE starting narration. This enables parallel image generation and audio narration. "
            "Continue speaking while the image generates."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "situation": types.Schema(type="STRING", description="Concrete description of the exposure situation from the hierarchy"),
                "level": types.Schema(type="INTEGER", description="Exposure level 1-10"),
                "toc_type": types.Schema(type="STRING", description="Category: contamination, checking, intrusive_thoughts, symmetry, hoarding, or other"),
            },
            required=["situation", "level", "toc_type"],
        ),
    ),
    types.FunctionDeclaration(
        name="erp_timer",
        description=(
            "Start an ERP exposure timer with progressive coaching messages. "
            "Call this ONLY AFTER the exposure image has been shown and the user has given "
            "their first anxiety rating (0-10). Duration depends on level: "
            "levels 1-3 = 10min, 4-6 = 20min, 7-9 = 30min, 10 = 40min."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "level": types.Schema(type="INTEGER", description="Current exposure level 1-10"),
                "duration_minutes": types.Schema(type="INTEGER", description="Timer duration in minutes (10-40)"),
            },
            required=["level", "duration_minutes"],
        ),
    ),
    types.FunctionDeclaration(
        name="session_tracker",
        description=(
            "Manage ERP session lifecycle in Firestore. "
            "Call 'start_session' at the beginning of each session. "
            "Call 'log_level' after each exposure exercise completes (with anxiety_peak and resistance). "
            "Call 'end_session' when the user wants to stop or the session closes naturally. "
            "Call 'get_history' when the user asks about past sessions."
        ),
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "action": types.Schema(type="STRING", description="Action: start_session | log_level | end_session | get_history"),
                "session_data": types.Schema(
                    type="OBJECT",
                    description="Session data payload",
                    properties={
                        "user_id": types.Schema(type="STRING", description="User identifier"),
                        "session_id": types.Schema(type="STRING", description="Session identifier"),
                        "level": types.Schema(type="INTEGER", description="Exposure level"),
                        "anxiety_peak": types.Schema(type="INTEGER", description="Peak anxiety 0-10"),
                        "resistance": types.Schema(type="BOOLEAN", description="Whether the user resisted the compulsion"),
                        "toc_type": types.Schema(type="STRING", description="OCD category"),
                        "toc_description": types.Schema(type="STRING", description="OCD description"),
                    },
                ),
            },
            required=["action", "session_data"],
        ),
    ),
]


class GeminiLiveSession:
    """Manages a Gemini Live audio session for a single WebSocket connection."""

    def __init__(self, gemini_api_key: str | None = None):
        if not gemini_api_key:
            raise ValueError("GOOGLE_GENAI_API_KEY is required")
        # Native audio models require v1alpha; standard models use v1beta
        api_version = "v1alpha" if "native-audio" in LIVE_MODEL else "v1beta"
        self.client = genai.Client(
            api_key=gemini_api_key,
            http_options=types.HttpOptions(api_version=api_version),
        )
        self.session = None
        self._ctx_manager = None  # store the async context manager
        self._connected = False
        self._reconnect_event = asyncio.Event()
        self._reconnect_event.set()  # not reconnecting initially
        self._response_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._receive_task: asyncio.Task | None = None
        self.session_state = {
            "current_phase": "intake",
            "current_level": 0,
            "hierarchy": None,
            "anxiety_readings": [],
            "session_id": None,
        }
        self._image_cache: dict[int, dict] = {}
        logger.info("GeminiLiveSession created: model=%s, api_version=%s", LIVE_MODEL, api_version)

    def _build_config(self) -> dict:
        """Build the LiveConnectConfig for Gemini Live."""
        is_native_audio = "native-audio" in LIVE_MODEL

        config = {
            "response_modalities": ["AUDIO"],
            "speech_config": types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name="Enceladus",
                    )
                )
            ),
            "system_instruction": types.Content(
                parts=[types.Part(text=SYSTEM_PROMPT)]
            ),
            "tools": [types.Tool(function_declarations=TOOL_DECLARATIONS)],
            # VAD: low end-of-speech sensitivity so the model waits for
            # anxious pauses (3-5s) without cutting the user off.
            "realtime_input_config": types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    end_of_speech_sensitivity=types.EndSensitivity.END_SENSITIVITY_LOW,
                ),
            ),
        }

        # Native audio models generate audio directly — transcription
        # gives us the text equivalent for logging and reassurance checking.
        if is_native_audio:
            config["output_audio_transcription"] = types.AudioTranscriptionConfig()
            config["input_audio_transcription"] = types.AudioTranscriptionConfig()

        logger.info(
            "_build_config: modalities=%s, voice=Enceladus, VAD=END_SENSITIVITY_LOW, "
            "native_audio=%s, transcription=%s",
            config["response_modalities"],
            is_native_audio,
            is_native_audio,
        )
        return config

    async def connect(self) -> None:
        """Establish connection to Gemini Live API.

        Tries with full config first, then falls back by stripping
        features that may not be supported by the current model/API version.
        """
        config = self._build_config()
        fallback_keys = ["input_audio_transcription", "realtime_input_config"]

        for attempt in range(len(fallback_keys) + 1):
            try:
                self._ctx_manager = self.client.aio.live.connect(
                    model=LIVE_MODEL,
                    config=config,
                )
                self.session = await self._ctx_manager.__aenter__()
                self._connected = True
                self._receive_task = asyncio.create_task(self._receive_loop())
                logger.info("Gemini Live session connected (attempt %d)", attempt + 1)
                return
            except Exception as e:
                err_msg = str(e)
                if attempt < len(fallback_keys):
                    key = fallback_keys[attempt]
                    if key in config:
                        logger.warning(
                            "Connection failed with %s enabled, retrying without it: %s",
                            key, err_msg,
                        )
                        del config[key]
                        # Clean up failed context manager
                        if self._ctx_manager:
                            try:
                                await self._ctx_manager.__aexit__(None, None, None)
                            except Exception:
                                pass
                            self._ctx_manager = None
                        continue
                logger.error("Failed to connect to Gemini Live: %s", err_msg)
                raise

    async def disconnect(self) -> None:
        """Close Gemini Live session."""
        self._connected = False
        if self._receive_task and not self._receive_task.done():
            self._receive_task.cancel()
            try:
                await self._receive_task
            except asyncio.CancelledError:
                pass
        if self._ctx_manager:
            try:
                await self._ctx_manager.__aexit__(None, None, None)
            except Exception:
                pass
            self._ctx_manager = None
            self.session = None
            logger.info("Gemini Live session closed")

    async def _reconnect(self) -> bool:
        """Attempt to reconnect to Gemini Live after a connection drop.

        Retries up to 3 times with exponential backoff (1s, 2s, 4s).
        On success, re-injects session context so the model knows where we left off.
        """
        max_retries = 3
        for attempt in range(max_retries):
            delay = 2 ** attempt
            logger.info(
                "Reconnecting to Gemini Live (attempt %d/%d) in %ds...",
                attempt + 1, max_retries, delay,
            )
            await asyncio.sleep(delay)

            # Clean up old session
            if self._ctx_manager:
                try:
                    await self._ctx_manager.__aexit__(None, None, None)
                except Exception:
                    pass
                self._ctx_manager = None
                self.session = None

            try:
                config = self._build_config()
                self._ctx_manager = self.client.aio.live.connect(
                    model=LIVE_MODEL,
                    config=config,
                )
                self.session = await self._ctx_manager.__aenter__()
                self._connected = True

                # Re-inject session context so the model picks up where we left off
                context = self._build_context_block()
                await self.session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part(
                            text=f"[RECONNEXION] La session a été interrompue brièvement. {context}"
                        )],
                    ),
                    turn_complete=True,
                )
                logger.info("Gemini Live reconnected on attempt %d", attempt + 1)
                return True
            except Exception as e:
                logger.warning("Reconnection attempt %d failed: %s", attempt + 1, e)

        logger.error("All %d Gemini reconnection attempts failed", max_retries)
        return False

    async def _wait_for_connection(self, timeout: float = 10.0) -> None:
        """Wait for an ongoing reconnection to finish, or raise if not connected."""
        if self._connected and self.session:
            return
        # A reconnection may be in progress — wait for it
        try:
            await asyncio.wait_for(self._reconnect_event.wait(), timeout=timeout)
        except asyncio.TimeoutError:
            pass
        if not self._connected or not self.session:
            raise RuntimeError("Session not connected")

    def _mark_disconnected(self, reason: str) -> None:
        """Mark the session as disconnected so reconnection can proceed."""
        if self._connected:
            logger.warning("Marking Gemini session disconnected: %s", reason)
            self._connected = False

    async def send_audio(self, audio_data: bytes) -> None:
        """Send raw PCM16 audio chunk to Gemini Live.

        Args:
            audio_data: Raw PCM16 audio bytes at 16kHz mono.
        """
        await self._wait_for_connection()

        try:
            logger.debug("send_audio: chunk_size=%d bytes", len(audio_data))
            await self.session.send_realtime_input(
                media=types.Blob(data=audio_data, mime_type="audio/pcm;rate=16000")
            )
        except Exception as e:
            # Detect dead websocket — mark disconnected so receive_loop can reconnect
            self._mark_disconnected(str(e))
            raise

    async def send_text(self, text: str) -> None:
        """Send a text message to Gemini Live.

        Args:
            text: User text input.
        """
        await self._wait_for_connection()

        try:
            logger.debug("send_text: length=%d chars", len(text))
            await self.session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=text)]),
                turn_complete=True,
            )
        except Exception as e:
            self._mark_disconnected(str(e))
            raise

    async def _receive_loop(self) -> None:
        """Background loop that receives from Gemini and queues processed messages.

        On connection drop, attempts transparent reconnection up to 3 times.
        Senders (send_audio/send_text) block on _reconnect_event during reconnection.
        """
        while True:
            try:
                async for response in self.session.receive():
                    try:
                        messages = await self._process_response(response)
                        for msg in messages:
                            await self._response_queue.put(msg)
                    except Exception as e:
                        logger.error(f"Error processing response: {e}", exc_info=True)
                # receive() iterator exhausted — this happens after each model
                # turn in the Gemini Live SDK.  Loop back to start a new
                # receive() for the next turn, unless the session was closed.
                if not self._connected or not self.session:
                    logger.info("Gemini Live session closed, exiting receive loop")
                    break
                logger.debug("Gemini Live receive() ended for current turn, restarting")
                continue
            except asyncio.CancelledError:
                logger.debug("Receive loop cancelled")
                return
            except Exception as e:
                logger.error(f"Gemini Live connection dropped: {e}")
                self._connected = False
                self._reconnect_event.clear()  # block senders during reconnection

                await self._response_queue.put({"type": "reconnecting"})

                if await self._reconnect():
                    self._reconnect_event.set()  # unblock senders
                    await self._response_queue.put({"type": "reconnected"})
                    logger.info("Receive loop resuming after reconnection")
                    continue  # restart the receive loop with new session
                else:
                    self._reconnect_event.set()  # unblock senders so they fail cleanly
                    await self._response_queue.put({
                        "type": "error",
                        "message": "Connexion avec Gemini perdue après plusieurs tentatives.",
                    })
                    return

    async def receive_responses(self) -> AsyncGenerator[dict, None]:
        """Yield processed response messages from the queue."""
        while True:
            # Stay alive if connected, reconnecting, or queue has pending messages
            is_reconnecting = not self._reconnect_event.is_set()
            if not self._connected and not is_reconnecting and self._response_queue.empty():
                break
            try:
                msg = await asyncio.wait_for(self._response_queue.get(), timeout=1.0)
                yield msg
            except asyncio.TimeoutError:
                continue

    async def _process_response(self, response) -> list[dict]:
        """Process a Gemini Live response into client-ready messages.

        Handles: text, audio, tool calls (with execution and response).
        """
        messages = []

        # Handle server content (text + audio + transcription)
        if response.server_content:
            content = response.server_content

            # Handle input audio transcription (what the user said)
            if hasattr(content, "input_transcription") and content.input_transcription:
                raw_text = content.input_transcription.text
                if raw_text:
                    logger.debug("input_transcription received: length=%d chars", len(raw_text))
                    # Crisis guard runs on RAW text (before cleaning)
                    crisis = crisis_guard(raw_text)
                    if crisis["crisis_detected"]:
                        logger.critical("CRISIS DETECTED in user speech: %r", crisis["matched_pattern"])
                        messages.append({
                            "type": "crisis_alert",
                            "redirect": crisis["redirect"],
                            "matched_pattern": crisis["matched_pattern"],
                        })
                    # Clean transcription for display (remove noise, stray chars)
                    clean_text = _clean_transcription(raw_text)
                    if clean_text:
                        messages.append({
                            "type": "user_transcript",
                            "content": clean_text,
                        })

            # Handle output audio transcription (native audio models)
            if hasattr(content, "output_transcription") and content.output_transcription:
                transcript_text = content.output_transcription.text
                if transcript_text:
                    logger.debug("output_transcription received: length=%d chars", len(transcript_text))
                    # Check transcription for reassurance patterns (post-hoc for native audio)
                    guard = reassurance_guard(transcript_text)
                    if not guard["allowed"]:
                        logger.warning(
                            "Reassurance detected in audio transcription: %r",
                            guard["matched_pattern"],
                        )
                        messages.append({
                            "type": "reassurance_violation",
                            "matched_pattern": guard["matched_pattern"],
                            "replacement": guard["replacement"],
                        })
                    messages.append({
                        "type": "transcript_delta",
                        "content": transcript_text,
                    })

            # On turn complete, flush any accumulated transcription
            if getattr(content, "turn_complete", False):
                logger.debug("turn_complete received")
                messages.append({"type": "turn_complete"})

            if getattr(content, "model_turn", None) and content.model_turn.parts:
                for part in content.model_turn.parts:
                    # Skip internal thinking/reasoning parts
                    if getattr(part, "thought", False):
                        continue

                    # Text part (non-thinking)
                    if part.text:
                        text = part.text
                        logger.debug("text part received: length=%d chars", len(text))
                        # Run through reassurance guard
                        guard = reassurance_guard(text)
                        if not guard["allowed"]:
                            text = guard["replacement"]
                            logger.warning("Reassurance pattern blocked")
                        messages.append({
                            "type": "text",
                            "content": text,
                        })

                    # Audio part (inline_data)
                    if part.inline_data and part.inline_data.data:
                        logger.debug(
                            "audio part received: size=%d bytes, mime=%s",
                            len(part.inline_data.data),
                            part.inline_data.mime_type or "audio/pcm;rate=24000",
                        )
                        audio_b64 = base64.b64encode(part.inline_data.data).decode("utf-8")
                        messages.append({
                            "type": "audio",
                            "data": audio_b64,
                            "mime_type": part.inline_data.mime_type or "audio/pcm;rate=24000",
                        })

        # Handle tool calls
        if response.tool_call:
            for fc in response.tool_call.function_calls:
                tool_name = fc.name
                tool_args = dict(fc.args) if fc.args else {}
                logger.debug("tool_call received: name=%s, args=%s", tool_name, tool_args)
                logger.info(f"Tool call: {tool_name}({tool_args})")

                result = await self._execute_tool(tool_name, tool_args)

                # Build a lightweight response for Gemini (strip large blobs)
                gemini_response = {
                    k: v for k, v in result.items()
                    if k not in ("image_base64",)
                }

                # Send tool result back to Gemini
                try:
                    await self.session.send_tool_response(
                        function_responses=[
                            types.FunctionResponse(
                                id=fc.id,
                                name=tool_name,
                                response=gemini_response,
                            )
                        ]
                    )
                except Exception as e:
                    logger.error(f"Error sending tool response: {e}")

                # Forward relevant tool results to the client
                if tool_name == "image_generator" and result.get("image_base64"):
                    messages.append({
                        "type": "exposure_image",
                        "image_base64": result["image_base64"],
                        "prompt_used": result.get("prompt_used", ""),
                        "level": result.get("level"),
                    })
                elif tool_name == "erp_timer":
                    messages.append({
                        "type": "timer",
                        "action": "start",
                        "level": tool_args.get("level"),
                        "duration_minutes": tool_args.get("duration_minutes"),
                        **result,
                    })

        return messages

    def _build_context_block(self) -> str:
        """Return a string summarising current session state for context injection."""
        state = self.session_state
        readings = state["anxiety_readings"]
        return (
            f"\n[SESSION] Phase: {state['current_phase']} | "
            f"Niveau: {state['current_level']}/10 | "
            f"Anxiété récente: {readings[-5:] if readings else 'aucune'}"
        )

    def _get_cached_image(self, level: int) -> dict | None:
        """Return a pre-generated image for the given level, if available."""
        return self._image_cache.get(level)

    async def _pregenerate_images(self, current_level: int) -> None:
        """Pre-generate exposure images for the next 1-2 levels in the background."""
        hierarchy = self.session_state.get("hierarchy")
        if not hierarchy:
            return

        for next_level_data in hierarchy:
            target_level = next_level_data.get("level", 0)
            if target_level <= current_level or target_level > current_level + 2:
                continue
            if target_level in self._image_cache:
                continue

            situation = next_level_data.get("situation", "")
            toc_type = self.session_state.get("toc_type", "")
            if not situation:
                continue

            logger.debug(
                "_pregenerate_images: starting background generation for level=%d, toc_type=%s",
                target_level,
                toc_type,
            )
            try:
                loop = asyncio.get_running_loop()
                result = await asyncio.wait_for(
                    loop.run_in_executor(
                        None,
                        lambda s=situation, l=target_level, t=toc_type: image_generator(
                            situation=s, level=l, toc_type=t
                        ),
                    ),
                    timeout=45.0,
                )
                if "error" not in result:
                    self._image_cache[target_level] = result
                    logger.info("Pre-generated image for level %d", target_level)
            except Exception as exc:
                logger.warning("Pre-generation failed for level %d: %s", target_level, exc)

    async def _execute_tool(self, tool_name: str, args: dict) -> dict:
        """Execute an ADK tool by name with a timeout.

        Args:
            tool_name: Tool function name.
            args: Tool arguments.

        Returns:
            Tool result dict.
        """
        logger.info("_execute_tool: name=%s, args=%s", tool_name, args)
        tool_fn = TOOLS.get(tool_name)
        if not tool_fn:
            logger.error(f"Unknown tool: {tool_name}")
            return {"error": f"Unknown tool: {tool_name}"}

        # Use cached image if available (from pre-generation)
        if tool_name == "image_generator":
            level = args.get("level", 0)
            cached = self._image_cache.pop(level, None)
            if cached:
                logger.info("Using pre-generated image for level %d", level)
                result = cached
                # Update state and return — skip the executor call
                self.session_state["current_phase"] = "exposure"
                self.session_state["current_level"] = level
                return result

        timeout = TOOL_TIMEOUTS.get(tool_name, 15.0)
        try:
            # Tools are sync functions, run in executor to avoid blocking.
            loop = asyncio.get_running_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: tool_fn(**args)),
                timeout=timeout,
            )
            logger.info(f"Tool {tool_name} completed")
        except asyncio.TimeoutError:
            logger.error(f"Tool {tool_name} timed out after {timeout}s")
            return {"error": f"Tool {tool_name} timed out"}
        except Exception as e:
            logger.error(f"Tool {tool_name} failed: {e}")
            return {"error": str(e)}

        # --- Update session state based on tool results ---
        previous_phase = self.session_state["current_phase"]
        phase_changed = False

        if "error" not in result:
            if tool_name == "hierarchy_builder":
                self.session_state["hierarchy"] = result.get("levels")
                self.session_state["current_phase"] = "hierarchy"
                self.session_state["toc_type"] = args.get("toc_type", "")
            elif tool_name == "image_generator":
                self.session_state["current_phase"] = "exposure"
                self.session_state["current_level"] = args.get("level", 0)
                # Pre-generate next levels in background
                asyncio.create_task(self._pregenerate_images(args.get("level", 0)))
            elif tool_name == "erp_timer":
                self.session_state["current_phase"] = "timer"
            elif tool_name == "session_tracker":
                action = args.get("action")
                if action == "start_session" and result.get("session_id"):
                    self.session_state["session_id"] = result["session_id"]
                elif action == "end_session":
                    self.session_state["current_phase"] = "closing"

            phase_changed = self.session_state["current_phase"] != previous_phase

        # Inject updated context into the conversation when the phase changes
        if phase_changed:
            logger.info(
                "Phase change: %s -> %s (level=%d)",
                previous_phase,
                self.session_state["current_phase"],
                self.session_state["current_level"],
            )
            try:
                await self.session.send_client_content(
                    turns=types.Content(
                        role="user",
                        parts=[types.Part(text=self._build_context_block())]
                    ),
                    turn_complete=False,
                )
            except Exception as e:
                logger.warning("Failed to inject session context: %s", e)

        return result
