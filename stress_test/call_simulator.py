import json
import time
import asyncio
import urllib.parse
from typing import Dict, Any, Optional

try:
    import websockets
except ImportError:
    websockets = None

from stress_config import (
    WS_URL,
    SAMPLE_RATE,
    FRAME_SIZE,
    FRAME_DURATION_SEC,
    CALL_TIMEOUT_SEC
)
from audio_generator import get_turn_audio_bytes
from metrics import CallMetric, TurnMetric

# 512 float32 samples = 2048 bytes
FRAME_BYTES = FRAME_SIZE * 4

class SimulatedCall:
    """Simulates a stateful caller interacting with the voice receptionist WebSocket."""

    def __init__(
        self,
        call_id: str,
        caller_phone: str,
        script: Dict[str, Any],
        ws_url: str = WS_URL,
        timeout_sec: float = CALL_TIMEOUT_SEC
    ):
        self.call_id = call_id
        self.caller_phone = caller_phone
        self.script = script
        self.ws_url = f"{ws_url}?caller_id={urllib.parse.quote(caller_phone)}"
        self.timeout_sec = timeout_sec
        self.metric = CallMetric(
            call_id=call_id,
            caller_phone=caller_phone,
            clinician=script.get("clinician", "Dr. Yousuf")
        )

    async def run(self) -> CallMetric:
        if websockets is None:
            self.metric.status = "FAILED"
            self.metric.error = "Module 'websockets' is not installed."
            self.metric.ended_at = time.time()
            return self.metric

        try:
            async with asyncio.timeout(self.timeout_sec):
                async with websockets.connect(self.ws_url) as ws:
                    # 1. Wait for Deirdre's greeting
                    await self._wait_for_greeting(ws)
                    self.metric.greeting_received = True

                    # 2. Execute conversational turns from script
                    for turn_data in self.script.get("turns", []):
                        await self._execute_turn(ws, turn_data)

                    # 3. Dynamic Alternative Slot Booking:
                    # If after the initial turns the booking is not yet created, negotiate alternative slots (up to 2 retries under contention)
                    for _ in range(2):
                        if self.metric.booking_created or not self.metric.turns:
                            break
                        last_bot_reply = self.metric.turns[-1].bot_reply_text.lower()
                        if any(k in last_bot_reply for k in ["booked", "available", "open", "prefer", "suit", "another time", "alternatively"]):
                            import re
                            # Strip out phrases stating a slot is unavailable or already taken
                            cleaned = re.sub(r"\b\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)\s+(?:is\s+not\s+available|has\s+already\s+passed|is\s+already\s+booked|is\s+booked|is\s+taken)\b", "", last_bot_reply, flags=re.IGNORECASE)
                            cleaned = re.sub(r"\b(?:the|that|it seems the)\s+\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.)\s+slot\b", "", cleaned, flags=re.IGNORECASE)
                            slots = re.findall(r"\b(\d{1,2}(?::\d{2})?\s*(?:am|pm|a\.m\.|p\.m\.))\b", cleaned, flags=re.IGNORECASE)
                            if slots:
                                chosen_slot = slots[0].strip()
                                alt_text = f"The first slot, {chosen_slot} works for me, please go ahead and book it."
                                safe_slot = re.sub(r"[^a-zA-Z0-9]", "", chosen_slot.lower().replace(".", ""))
                                turn_key = f"alt_slot_{safe_slot}"
                            else:
                                alt_text = "Yes, that alternative time you mentioned works for me, please go ahead and book it."
                                turn_key = "alternative_slot_confirm"

                            alt_turn = {
                                "turn_index": len(self.metric.turns) + 1,
                                "turn_key": turn_key,
                                "text": alt_text,
                                "expected_tool": "book_calendar_slot"
                            }
                            await self._execute_turn(ws, alt_turn)

                    # 4. Graceful Hangup
                    await ws.send(json.dumps({"action": "hangup"}))
                    await asyncio.sleep(0.1)

                    self.metric.status = "SUCCESS"
        except asyncio.TimeoutError:
            self.metric.status = "TIMEOUT"
            self.metric.error = f"Call timed out after {self.timeout_sec}s"
        except Exception as e:
            self.metric.status = "FAILED"
            self.metric.error = str(e)
        finally:
            self.metric.ended_at = time.time()

        return self.metric

    async def _wait_for_greeting(self, ws):
        """Awaits initial bot greeting audio and transcripts, draining all greeting sentences."""
        greeting_audio_count = 0
        deadline = time.time() + 12.0

        while time.time() < deadline:
            try:
                # Wait for greeting packets; subsequent audio chunks have a shorter timeout
                poll_timeout = 3.5 if greeting_audio_count == 0 else 1.5
                raw = await asyncio.wait_for(ws.recv(), timeout=poll_timeout)
                if isinstance(raw, str):
                    data = json.loads(raw)
                    msg_type = data.get("type")
                    if msg_type == "audio":
                        greeting_audio_count += 1
                        # Acknowledge playback of this greeting sentence
                        await ws.send(json.dumps({"action": "playback_finished"}))
                    elif msg_type == "transcript" and data.get("role") == "Deirdre":
                        pass
            except asyncio.TimeoutError:
                # If we received at least one greeting audio chunk and then 1.5s of silence,
                # the greeting is completely finished and drained from the socket buffer.
                if greeting_audio_count > 0:
                    break

        # Brief conversational pause before caller starts speaking
        await asyncio.sleep(0.3)

    async def _execute_turn(self, ws, turn_data: Dict[str, Any]):
        """Streams caller audio and tracks VAD, STT, LLM, GCal, and TTS responses."""
        turn_idx = turn_data["turn_index"]
        text = turn_data["text"]
        turn_key = turn_data.get("turn_key") or f"{self.script['id']}_t{turn_idx}"

        turn_metric = TurnMetric(
            turn_index=turn_idx,
            user_text=text
        )
        self.metric.turns.append(turn_metric)

        # Get audio bytes (16kHz float32 PCM with trailing silence)
        audio_bytes = get_turn_audio_bytes(text, turn_key)
        total_samples = len(audio_bytes) // 4
        turn_metric.speech_duration_sec = total_samples / SAMPLE_RATE

        # Stream audio frames in real time
        pos = 0
        while pos < len(audio_bytes):
            chunk = audio_bytes[pos : pos + FRAME_BYTES]
            if len(chunk) < FRAME_BYTES:
                chunk = chunk + b"\x00" * (FRAME_BYTES - len(chunk))
            
            # Send raw float32 PCM frame bytes
            await ws.send(chunk)
            pos += FRAME_BYTES
            await asyncio.sleep(FRAME_DURATION_SEC * 0.95)

        turn_metric.speech_ended_at = time.time()

        # Listen for Deirdre's response events
        await self._receive_turn_response(ws, turn_metric)

    async def _receive_turn_response(self, ws, turn_metric: TurnMetric):
        """Collects server response packets for the current turn."""
        turn_timeout = time.time() + 30.0
        last_packet_time = time.time()

        while time.time() < turn_timeout:
            try:
                # Allow generous window between LLM / Tool / TTS packets
                raw = await asyncio.wait_for(ws.recv(), timeout=2.5)
                now = time.time()
                last_packet_time = now

                if isinstance(raw, str):
                    data = json.loads(raw)
                    msg_type = data.get("type")

                    if msg_type == "vad_state":
                        if not data.get("speaking") and not turn_metric.vad_detected_at:
                            turn_metric.vad_detected_at = now

                    elif msg_type == "tool_start":
                        turn_metric.tool_name = data.get("tool")
                        turn_metric.tool_started_at = now

                    elif msg_type == "tool_log":
                        turn_metric.tool_finished_at = now

                    elif msg_type == "booking_created":
                        self.metric.booking_created = True
                        self.metric.booking_details = data.get("booking")

                    elif msg_type == "transcript":
                        role = data.get("role")
                        if role == "Deirdre":
                            if not turn_metric.first_transcript_at:
                                turn_metric.first_transcript_at = now
                            turn_metric.bot_reply_text += " " + data.get("text", "")
                        elif role == "Patient":
                            turn_metric.user_text = data.get("text", "")

                    elif msg_type == "audio":
                        if not turn_metric.first_audio_at:
                            turn_metric.first_audio_at = now
                        turn_metric.audio_packets_received += 1
                        turn_metric.total_audio_bytes_received += len(data.get("b64", ""))
                        # Inform server that this audio chunk finished playing
                        await ws.send(json.dumps({"action": "playback_finished"}))

            except asyncio.TimeoutError:
                # If bot audio has been received, and 1.5s of silence has passed, turn is complete
                if turn_metric.first_audio_at and (time.time() - last_packet_time >= 1.5):
                    break

        turn_metric.turn_completed_at = time.time()
        # Final playback_finished confirmation
        await ws.send(json.dumps({"action": "playback_finished"}))
        await asyncio.sleep(0.3)
