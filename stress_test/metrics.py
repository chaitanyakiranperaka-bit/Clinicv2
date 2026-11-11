import time
import statistics
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field

@dataclass
class TurnMetric:
    turn_index: int
    user_text: str
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

@dataclass
class CallMetric:
    call_id: str
    caller_phone: str
    clinician: str
    started_at: float = field(default_factory=time.time)
    ended_at: Optional[float] = None
    status: str = "IN_PROGRESS"  # SUCCESS, FAILED, TIMEOUT
    error: Optional[str] = None
    greeting_received: bool = False
    booking_created: bool = False
    booking_details: Optional[Dict[str, Any]] = None
    turns: List[TurnMetric] = field(default_factory=list)

    @property
    def duration(self) -> float:
        end = self.ended_at or time.time()
        return max(0.0, end - self.started_at)

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

