"""Gemini Live WebSocket integration for real-time audio conversations."""

import asyncio
import base64
import logging
from typing import AsyncGenerator

from google import genai
from google.genai import types

from config import GEMINI_LIVE_MODEL as LIVE_MODEL

from agent.prompts.system_prompt import SYSTEM_PROMPT
from agent.tools.reassurance_guard import reassurance_guard
from agent.tools.hierarchy_builder import hierarchy_builder
from agent.tools.image_generator import image_generator
from agent.tools.erp_timer import erp_timer
from agent.tools.session_tracker import session_tracker

logger = logging.getLogger(__name__)

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
        description="Build a personalized ERP exposure hierarchy (10 levels) based on the user's OCD description.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "toc_description": types.Schema(type="STRING", description="User's description of their OCD"),
                "toc_type": types.Schema(type="STRING", description="Category of OCD (e.g. contamination, checking, intrusive thoughts)"),
            },
            required=["toc_description", "toc_type"],
        ),
    ),
    types.FunctionDeclaration(
        name="image_generator",
        description="Generate an exposure image for a specific hierarchy level using Imagen 3.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "situation": types.Schema(type="STRING", description="Description of the exposure situation"),
                "level": types.Schema(type="INTEGER", description="Exposure level 1-10"),
                "toc_type": types.Schema(type="STRING", description="Category of OCD"),
            },
            required=["situation", "level", "toc_type"],
        ),
    ),
    types.FunctionDeclaration(
        name="erp_timer",
        description="Start an ERP exposure timer for coaching the user through anxiety.",
        parameters=types.Schema(
            type="OBJECT",
            properties={
                "level": types.Schema(type="INTEGER", description="Current exposure level"),
                "duration_minutes": types.Schema(type="INTEGER", description="Timer duration in minutes"),
            },
            required=["level", "duration_minutes"],
        ),
    ),
    types.FunctionDeclaration(
        name="session_tracker",
        description="Track session data in Firestore (start, log level, end, get history).",
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
        self._response_queue: asyncio.Queue[dict] = asyncio.Queue()
        self._receive_task: asyncio.Task | None = None
        self.session_state = {
            "current_phase": "intake",
            "current_level": 0,
            "hierarchy": None,
            "anxiety_readings": [],
            "session_id": None,
        }

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
        }

        # Native audio models generate audio directly — transcription
        # gives us the text equivalent. Non-native models (e.g. gemini-2.0-flash)
        # already emit text parts alongside TTS audio.
        if is_native_audio:
            config["output_audio_transcription"] = types.AudioTranscriptionConfig()

        return config

    async def connect(self) -> None:
        """Establish connection to Gemini Live API."""
        try:
            config = self._build_config()
            # Store the context manager so we can __aexit__ it later
            self._ctx_manager = self.client.aio.live.connect(
                model=LIVE_MODEL,
                config=config,
            )
            self.session = await self._ctx_manager.__aenter__()
            self._connected = True
            # Start background task to receive responses
            self._receive_task = asyncio.create_task(self._receive_loop())
            logger.info("Gemini Live session connected")
        except Exception as e:
            logger.error(f"Failed to connect to Gemini Live: {e}")
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

    async def send_audio(self, audio_data: bytes) -> None:
        """Send raw PCM16 audio chunk to Gemini Live.

        Args:
            audio_data: Raw PCM16 audio bytes at 16kHz mono.
        """
        if not self.session or not self._connected:
            raise RuntimeError("Session not connected")

        try:
            await self.session.send_realtime_input(
                media=types.Blob(data=audio_data, mime_type="audio/pcm;rate=16000")
            )
        except Exception as e:
            logger.error(f"Error sending audio to Gemini Live: {e}")
            raise

    async def send_text(self, text: str) -> None:
        """Send a text message to Gemini Live.

        Args:
            text: User text input.
        """
        if not self.session or not self._connected:
            raise RuntimeError("Session not connected")

        try:
            await self.session.send_client_content(
                turns=types.Content(role="user", parts=[types.Part(text=text)]),
                turn_complete=True,
            )
        except Exception as e:
            logger.error(f"Error sending text to Gemini Live: {e}")
            raise

    async def _receive_loop(self) -> None:
        """Background loop that receives from Gemini and queues processed messages."""
        try:
            async for response in self.session.receive():
                try:
                    messages = await self._process_response(response)
                    for msg in messages:
                        await self._response_queue.put(msg)
                except Exception as e:
                    logger.error(f"Error processing response: {e}", exc_info=True)
        except asyncio.CancelledError:
            logger.debug("Receive loop cancelled")
        except Exception as e:
            logger.error(f"Error in receive loop: {e}")
            self._connected = False
            await self._response_queue.put({"type": "error", "message": str(e)})

    async def receive_responses(self) -> AsyncGenerator[dict, None]:
        """Yield processed response messages from the queue."""
        while self._connected or not self._response_queue.empty():
            try:
                msg = await asyncio.wait_for(self._response_queue.get(), timeout=1.0)
                yield msg
            except asyncio.TimeoutError:
                if not self._connected and self._response_queue.empty():
                    break
                continue

    async def _process_response(self, response) -> list[dict]:
        """Process a Gemini Live response into client-ready messages.

        Handles: text, audio, tool calls (with execution and response).
        """
        messages = []

        # Handle server content (text + audio + transcription)
        if response.server_content:
            content = response.server_content

            # Handle output audio transcription (native audio models)
            if hasattr(content, "output_transcription") and content.output_transcription:
                transcript_text = content.output_transcription.text
                if transcript_text:
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
            if content.turn_complete:
                messages.append({"type": "turn_complete"})

            if content.model_turn and content.model_turn.parts:
                for part in content.model_turn.parts:
                    # Skip internal thinking/reasoning parts
                    if getattr(part, "thought", False):
                        continue

                    # Text part (non-thinking)
                    if part.text:
                        text = part.text
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

    async def _execute_tool(self, tool_name: str, args: dict) -> dict:
        """Execute an ADK tool by name with a timeout.

        Args:
            tool_name: Tool function name.
            args: Tool arguments.

        Returns:
            Tool result dict.
        """
        tool_fn = TOOLS.get(tool_name)
        if not tool_fn:
            logger.error(f"Unknown tool: {tool_name}")
            return {"error": f"Unknown tool: {tool_name}"}

        try:
            # Tools are sync functions, run in executor to avoid blocking.
            # Timeout prevents the Gemini connection from dropping while
            # waiting for slow external services (Vertex AI, Firestore).
            loop = asyncio.get_event_loop()
            result = await asyncio.wait_for(
                loop.run_in_executor(None, lambda: tool_fn(**args)),
                timeout=15.0,
            )
            logger.info(f"Tool {tool_name} completed")
        except asyncio.TimeoutError:
            logger.error(f"Tool {tool_name} timed out after 15s")
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
            elif tool_name == "image_generator":
                self.session_state["current_phase"] = "exposure"
                self.session_state["current_level"] = args.get("level", 0)
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
