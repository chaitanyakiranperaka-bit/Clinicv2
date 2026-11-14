import os
import time
import shutil
import asyncio
import subprocess
from typing import Dict, Any, List, Optional, Tuple

try:
    import psutil
except ImportError:
    psutil = None

class SystemMonitor:
    """Asynchronous background resource monitor tracking CPU, RAM, and NVIDIA A10G GPU."""

    def __init__(self, sample_interval_sec: float = 1.0):
        self.interval = sample_interval_sec
        self.is_running = False
        self._task: Optional[asyncio.Task] = None
        self.has_nvidia_smi = bool(shutil.which("nvidia-smi"))

        self.cpu_samples: List[float] = []
        self.ram_samples: List[float] = []
        self.gpu_util_samples: List[float] = []
        self.gpu_mem_samples: List[float] = []
        self.gpu_temp_samples: List[float] = []

        # Zero-dependency Linux /proc state tracking
        self._prev_idle: Optional[float] = None
        self._prev_total: Optional[float] = None
        self._linux_total_ram_gb: Optional[float] = None

    async def start(self):
        self.is_running = True
        # Seed CPU metrics before sampling loop begins
        if psutil:
            try:
                psutil.cpu_percent(interval=None)
            except Exception:
                pass
        else:
            self._prev_idle, self._prev_total = self._read_proc_stat()
            self._read_proc_mem()

        self._task = asyncio.create_task(self._sample_loop())

    async def stop(self):
        self.is_running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _sample_loop(self):
        while self.is_running:
            try:
                # 1. CPU & RAM
                cpu, ram = self._get_cpu_ram()
                if cpu is not None:
                    self.cpu_samples.append(cpu)
                if ram is not None:
                    self.ram_samples.append(ram)

                # 2. NVIDIA GPU stats via nvidia-smi
                if self.has_nvidia_smi:
                    gpu_util, gpu_mem, gpu_temp = self._get_gpu_stats()
                    if gpu_util is not None:
                        self.gpu_util_samples.append(gpu_util)
                    if gpu_mem is not None:
                        self.gpu_mem_samples.append(gpu_mem)
                    if gpu_temp is not None:
                        self.gpu_temp_samples.append(gpu_temp)

                await asyncio.sleep(self.interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(self.interval)

    def _read_proc_stat(self) -> Tuple[Optional[float], Optional[float]]:
        """Reads CPU times from Linux /proc/stat."""
        try:
            if os.path.exists("/proc/stat"):
                with open("/proc/stat", "r") as f:
                    for line in f:
                        if line.startswith("cpu "):
                            parts = [float(x) for x in line.split()[1:]]
                            idle = parts[3] + (parts[4] if len(parts) > 4 else 0.0)
                            total = sum(parts)
                            return idle, total
        except Exception:
            pass
        return None, None

    def _read_proc_mem(self) -> Optional[float]:
        """Reads RAM usage percent from Linux /proc/meminfo."""
        try:
            if os.path.exists("/proc/meminfo"):
                total_kb = None
                avail_kb = None
                with open("/proc/meminfo", "r") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            total_kb = float(line.split()[1])
                        elif line.startswith("MemAvailable:"):
                            avail_kb = float(line.split()[1])
                if total_kb and avail_kb:
                    used_pct = round(((total_kb - avail_kb) / total_kb) * 100.0, 1)
                    self._linux_total_ram_gb = round(total_kb / (1024 * 1024), 1)
                    return used_pct
        except Exception:
            pass
        return None

    def _get_cpu_ram(self) -> Tuple[Optional[float], Optional[float]]:
        # 1. Primary: Use psutil if installed
        if psutil:
            try:
                cpu = psutil.cpu_percent(interval=None)
                ram = psutil.virtual_memory().percent
                return cpu, ram
            except Exception:
                pass

        # 2. Native Linux /proc fallback (Zero-dependency for Ubuntu EC2)
        idle, total = self._read_proc_stat()
        cpu_pct = None
        if idle is not None and total is not None:
            if self._prev_idle is not None and self._prev_total is not None:
                d_idle = idle - self._prev_idle
                d_total = total - self._prev_total
                if d_total > 0:
                    cpu_pct = round(max(0.0, min(100.0, (1.0 - (d_idle / d_total)) * 100.0)), 1)
            self._prev_idle = idle
            self._prev_total = total

        ram_pct = self._read_proc_mem()
        return cpu_pct, ram_pct

    def _get_gpu_stats(self):
        """Queries nvidia-smi for utilization.gpu, memory.used, and temperature.gpu."""
        try:
            cmd = [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,temperature.gpu",
                "--format=csv,noheader,nounits"
            ]
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=2.0)
            if res.returncode == 0:
                parts = [p.strip() for p in res.stdout.strip().split(",")]
                if len(parts) >= 3:
                    gpu_util = float(parts[0])
                    gpu_mem_mib = float(parts[1])
                    gpu_temp = float(parts[2])
                    return gpu_util, gpu_mem_mib, gpu_temp
        except Exception:
            pass
        return None, None, None

    def get_summary(self) -> Dict[str, Any]:
        def stats(vals):
            if not vals:
                return {"avg": 0.0, "max": 0.0}
            return {"avg": round(sum(vals) / len(vals), 1), "max": round(max(vals), 1)}

        return {
            "has_gpu": self.has_nvidia_smi,
            "cpu": stats(self.cpu_samples),
            "ram": stats(self.ram_samples),
            "gpu_util_pct": stats(self.gpu_util_samples),
            "gpu_mem_mib": stats(self.gpu_mem_samples),
            "gpu_temp_c": stats(self.gpu_temp_samples),
            "samples_collected": len(self.cpu_samples)
        }

    def print_summary(self):
        s = self.get_summary()
        vcpus = (psutil.cpu_count(logical=True) if psutil else None) or os.cpu_count() or 4
        if psutil:
            try:
                ram_gb = round(psutil.virtual_memory().total / (1024**3))
            except Exception:
                ram_gb = round(self._linux_total_ram_gb) if self._linux_total_ram_gb else 16
        elif self._linux_total_ram_gb:
            ram_gb = round(self._linux_total_ram_gb)
        else:
            ram_gb = 16

        print("-" * 78)
        print(" HARDWARE UTILIZATION PROFILE (AWS EC2):")
        print(f"   • CPU Usage:     Avg {s['cpu']['avg']}%  |  Peak {s['cpu']['max']}% ({vcpus} vCPUs)")
        print(f"   • System RAM:    Avg {s['ram']['avg']}%  |  Peak {s['ram']['max']}% ({ram_gb} GB)")
        if s["has_gpu"]:
            print(f"   • NVIDIA A10G:   Avg {s['gpu_util_pct']['avg']}%  |  Peak {s['gpu_util_pct']['max']}%")
            print(f"   • VRAM Used:     Avg {s['gpu_mem_mib']['avg']} MiB  |  Peak {s['gpu_mem_mib']['max']} MiB / 24,576 MiB")
            print(f"   • GPU Temp:      Avg {s['gpu_temp_c']['avg']}°C  |  Peak {s['gpu_temp_c']['max']}°C")
        else:
            print("   • NVIDIA GPU:    No nvidia-smi detected (Running on CPU/Local host)")
        print("-" * 78)
