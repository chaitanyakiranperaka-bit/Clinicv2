# Voice Receptionist Concurrency & Stress Testing Suite

Dedicated load and stress testing framework designed for the **Star Dental & GP Clinic Autonomous Voice Receptionist** deployed on an **AWS EC2 `g5.2xlarge`** instance.

All appointments and slot verifications in this suite operate on **Google Calendar** (Routine GP with `Dr. Yousuf` and Nurse Appointments with `Nurse Kelly`).

---

## 1. AWS EC2 `g5.2xlarge` Architecture & Capacity

| Resource | Specification | Allocation & Expected Load |
| :--- | :--- | :--- |
| **GPU** | 1x NVIDIA A10G (24 GB VRAM) | **Faster-Whisper** (`small.en`, ~1.5 GB) + **Kokoro-82M** (~500 MB). Combined base VRAM is ~2.5 GB, leaving $> 21\text{ GB}$ headroom. |
| **vCPUs** | 8 vCPUs (AMD EPYC) | Dedicated **Silero VAD** instances per active audio stream (512 samples / 32ms frames). |
| **RAM** | 32 GB System Memory | OS, Python runtime buffers, and audio fifos. |
| **LLM Inference** | AWS Bedrock (`eu-west-1`) | Cloud-hosted Qwen (`qwen.qwen3-coder-30b-a3b-v1:0`) executing function calling. |
| **Calendar Backend** | Google Calendar API | Service account syncing events to `GOOGLE_CALENDAR_ID`. |

---

## 2. Directory Structure

```
stress_test/
├── README.md               # THIS GUIDE: Architecture, execution commands, and optimization
├── __init__.py             # Package exports
├── requirements.txt        # Lightweight dependencies for load runner
├── stress_config.py        # Concurrency parameters, timeouts, and caller profiles
├── audio_generator.py      # Real-time 16kHz float32 audio payload generator (VAD + speech)
├── call_simulator.py       # Stateful caller simulation over WebSockets
├── load_runner.py          # Concurrency orchestrator (baseline, burst, ramp-up, soak)
├── metrics.py              # Latency percentile statistics (p50, p90, p95, p99, TTFA)
├── system_monitor.py       # Real-time NVIDIA A10G GPU, VRAM, and CPU telemetry
├── run_stress_test.py      # Main CLI runner
└── results/                # Timestamped JSON benchmark reports
```

---

## 3. Pre-Flight Setup on AWS EC2

### Step 1: Activate the Environment & Install Dependencies
Inside your EC2 instance (`/home/ubuntu`):
```bash
# 1. Activate virtual environment
source ~/voice-env/bin/activate

# 2. Navigate to project root
cd ~/clinic_ai   # or your project directory

# 3. Install stress testing dependencies (if not already present)
pip install -r stress_test/requirements.txt
```

### Step 2: Start the Main Voice Server (Port 8998)
Run the core Google Calendar voice receptionist server:
```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8998
```
*(Verify server output shows: `🟢 Live GCal` and `Uvicorn running on http://0.0.0.0:8998`)*

---

## 4. Running Test Scenarios

### Scenario 1: Baseline Single-Call Benchmark
Establishes clean unconstrained latency for STT, Bedrock LLM, Google Calendar, and TTS:
```bash
python stress_test/run_stress_test.py --mode baseline
```

### Scenario 2: Concurrency Ramp-Up Test (Recommended)
Ramps up active concurrent callers gradually (e.g. from 2 up to 10 callers, adding 2 callers every 3 seconds) to detect degradation thresholds:
```bash
python stress_test/run_stress_test.py --mode ramp_up --concurrency 10 --step 2 --step-delay 3.0
```

### Scenario 3: Instant Burst Spike Test
Launches $N$ callers simultaneously at $T=0$ to test GPU queueing, CUDA thread contention, and Bedrock rate limits:
```bash
python stress_test/run_stress_test.py --mode burst --concurrency 8
```

### Scenario 4: Sustained Soak Test
Maintains a constant load of $N$ concurrent callers for a set duration to identify memory leaks, VAD state corruption, or GPU thermal throttling:
```bash
python stress_test/run_stress_test.py --mode soak --concurrency 5 --duration 120
```

---

## 5. Metrics & Threshold Guidelines

The test suite captures and analyzes:

* **TTFA (Time to First Audio)**:
  * Measures latency from the moment the caller finishes speaking until the first audio packet is received from Deirdre.
  * **Target on A10G**: $< 1.8\text{s}$ (p50), $< 2.6\text{s}$ (p95).
* **VAD Latency**:
  * The time required for Silero VAD to confirm turn completion (~1.22s deliberate conversational hysteresis).
* **Google Calendar Booking Latency**:
  * Time spent executing `check_calendar_slots` and `book_calendar_slot` against Google Calendar.
  * **Target**: $300\text{ms} - 800\text{ms}$.
* **Hardware Utilization Profile**:
  * **A10G GPU Compute Utilization %**
  * **VRAM Consumption** (Base ~2.5 GB; peak should remain under 6 GB during high concurrency)
  * **8 vCPU Load %**

All results are printed in a formatted report in the terminal and saved as a JSON report in `stress_test/results/`.
