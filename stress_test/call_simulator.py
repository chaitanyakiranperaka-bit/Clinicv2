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
        patient_name: str = "Unknown Patient",
        ws_url: str = WS_URL,
        timeout_sec: float = CALL_TIMEOUT_SEC
    ):
        self.call_id = call_id
        self.caller_phone = caller_phone
        self.patient_name = patient_name
        self.script = script
        self.ws_url = f"{ws_url}?caller_id={urllib.parse.quote(caller_phone)}"
        self.timeout_sec = timeout_sec
        self.metric = CallMetric(
            call_id=call_id,
            caller_phone=caller_phone,
            patient_name=patient_name,
            script_id=script.get("id", "script_01"),
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
                async with websockets.connect(self.ws_url, open_timeout=30.0, close_timeout=10.0) as ws:
                    # 1. Wait for Deirdre's greeting
                    await self._wait_for_greeting(ws)
                    self.metric.greeting_received = True

                    # 2. Opening Turn: Caller states their primary booking request
                    initial_turns = self.script.get("turns", [])
                    if initial_turns:
                        await self._execute_turn(ws, initial_turns[0])

                    # 3. Goal-Driven Conversational Loop:
                    # Dynamically converse until booking is created or conversation reaches natural end
                    while not self.metric.booking_created:
                        if not self.metric.turns:
                            break

                        last_reply = self.metric.turns[-1].bot_reply_text.lower().strip()

                        # Exit if booking was already confirmed or receptionist signed off
                        if self.metric.booking_created or "anything else" in last_reply or "booked your appointment" in last_reply:
                            break

                        # Safety guard against infinite loops (max 8 turns per call)
                        if len(self.metric.turns) >= 8:
                            break

                        next_turn = self._determine_next_turn(last_reply)
                        if next_turn:
                            await self._execute_turn(ws, next_turn)
                        else:
                            break

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

    def _determine_next_turn(self, last_reply: str) -> Optional[Dict[str, Any]]:
        """Determines the appropriate natural response based on Deirdre's last utterance."""
        turn_idx = len(self.metric.turns) + 1

        # Case 1: Deirdre says requested day is full and offers alternative days/weeks
        if any(p in last_reply for p in ["no remaining", "fully booked", "no appointment", "check next week", "check monday", "check tuesday", "check wednesday", "check thursday", "check friday", "instead"]):
            return {
                "turn_index": turn_idx,
                "turn_key": "confirm_std",
                "text": "Yes, please book the earliest available slot.",
                "expected_tool": "check_calendar_slots"
            }

        # Case 2: Deirdre reports a conflict (slot was taken by another concurrent caller)
        if any(p in last_reply for p in ["already booked", "just taken", "just booked", "is taken", "try another"]):
            return {
                "turn_index": turn_idx,
                "turn_key": "alternative_slot_confirm",
                "text": "Yes, whichever other time you have available works for me. Please book it.",
                "expected_tool": "book_calendar_slot"
            }

        # Case 3: Deirdre quotes available time slots or asks if a time suits
        if any(p in last_reply for p in ["available", "open", "suit you", "would you like me to book", "would one of those", "prefer", "which time"]):
            return {
                "turn_index": turn_idx,
                "turn_key": "alternative_slot_confirm",
                "text": "Yes, that alternative time you mentioned works for me. Please go ahead and book it.",
                "expected_tool": "book_calendar_slot"
            }

        return None

    async def _wait_for_greeting(self, ws):
        """Awaits initial bot greeting audio and transcripts, draining all greeting sentences."""
        greeting_audio_count = 0
        deadline = time.time() + 12.0
        greeting_text = ""
        first_audio_time = None

        while time.time() < deadline:
            try:
                # Wait for greeting packets; subsequent audio chunks have a shorter timeout
                poll_timeout = 3.5 if greeting_audio_count == 0 else 1.5
                raw = await asyncio.wait_for(ws.recv(), timeout=poll_timeout)
                now = time.time()
                if isinstance(raw, str):
                    data = json.loads(raw)
                    msg_type = data.get("type")
                    if msg_type == "audio":
                        if not first_audio_time:
                            first_audio_time = now
                        greeting_audio_count += 1
                        # Acknowledge playback of this greeting sentence
                        await ws.send(json.dumps({"action": "playback_finished"}))
                    elif msg_type == "transcript" and data.get("role") == "Deirdre":
                        greeting_text += " " + data.get("text", "")
            except asyncio.TimeoutError:
                # If we received at least one greeting audio chunk and then 1.5s of silence,
                # the greeting is completely finished and drained from the socket buffer.
                if greeting_audio_count > 0:
                    break

        self.metric.greeting_text = greeting_text.strip()
        if first_audio_time:
            self.metric.greeting_received_at = first_audio_time
            self.metric.greeting_latency_ms = max(0.0, (first_audio_time - self.metric.started_at) * 1000.0)

        # Brief conversational pause before caller starts speaking
        await asyncio.sleep(0.3)

    async def _execute_turn(self, ws, turn_data: Dict[str, Any]):
        """Streams caller audio and tracks VAD, STT, LLM, GCal, and TTS responses."""
        turn_idx = turn_data["turn_index"]
        text = turn_data["text"]
        turn_key = turn_data.get("turn_key") or f"{self.script['id']}_t{turn_idx}"

        turn_metric = TurnMetric(
            turn_index=turn_idx,
            user_text=text,
            speech_started_at=time.time()
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
        turn_timeout = time.time() + 90.0
        last_packet_time = time.time()

        while time.time() < turn_timeout:
            try:
                # Allow generous window between LLM / Tool / TTS packets
                raw = await asyncio.wait_for(ws.recv(), timeout=4.5)
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
                        turn_metric.tool_input = data.get("input", {})

                    elif msg_type == "tool_result":
                        turn_metric.tool_finished_at = now
                        t_name = data.get("tool") or turn_metric.tool_name
                        t_in = data.get("input") or turn_metric.tool_input or {}
                        t_res = data.get("result", {})
                        dur = round((now - (turn_metric.tool_started_at or now)) * 1000.0, 1)
                        turn_metric.tool_calls.append({
                            "tool": t_name,
                            "input": t_in,
                            "result": t_res,
                            "duration_ms": dur
                        })

                    elif msg_type == "tool_log":
                        if not turn_metric.tool_finished_at:
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
