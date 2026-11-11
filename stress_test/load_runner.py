import time
import asyncio
import random
from typing import List, Dict, Any, Optional

from stress_config import (
    WS_URL,
    SIMULATED_CALLERS,
    TEST_SCRIPTS,
    DEFAULT_CONCURRENCY,
    DEFAULT_DURATION_SEC,
    RAMP_UP_DELAY_SEC
)
from call_simulator import SimulatedCall
from metrics import MetricsCollector, CallMetric
from system_monitor import SystemMonitor

class LoadRunner:
    """Orchestrates concurrent caller simulation across various load testing scenarios."""

    def __init__(self, ws_url: str = WS_URL):
        self.ws_url = ws_url
        self.metrics = MetricsCollector()
        self.monitor = SystemMonitor(sample_interval_sec=1.0)
        self._call_counter = 0

    def _get_next_caller(self) -> Dict[str, Any]:
        self._call_counter += 1
        caller = SIMULATED_CALLERS[(self._call_counter - 1) % len(SIMULATED_CALLERS)]
        # Add index to phone to ensure unique session per caller
        phone = f"{caller['phone'][:-2]}{self._call_counter % 100:02d}"
        script = random.choice(TEST_SCRIPTS)
        return {
            "call_id": f"call-{self._call_counter:03d}",
            "phone": phone,
            "script": script
        }

    async def run_single_call(self) -> CallMetric:
        """Executes a single benchmark call to verify basic end-to-end connectivity."""
        caller = self._get_next_caller()
        sim = SimulatedCall(
            call_id=caller["call_id"],
            caller_phone=caller["phone"],
            script=caller["script"],
            ws_url=self.ws_url
        )
        metric = await sim.run()
        self.metrics.add_call(metric)
        return metric

    async def run_concurrent_batch(self, concurrency: int) -> List[CallMetric]:
        """Launches a concurrent batch of N calls simultaneously."""
        print(f"\n[LOAD RUNNER] Launching burst batch of {concurrency} concurrent calls...", flush=True)
        tasks = []
        for _ in range(concurrency):
            caller = self._get_next_caller()
            sim = SimulatedCall(
                call_id=caller["call_id"],
                caller_phone=caller["phone"],
                script=caller["script"],
                ws_url=self.ws_url
            )
            tasks.append(asyncio.create_task(sim.run()))

        results = await asyncio.gather(*tasks, return_exceptions=True)
        completed = []
        for r in results:
            if isinstance(r, CallMetric):
                self.metrics.add_call(r)
                completed.append(r)
            else:
                # Exception raised
                err_metric = CallMetric(call_id="err", caller_phone="N/A", clinician="Unknown", status="FAILED", error=str(r))
                self.metrics.add_call(err_metric)
                completed.append(err_metric)
        return completed

    async def run_ramp_up(self, target_concurrency: int = 10, step: int = 2, step_delay_sec: float = 3.0):
        """Ramps up concurrency gradually to identify degradation inflection point."""
        print(f"\n[LOAD RUNNER] Starting Concurrency Ramp-Up to {target_concurrency} calls (Step: +{step} every {step_delay_sec}s)...", flush=True)
        await self.monitor.start()

        active_tasks = []
        current_concurrency = 0

        while current_concurrency < target_concurrency:
            batch_size = min(step, target_concurrency - current_concurrency)
            for _ in range(batch_size):
                caller = self._get_next_caller()
                sim = SimulatedCall(
                    call_id=caller["call_id"],
                    caller_phone=caller["phone"],
                    script=caller["script"],
                    ws_url=self.ws_url
                )
                t = asyncio.create_task(sim.run())
                active_tasks.append(t)
                current_concurrency += 1

            print(f"  • Ramp: Concurrency active = {current_concurrency} calls", flush=True)
            await asyncio.sleep(step_delay_sec)

        # Wait for all calls to conclude
        results = await asyncio.gather(*active_tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, CallMetric):
                self.metrics.add_call(r)

        await self.monitor.stop()
        self.metrics.finish_test()

    async def run_soak_test(self, concurrency: int = 5, duration_sec: int = 60):
        """Maintains continuous concurrent load for a set duration to detect memory/VRAM leaks."""
        print(f"\n[LOAD RUNNER] Starting Soak Test: {concurrency} persistent concurrent calls for {duration_sec}s...", flush=True)
        await self.monitor.start()

        deadline = time.time() + duration_sec
        active_tasks = set()

        def spawn_call():
            caller = self._get_next_caller()
            sim = SimulatedCall(
                call_id=caller["call_id"],
                caller_phone=caller["phone"],
                script=caller["script"],
                ws_url=self.ws_url
            )
            return asyncio.create_task(sim.run())

        # Seed initial pool
        for _ in range(concurrency):
            active_tasks.add(spawn_call())

        while time.time() < deadline and active_tasks:
            done, active_tasks = await asyncio.wait(active_tasks, return_when=asyncio.FIRST_COMPLETED, timeout=1.0)
            for d in done:
                res = d.result()
                if isinstance(res, CallMetric):
                    self.metrics.add_call(res)
                # If still before deadline, spawn replacement call to maintain concurrency
                if time.time() < deadline:
                    active_tasks.add(spawn_call())

        # Drain remaining calls
        if active_tasks:
            results = await asyncio.gather(*active_tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, CallMetric):
                    self.metrics.add_call(r)

        await self.monitor.stop()
        self.metrics.finish_test()

