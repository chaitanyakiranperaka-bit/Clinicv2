#!/usr/bin/env python3
"""
live_monitor.py - Real-Time AWS EC2 Hardware & Bedrock Utilization Monitor

Monitors and displays live statistics for:
  • Bedrock LLM Runtime (Model ID, Region, API Round-Trip Ping, Server Status)
  • HARDWARE UTILIZATION PROFILE (AWS EC2):
      - CPU Usage (Current %, Average, Peak, vCPUs count, Visual Bar)
      - System RAM (Used / Total GB, %, Peak, Visual Bar)
      - NVIDIA A10G (Compute Util %, Average, Peak, Visual Bar)
      - VRAM Used (Used / Total MiB, %, Peak, Visual Bar)
      - GPU Temp (Current °C, Average, Peak)

Usage:
    python live_monitor.py
    python live_monitor.py --interval 1.0 --server http://127.0.0.1:8998
"""

import os
import sys
import time
import shutil
import argparse
import subprocess
import threading
import urllib.request
import json
from typing import Optional, Dict, Any, List

# Try loading psutil
try:
    import psutil
except ImportError:
    psutil = None

# Try loading boto3 for live Bedrock round-trip ping
try:
    import boto3
    from botocore.config import Config
    HAS_BOTO3 = True
except ImportError:
    HAS_BOTO3 = False

# Try importing from local config
try:
    from config import AWS_REGION, BEDROCK_MODEL_ID, GOOGLE_CALENDAR_ID
except ImportError:
    AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")
    BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "qwen.qwen3-coder-30b-a3b-v1:0")
    GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "chaitanyakiran.peraka@gmail.com")


def progress_bar(pct: float, width: int = 15) -> str:
    """Renders a clean Unicode bar graph [████░░░░░░]."""
    clamped = max(0.0, min(100.0, pct))
    filled = int(round((clamped / 100.0) * width))
    empty = width - filled
    return f"[{'█' * filled}{'░' * empty}]"


class LiveMonitor:
    def __init__(self, interval: float = 1.0, server_url: str = "http://127.0.0.1:8998", test_bedrock_ping: bool = True):
        self.interval = interval
        self.server_url = server_url.rstrip("/")
        self.test_bedrock_ping = test_bedrock_ping
        self.running = True

        # Hardware tracking samples
        self.cpu_samples: List[float] = []
        self.ram_samples: List[float] = []
        self.gpu_util_samples: List[float] = []
        self.vram_samples: List[float] = []
        self.gpu_temp_samples: List[float] = []

        # NVIDIA GPU metadata
        self.has_nvidia = bool(shutil.which("nvidia-smi"))
        self.gpu_name = "NVIDIA A10G"
        self.vram_total_mib = 24576.0

        # Server & Bedrock live state
        self.server_status = "Connecting..."
        self.calendar_badge = "Checking..."
        self.bedrock_ping_ms: Optional[float] = None
        self.bedrock_status = "Initializing..."
        self.bedrock_client = None

        if HAS_BOTO3 and self.test_bedrock_ping:
            try:
                boto_cfg = Config(connect_timeout=3, read_timeout=5, retries={"max_attempts": 0})
                self.bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=boto_cfg)
            except Exception as e:
                self.bedrock_status = f"Client Init Error: {e}"

        # Background ping thread to keep UI fast & non-blocking
        self.ping_thread = threading.Thread(target=self._background_ping_loop, daemon=True)
        self.ping_thread.start()

    def _background_ping_loop(self):
        """Asynchronously checks local server health and Bedrock converse latency."""
        while self.running:
            # 1. Local Server Status Check
            try:
                req = urllib.request.Request(f"{self.server_url}/status", headers={"User-Agent": "LiveMonitor"})
                with urllib.request.urlopen(req, timeout=2.0) as resp:
                    if resp.status == 200:
                        data = json.loads(resp.read().decode())
                        self.server_status = "🟢 Online (Port 8998)"
                        self.calendar_badge = data.get("calendar_badge", "Active")
                    else:
                        self.server_status = f"🟡 HTTP {resp.status}"
            except Exception:
                self.server_status = "⚪ Server Offline (127.0.0.1:8998)"
                self.calendar_badge = "N/A"

            # 2. Bedrock Round-Trip Latency Ping
            if self.bedrock_client and self.test_bedrock_ping:
                try:
                    t0 = time.time()
                    self.bedrock_client.converse(
                        modelId=BEDROCK_MODEL_ID,
                        messages=[{"role": "user", "content": [{"text": "hi"}]}],
                        inferenceConfig={"maxTokens": 1, "temperature": 0.0}
                    )
                    latency = (time.time() - t0) * 1000.0
                    self.bedrock_ping_ms = latency
                    self.bedrock_status = f"🟢 Connected ({latency:.0f}ms round-trip)"
                except Exception as e:
                    err_msg = str(e)
                    if "AccessDenied" in err_msg:
                        self.bedrock_status = "🔴 Access Denied (Check AWS Credentials)"
                    elif "ResourceNotFound" in err_msg:
                        self.bedrock_status = "🔴 Model Not Found / Invalid Region"
                    else:
                        short_err = err_msg.split("\n")[0][:40]
                        self.bedrock_status = f"🟡 Delay / Error: {short_err}"
            elif not HAS_BOTO3:
                self.bedrock_status = "⚪ boto3 not installed (Cannot ping)"
            else:
                self.bedrock_status = "⚪ Ping disabled"

            # Sleep between background network pings (every 5 seconds)
            time.sleep(5.0)

    def _get_cpu_ram(self):
        """Reads CPU and RAM percentages."""
        if psutil:
            try:
                cpu = psutil.cpu_percent(interval=None)
                vm = psutil.virtual_memory()
                used_gb = vm.used / (1024 ** 3)
                total_gb = vm.total / (1024 ** 3)
                ram_pct = vm.percent
                return cpu, used_gb, total_gb, ram_pct
            except Exception:
                pass

        # Fallback for Linux procfs
        try:
            mem_total = 16.0
            mem_free = 12.0
            if os.path.exists("/proc/meminfo"):
                with open("/proc/meminfo") as f:
                    lines = f.readlines()
                info = {}
                for l in lines:
                    parts = l.split(":")
                    if len(parts) == 2:
                        info[parts[0].strip()] = float(parts[1].split()[0])
                total_kb = info.get("MemTotal", 16 * 1024 * 1024)
                avail_kb = info.get("MemAvailable", info.get("MemFree", 8 * 1024 * 1024))
                total_gb = total_kb / (1024 * 1024)
                used_gb = (total_kb - avail_kb) / (1024 * 1024)
                ram_pct = (used_gb / total_gb) * 100.0
                return 15.0, used_gb, total_gb, ram_pct
        except Exception:
            pass

        return 0.0, 4.0, 16.0, 25.0

    def _get_gpu_stats(self):
        """Queries nvidia-smi for real-time GPU utilization, VRAM usage, and temp."""
        if not self.has_nvidia:
            return None

        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=name,utilization.gpu,memory.used,memory.total,temperature.gpu",
                "--format=csv,noheader,nounits"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=1.5)
            if res.returncode == 0:
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 5:
                    self.gpu_name = parts[0]
                    gpu_util = float(parts[1])
                    vram_used = float(parts[2])
                    vram_total = float(parts[3])
                    gpu_temp = float(parts[4])
                    self.vram_total_mib = vram_total
                    return {
                        "name": self.gpu_name,
                        "util_pct": gpu_util,
                        "vram_used_mib": vram_used,
                        "vram_total_mib": vram_total,
                        "vram_pct": (vram_used / max(1.0, vram_total)) * 100.0,
                        "temp_c": gpu_temp
                    }
        except Exception:
            pass
        return None

    def render(self):
        """Builds and prints the live terminal dashboard."""
        cpu, ram_used_gb, ram_total_gb, ram_pct = self._get_cpu_ram()
        self.cpu_samples.append(cpu)
        self.ram_samples.append(ram_pct)

        gpu_stats = self._get_gpu_stats()
        if gpu_stats:
            self.gpu_util_samples.append(gpu_stats["util_pct"])
            self.vram_samples.append(gpu_stats["vram_used_mib"])
            self.gpu_temp_samples.append(gpu_stats["temp_c"])

        # Compute rolling aggregates
        def avg(l): return sum(l) / len(l) if l else 0.0
        def peak(l): return max(l) if l else 0.0

        cpu_avg = avg(self.cpu_samples)
        cpu_peak = peak(self.cpu_samples)

        ram_avg = avg(self.ram_samples)
        ram_peak = peak(self.ram_samples)

        vcpus = psutil.cpu_count(logical=True) if psutil else 4

        # ANSI clear screen & cursor home
        lines = []
        lines.append("\033[H\033[J")
        lines.append("==============================================================================")
        lines.append("           LIVE AWS EC2 & BEDROCK HARDWARE UTILIZATION MONITOR")
        lines.append("==============================================================================")
        lines.append(" BEDROCK RUNTIME & SERVICES:")
        lines.append(f"   • Model ID:       {BEDROCK_MODEL_ID} ({AWS_REGION})")
        lines.append(f"   • Bedrock API:    {self.bedrock_status}")
        lines.append(f"   • Voice Server:   {self.server_status}")
        lines.append(f"   • Booking GCal:   {self.calendar_badge}")
        lines.append("")
        lines.append(" HARDWARE UTILIZATION PROFILE (AWS EC2):")

        # CPU
        cpu_bar = progress_bar(cpu, 14)
        lines.append(
            f"   • CPU Usage:     {cpu:5.1f}%  |  Avg {cpu_avg:5.1f}%  |  Peak {cpu_peak:5.1f}% ({vcpus} vCPUs)  {cpu_bar}"
        )

        # RAM
        ram_bar = progress_bar(ram_pct, 14)
        lines.append(
            f"   • System RAM:    {ram_used_gb:4.2f} / {ram_total_gb:4.2f} GB ({ram_pct:4.1f}%)  |  Peak {ram_peak:4.1f}%     {ram_bar}"
        )

        # GPU / NVIDIA A10G
        if gpu_stats:
            gpu_u = gpu_stats["util_pct"]
            gpu_bar = progress_bar(gpu_u, 14)
            gpu_avg = avg(self.gpu_util_samples)
            gpu_peak = peak(self.gpu_util_samples)
            lines.append(
                f"   • {self.gpu_name:13s}:  {gpu_u:5.1f}%  |  Avg {gpu_avg:5.1f}%  |  Peak {gpu_peak:5.1f}%           {gpu_bar}"
            )

            # VRAM
            v_used = gpu_stats["vram_used_mib"]
            v_tot = gpu_stats["vram_total_mib"]
            v_pct = gpu_stats["vram_pct"]
            vram_bar = progress_bar(v_pct, 14)
            v_peak = peak(self.vram_samples)
            lines.append(
                f"   • VRAM Used:     {v_used:6.0f} / {v_tot:6.0f} MiB ({v_pct:4.1f}%)  |  Peak {v_peak:6.0f} MiB {vram_bar}"
            )

            # GPU Temp
            g_temp = gpu_stats["temp_c"]
            t_avg = avg(self.gpu_temp_samples)
            t_max = peak(self.gpu_temp_samples)
            lines.append(
                f"   • GPU Temp:      {g_temp:4.0f}°C  |  Avg {t_avg:4.1f}°C  |  Max {t_max:4.0f}°C"
            )
        else:
            lines.append(
                "   • NVIDIA GPU:    ⚪ No nvidia-smi detected (Host is running on CPU / Mac local)"
            )
            lines.append(
                "   • VRAM Used:     N/A (GPU acceleration disabled on this host)"
            )
            lines.append(
                "   • GPU Temp:      N/A"
            )

        lines.append("==============================================================================")
        lines.append(f" Samples: {len(self.cpu_samples)}  |  Refresh Interval: {self.interval}s  |  Press Ctrl+C to Stop")
        lines.append("==============================================================================")

        sys.stdout.write("\n".join(lines) + "\n")
        sys.stdout.flush()

    def run(self):
        try:
            while self.running:
                self.render()
                time.sleep(self.interval)
        except KeyboardInterrupt:
            self.running = False
            self.print_final_summary()

    def print_final_summary(self):
        def avg(l): return sum(l) / len(l) if l else 0.0
        def peak(l): return max(l) if l else 0.0
        print("\n\n" + "=" * 78)
        print("                   FINAL HARDWARE UTILIZATION SUMMARY")
        print("=" * 78)
        print(f"   • Total Samples: {len(self.cpu_samples)}")
        print(f"   • CPU Usage:     Avg {avg(self.cpu_samples):.1f}%  |  Peak {peak(self.cpu_samples):.1f}%")
        print(f"   • System RAM:    Avg {avg(self.ram_samples):.1f}%  |  Peak {peak(self.ram_samples):.1f}%")
        if self.gpu_util_samples:
            print(f"   • {self.gpu_name}:   Avg {avg(self.gpu_util_samples):.1f}%  |  Peak {peak(self.gpu_util_samples):.1f}%")
            print(f"   • VRAM Used:     Avg {avg(self.vram_samples):.0f} MiB  |  Peak {peak(self.vram_samples):.0f} MiB")
            print(f"   • GPU Temp:      Avg {avg(self.gpu_temp_samples):.1f}°C  |  Max {peak(self.gpu_temp_samples):.0f}°C")
        print("=" * 78 + "\n")


def main():
    parser = argparse.ArgumentParser(description="Live AWS EC2 Hardware & Bedrock Utilization Monitor")
    parser.add_argument("--interval", "-i", type=float, default=1.0, help="Refresh interval in seconds (default: 1.0)")
    parser.add_argument("--server", "-s", type=str, default="http://127.0.0.1:8998", help="Voice server base URL")
    parser.add_argument("--no-ping-bedrock", action="store_true", help="Disable background Bedrock round-trip ping")
    args = parser.parse_args()

    monitor = LiveMonitor(
        interval=args.interval,
        server_url=args.server,
        test_bedrock_ping=not args.no_ping_bedrock
    )
    monitor.run()


if __name__ == "__main__":
    main()
