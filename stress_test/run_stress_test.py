#!/usr/bin/env python3
"""CLI Entry Point for Star Clinic Autonomous Voice Receptionist Stress & Load Testing.
Tests concurrency, VAD, Faster-Whisper STT, Bedrock Qwen, Google Calendar, and Kokoro TTS on AWS g5.2xlarge.
"""

import sys
import os
import json
import time
import argparse
import asyncio
import urllib.request
from pathlib import Path

# Add project root and stress_test to sys.path
_cur_dir = Path(__file__).resolve().parent
_root_dir = _cur_dir.parent
sys.path.insert(0, str(_root_dir))
sys.path.insert(0, str(_cur_dir))

from stress_config import SERVER_HOST, SERVER_PORT, WS_URL, STATUS_URL
from load_runner import LoadRunner

def check_server_health(host: str, port: int) -> bool:
    """Verifies that server.py is running and responds to HTTP /status."""
    status_url = f"http://{host}:{port}/status"
    print(f"[PRE-FLIGHT] Checking server status at {status_url}...", flush=True)
    try:
        req = urllib.request.Request(status_url, headers={"User-Agent": "StressTester/1.0"})
        with urllib.request.urlopen(req, timeout=4) as resp:
            if resp.status == 200:
                body = json.loads(resp.read().decode("utf-8"))
                print(f"  ✓ Server is healthy! Calendar: {body.get('calendar_badge')} | Model: {body.get('model_id')}")
                return True
    except Exception as e:
        print(f"  ✗ Could not reach server at {status_url}: {e}")
        print(f"    Please ensure server.py is running: python -m uvicorn server:app --host 0.0.0.0 --port {port}")
        return False
    return False

def save_results_json(summary: dict, hardware: dict, scenario: str, concurrency: int):
    """Saves benchmark results to a timestamped JSON report in stress_test/results/."""
    results_dir = _cur_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    ts = time.strftime("%Y%m%d_%H%M%S")
    filepath = results_dir / f"stress_{scenario}_c{concurrency}_{ts}.json"
    
    payload = {
        "timestamp": ts,
        "scenario": scenario,
        "target_concurrency": concurrency,
        "metrics": summary,
        "hardware": hardware
    }
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)
    print(f"[REPORT SAVED]: {filepath}")

async def main_async():
    parser = argparse.ArgumentParser(description="Voice Receptionist Load & Stress Testing Suite (Google Calendar)")
    parser.add_argument("--mode", choices=["baseline", "burst", "ramp_up", "soak"], default="ramp_up", help="Test scenario mode")
    parser.add_argument("--concurrency", type=int, default=5, help="Target concurrent callers (e.g. 5, 10, 20)")
    parser.add_argument("--duration", type=int, default=60, help="Duration in seconds for soak test mode")
    parser.add_argument("--step", type=int, default=2, help="Concurrency increment step for ramp_up mode")
    parser.add_argument("--step-delay", type=float, default=3.0, help="Delay between steps in ramp_up mode (seconds)")
    parser.add_argument("--host", default=SERVER_HOST, help=f"Server host (default: {SERVER_HOST})")
    parser.add_argument("--port", type=int, default=SERVER_PORT, help=f"Server port (default: {SERVER_PORT})")
    parser.add_argument("--skip-preflight", action="store_true", help="Skip HTTP /status health check")
    args = parser.parse_args()

    # Pre-flight check
    if not args.skip_preflight:
        if not check_server_health(args.host, args.port):
            sys.exit(1)

    ws_url = f"ws://{args.host}:{args.port}/ws/call"
    runner = LoadRunner(ws_url=ws_url)

    print("\n" + "=" * 78)
    print(f" LAUNCHING STRESS TEST SCENARIO: {args.mode.upper()}")
    print(f" Target WebSocket URL:  {ws_url}")
    print(f" Target Concurrency:    {args.concurrency} concurrent callers")
    print(f" Booking System:        Google Calendar (GP & Nurse)")
    print("=" * 78)

    test_start = time.time()

    if args.mode == "baseline":
        await runner.monitor.start()
        print("\n[SCENARIO] Running single baseline benchmark call...")
        await runner.run_single_call()
        await runner.monitor.stop()
        runner.metrics.finish_test()

    elif args.mode == "burst":
        await runner.monitor.start()
        print(f"\n[SCENARIO] Running burst spike with {args.concurrency} simultaneous calls...")
        await runner.run_concurrent_batch(args.concurrency)
        await runner.monitor.stop()
        runner.metrics.finish_test()

    elif args.mode == "ramp_up":
        await runner.run_ramp_up(target_concurrency=args.concurrency, step=args.step, step_delay_sec=args.step_delay)

    elif args.mode == "soak":
        await runner.run_soak_test(concurrency=args.concurrency, duration_sec=args.duration)

    # Print Final Reports
    runner.metrics.print_report()
    runner.monitor.print_summary()

    # Save JSON Report
    save_results_json(
        summary=runner.metrics.get_summary(),
        hardware=runner.monitor.get_summary(),
        scenario=args.mode,
        concurrency=args.concurrency
    )

def main():
    try:
        asyncio.run(main_async())
    except KeyboardInterrupt:
        print("\n[STRESS TEST INTERRUPTED BY USER]")

if __name__ == "__main__":
    main()
