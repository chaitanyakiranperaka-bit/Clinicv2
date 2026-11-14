import time
import json
import statistics
from pathlib import Path
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class TurnMetric:
    turn_index: int
    user_text: str
    speech_started_at: float = 0.0
    speech_duration_sec: float = 0.0
    speech_ended_at: float = 0.0
    vad_detected_at: Optional[float] = None
    first_transcript_at: Optional[float] = None
    first_audio_at: Optional[float] = None
    turn_completed_at: Optional[float] = None
    tool_name: Optional[str] = None
    tool_started_at: Optional[float] = None
    tool_finished_at: Optional[float] = None
    bot_reply_text: str = ""
    audio_packets_received: int = 0
    total_audio_bytes_received: int = 0

    @property
    def ttfa(self) -> Optional[float]:
        """Time to First Audio: latency from speech finish to first bot audio byte."""
        if self.first_audio_at and self.speech_ended_at:
            return max(0.0, self.first_audio_at - self.speech_ended_at)
        return None

    @property
    def vad_latency(self) -> Optional[float]:
        """Time from speech finish to server VAD silence trigger."""
        if self.vad_detected_at and self.speech_ended_at:
            return max(0.0, self.vad_detected_at - self.speech_ended_at)
        return None

    @property
    def tool_duration(self) -> Optional[float]:
        """Time spent executing external tool (Google Calendar)."""
        if self.tool_finished_at and self.tool_started_at:
            return max(0.0, self.tool_finished_at - self.tool_started_at)
        return None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "turn_index": self.turn_index,
            "user_text": self.user_text,
            "speech_duration_sec": round(self.speech_duration_sec, 3),
            "speech_started_at": round(self.speech_started_at, 3) if self.speech_started_at else None,
            "speech_ended_at": round(self.speech_ended_at, 3) if self.speech_ended_at else None,
            "vad_latency_ms": round(self.vad_latency * 1000.0, 1) if self.vad_latency is not None else None,
            "ttfa_delay_ms": round(self.ttfa * 1000.0, 1) if self.ttfa is not None else None,
            "tool_name": self.tool_name,
            "tool_duration_ms": round(self.tool_duration * 1000.0, 1) if self.tool_duration is not None else None,
            "bot_reply_text": self.bot_reply_text.strip(),
            "audio_packets_received": self.audio_packets_received
        }

@dataclass
class CallMetric:
    call_id: str
    caller_phone: str
    clinician: str
    patient_name: str = "Unknown Patient"
    script_id: str = "script_01"
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    status: str = "IN_PROGRESS"  # SUCCESS, FAILED, TIMEOUT
    error: Optional[str] = None
    greeting_received: bool = False
    greeting_text: str = ""
    greeting_received_at: Optional[float] = None
    greeting_latency_ms: Optional[float] = None
    booking_created: bool = False
    booking_details: Optional[Dict[str, Any]] = None
    turns: List[TurnMetric] = field(default_factory=list)

    @property
    def duration(self) -> float:
        end = self.ended_at or time.time()
        return max(0.0, end - self.started_at)

    def to_transcript_text(self) -> str:
        t0 = self.started_at
        lines = []
        lines.append("=" * 80)
        lines.append(f"                    CALL CONVERSATION AUDIT: {self.call_id}")
        lines.append(f" Caller:     {self.patient_name} ({self.caller_phone})")
        lines.append(f" Clinician:  {self.clinician}")
        lines.append(f" Status:     {self.status}" + (" (🟢 Booking Created)" if self.booking_created else ""))
        lines.append(f" Duration:   {self.duration:.2f}s  (Script: {self.script_id})")
        if self.booking_details:
            b = self.booking_details
            lines.append(f" Booking:    {b.get('clinician')} | {b.get('date')} at {b.get('slot_time', '10:00')}")
        if self.error:
            lines.append(f" Failure:    ⚠️ {self.error}")
        lines.append("=" * 80)
        lines.append(f"[+00.000s] 📞 WebSocket Connected: /ws/call?caller_id={self.caller_phone}")

        # Initial Bot Greeting
        if self.greeting_text:
            lat = f"{self.greeting_latency_ms:.0f}ms" if self.greeting_latency_ms else "N/A"
            greet_rel = (self.greeting_received_at - t0) if self.greeting_received_at else 0.1
            lines.append(f"[+{greet_rel:06.3f}s] 🤖 Deirdre (Initial Greeting):")
            lines.append(f"           \"{self.greeting_text}\"")
            lines.append(f"           (Latency to audio: {lat})")
            lines.append("")

        # Conversational Turns
        for t in self.turns:
            sp_start_rel = (t.speech_started_at - t0) if t.speech_started_at else 0.0
            sp_end_rel = (t.speech_ended_at - t0) if t.speech_ended_at else 0.0

            lines.append(f"[+{sp_start_rel:06.3f}s] 👤 {self.patient_name} (Turn {t.turn_index}):")
            lines.append(f"           \"{t.user_text}\"")
            lines.append(f"           (Speech Duration: {t.speech_duration_sec:.2f}s | Ended: +{sp_end_rel:06.3f}s)")
            lines.append("")

            # Inter-message delay breakdown
            lines.append("           " + "-" * 60)
            lines.append("           ⏱️  TIME DELAY & PROCESSING BREAKDOWN:")
            lines.append(f"              • Caller finished speaking:  +{sp_end_rel:06.3f}s")
            if t.vad_latency is not None:
                lines.append(f"              • VAD Silence Detected:     +{t.vad_latency * 1000.0:0.0f}ms after speech")
            if t.tool_name:
                t_dur = f"{t.tool_duration * 1000.0:0.0f}ms" if t.tool_duration is not None else "In Progress"
                lines.append(f"              • Tool Executed:            {t.tool_name} (Duration: {t_dur})")
            if t.ttfa is not None:
                lines.append(f"              • Inter-Message Delay (TTFA): {t.ttfa * 1000.0:0.0f}ms  <-- Caller waited")
            lines.append("           " + "-" * 60)
            lines.append("")

            # Bot Reply
            bot_rel = (t.first_audio_at - t0) if t.first_audio_at else (sp_end_rel + (t.ttfa or 0.5))
            lines.append(f"[+{bot_rel:06.3f}s] 🤖 Deirdre (Turn {t.turn_index} Response):")
            lines.append(f"           \"{t.bot_reply_text.strip()}\"")
            lines.append(f"           (Audio Packets: {t.audio_packets_received})")
            lines.append("")

        # Final call status
        dur_rel = self.duration
        if self.status == "SUCCESS":
            lines.append(f"[+{dur_rel:06.3f}s] 🏁 Call Completed Successfully (Total Duration: {self.duration:.2f}s)")
        elif self.status == "TIMEOUT":
            lines.append(f"[+{dur_rel:06.3f}s] ⚠️ Call Timed Out After {self.duration:.2f}s: {self.error}")
        else:
            lines.append(f"[+{dur_rel:06.3f}s] ❌ Call Terminated: {self.error}")
        lines.append("=" * 80 + "\n")
        return "\n".join(lines)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "call_id": self.call_id,
            "caller_phone": self.caller_phone,
            "patient_name": self.patient_name,
            "clinician": self.clinician,
            "script_id": self.script_id,
            "status": self.status,
            "error": self.error,
            "duration_sec": round(self.duration, 2),
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "greeting_received": self.greeting_received,
            "greeting_text": self.greeting_text,
            "greeting_latency_ms": round(self.greeting_latency_ms, 1) if self.greeting_latency_ms else None,
            "booking_created": self.booking_created,
            "booking_details": self.booking_details,
            "turns": [t.to_dict() for t in self.turns]
        }

class MetricsCollector:
    """Thread-safe and async-safe collector for stress test results."""

    def __init__(self):
        self.calls: List[CallMetric] = []
        self.test_start_time = time.time()
        self.test_end_time: Optional[float] = None

    def add_call(self, call: CallMetric):
        self.calls.append(call)

    def finish_test(self):
        self.test_end_time = time.time()

    def get_summary(self) -> Dict[str, Any]:
        total_calls = len(self.calls)
        successful = sum(1 for c in self.calls if c.status == "SUCCESS")
        failed = sum(1 for c in self.calls if c.status == "FAILED")
        timed_out = sum(1 for c in self.calls if c.status == "TIMEOUT")
        bookings = sum(1 for c in self.calls if c.booking_created)

        test_duration = (self.test_end_time or time.time()) - self.test_start_time

        ttfa_list = []
        vad_latencies = []
        tool_durations = []

        for c in self.calls:
            for t in c.turns:
                if t.ttfa is not None:
                    ttfa_list.append(t.ttfa)
                if t.vad_latency is not None:
                    vad_latencies.append(t.vad_latency)
                if t.tool_duration is not None:
                    tool_durations.append(t.tool_duration)

        def calc_percentiles(values: List[float]) -> Dict[str, float]:
            if not values:
                return {"mean": 0.0, "min": 0.0, "max": 0.0, "p50": 0.0, "p90": 0.0, "p95": 0.0, "p99": 0.0}
            sorted_v = sorted(values)
            n = len(sorted_v)
            def p(pct):
                idx = min(int(n * pct / 100.0), n - 1)
                return sorted_v[idx]
            return {
                "mean": round(statistics.mean(sorted_v), 3),
                "min": round(sorted_v[0], 3),
                "max": round(sorted_v[-1], 3),
                "p50": round(statistics.median(sorted_v), 3),
                "p90": round(p(90), 3),
                "p95": round(p(95), 3),
                "p99": round(p(99), 3),
            }

        return {
            "test_duration_sec": round(test_duration, 2),
            "total_calls": total_calls,
            "successful_calls": successful,
            "failed_calls": failed,
            "timed_out_calls": timed_out,
            "success_rate_pct": round((successful / total_calls * 100.0), 1) if total_calls > 0 else 0.0,
            "bookings_created": bookings,
            "calls_per_minute": round((total_calls / (test_duration / 60.0)), 1) if test_duration > 0 else 0.0,
            "ttfa_metrics": calc_percentiles(ttfa_list),
            "vad_latency_metrics": calc_percentiles(vad_latencies),
            "tool_duration_metrics": calc_percentiles(tool_durations),
            "total_turns_analyzed": len(ttfa_list)
        }

    def print_report(self):
        s = self.get_summary()
        print("\n" + "=" * 78)
        print("                 VOICE RECEPTIONIST STRESS TEST REPORT")
        print("=" * 78)
        print(f" Test Duration:        {s['test_duration_sec']}s")
        print(f" Total Calls:          {s['total_calls']}")
        print(f" Successful Calls:     {s['successful_calls']} ({s['success_rate_pct']}%)")
        print(f" Failed Calls:         {s['failed_calls']}")
        print(f" Timed Out Calls:      {s['timed_out_calls']}")
        print(f" Google Cal Bookings:  {s['bookings_created']}")
        print(f" Throughput:           {s['calls_per_minute']} calls/min")

        if s["failed_calls"] > 0 or s["timed_out_calls"] > 0:
            print("-" * 78)
            print(" FAILURE REASONS:")
            errors = {}
            for c in self.calls:
                if c.error:
                    errors[c.error] = errors.get(c.error, 0) + 1
            for err, count in errors.items():
                print(f"   • ({count}x) {err}")
        print("-" * 78)

        ttfa = s["ttfa_metrics"]
        print(" LATENCY BREAKDOWN: Time to First Audio (TTFA):")
        print(f"   • Mean: {ttfa['mean']}s  |  Min: {ttfa['min']}s  |  Max: {ttfa['max']}s")
        print(f"   • p50 (Median): {ttfa['p50']}s")
        print(f"   • p90:          {ttfa['p90']}s")
        print(f"   • p95:          {ttfa['p95']}s")
        print(f"   • p99:          {ttfa['p99']}s")

        tool = s["tool_duration_metrics"]
        if tool["max"] > 0:
            print("-" * 78)
            print(" GOOGLE CALENDAR TOOL EXECUTION LATENCY:")
            print(f"   • Mean: {tool['mean']}s  |  p50: {tool['p50']}s  |  p95: {tool['p95']}s  |  Max: {tool['max']}s")

        print("=" * 78 + "\n")

    def export_conversations(self, output_dir: Path):
        """Exports every conversation log with detailed inter-message delays to disk."""
        output_dir = Path(output_dir)
        calls_dir = output_dir / "calls"
        calls_dir.mkdir(parents=True, exist_ok=True)

        combined_lines = []
        combined_lines.append("# STRESS TEST CONVERSATION AUDIT LOG")
        combined_lines.append(f"Total Calls: {len(self.calls)} | Exported: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")

        index_md_rows = []
        index_md_rows.append("# Conversation Audit Index\n")
        index_md_rows.append("| Call ID | Patient Name | Phone | Clinician | Status | Duration | Mean TTFA | Booked |")
        index_md_rows.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")

        for c in self.calls:
            clean_phone = c.caller_phone.replace("+", "").strip()
            clean_name = c.patient_name.replace(" ", "_").strip()
            filename = f"{c.call_id}_{clean_phone}_{clean_name}.txt"

            transcript = c.to_transcript_text()

            # 1. Individual call log
            with open(calls_dir / filename, "w", encoding="utf-8") as f:
                f.write(transcript)

            # 2. Append to combined master log
            combined_lines.append(transcript)

            # 3. Index row
            ttfas = [t.ttfa for t in c.turns if t.ttfa is not None]
            avg_ttfa = f"{statistics.mean(ttfas) * 1000:.0f}ms" if ttfas else "N/A"
            booked_str = "🟢 Yes" if c.booking_created else "⚪ No"
            index_md_rows.append(
                f"| [{c.call_id}](calls/{filename}) | {c.patient_name} | `{c.caller_phone}` | {c.clinician} | **{c.status}** | {c.duration:.1f}s | {avg_ttfa} | {booked_str} |"
            )

        # Write combined transcript
        with open(output_dir / "all_conversations.txt", "w", encoding="utf-8") as f:
            f.write("\n".join(combined_lines))

        # Write Markdown Index
        with open(output_dir / "INDEX.md", "w", encoding="utf-8") as f:
            f.write("\n".join(index_md_rows) + "\n")

        # Write structured JSON
        json_payload = {
            "test_summary": self.get_summary(),
            "calls": [c.to_dict() for c in self.calls]
        }
        with open(output_dir / "conversations.json", "w", encoding="utf-8") as f:
            json.dump(json_payload, f, indent=2)
