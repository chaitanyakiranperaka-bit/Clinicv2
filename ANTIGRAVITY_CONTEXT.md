# Star Dental & GP Clinic — Autonomous Voice AI Receptionist

## 1. Executive Summary & Project Identity
* **Project Name**: Star Clinic Autonomous Voice Receptionist ("Deirdre")
* **Location/Practice**: Star Dental & GP Clinic, Clonsilla, Dublin 15, Ireland
* **Timezone**: `Europe/Dublin` (Irish Standard Time / GMT with daylight saving)
* **Jurisdiction & Compliance**: GDPR (Irish Data Protection Commission) & EU AI Act compliant
  * **Transparency**: Automated AI identity disclosure on every call pickup
  * **Data Minimization**: Zero clinical symptoms stored in calendar payloads; only administrative categories (`Routine GP`, `Dental`, `Nurse Appointment`), Name, DOB, and Phone
  * **Data Residency**: All infrastructure and LLM inference strictly pinned to AWS Ireland (`eu-west-1`)

---

## 2. Infrastructure & Technical Architecture

```
              ┌──────────────────────────────────────────────────┐
              │                 Browser Softphone                │
              │        (HTML5 Web Audio API / 16kHz PCM)         │
              └─────────────────────────┬────────────────────────┘
                                        │ WebSocket (/ws/call)
                                        ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ EC2 Instance: g5.xlarge (4 vCPUs, 16GB RAM, NVIDIA A10G 24GB) | Dublin (eu-west-1)    │
│                                                                                        │
│  ┌───────────────────────┐   ┌──────────────────────┐   ┌───────────────────────────┐  │
│  │   Silero VAD (CPU)    ├──►│ Faster-Whisper (CUDA)├──►│ Bedrock Converse Client   │  │
│  │ (32ms / 512-smpl FIFO)│   │ (distil-large-v3)    │   │  (llm.py / Qwen 3 Coder)  │  │
│  └───────────────────────┘   └──────────────────────┘   └─────────────┬─────────────┘  │
│                                                                       │                │
│  ┌───────────────────────┐                                            │ AWS PrivateLink│
│  │   Kokoro-82M (CUDA)   │◄───────────────────────────────────────────┤ (Port 443 VPC) │
│  │ (af_heart Hiberno)    │                                            ▼                │
│  └───────────────────────┘                         ┌─────────────────────────────────┐ │
│                                                    │ AWS Bedrock (eu-west-1)         │ │
│                                                    │ qwen.qwen3-coder-30b-a3b-v1:0   │ │
│                                                    └─────────────────────────────────┘ │
└───────────────────────────────────────────┬────────────────────────────────────────────┘
                                            │ Google Calendar API v3
                                            ▼
                             ┌───────────────────────────────┐
                             │ Google Calendar Service Acct  │
                             │ (09:00 - 17:00 • 15-min slots)│
                             └───────────────────────────────┘
```

### Component Stack
1. **Host**: AWS EC2 `g5.xlarge` in `eu-west-1` running Ubuntu 22.04 LTS (NVIDIA A10G 24GB).
2. **LLM Engine**: Amazon Bedrock via Converse API using `qwen.qwen3-coder-30b-a3b-v1:0`.
   - Private communication over AWS PrivateLink interface VPC Endpoint (`172.31.16.231:443`).
3. **STT (Speech-to-Text)**: `faster-whisper` (`distil-large-v3` / `large-v3`).
4. **TTS (Text-to-Speech)**: `Kokoro-82M` (voice: `af_heart` tuned Irish/Hiberno cadence).
5. **VAD (Voice Activity Detection)**: `silero-vad` with dual-threshold hysteresis and barge-in grace periods.
6. **Calendar Integration**: Google Calendar API v3 authenticated via Service Account (`service_account.json`). Target Calendar ID: `chaitanyakiran.peraka@gmail.com`.

---

## 3. Repository Directory Structure

```text
Clinicv2/
├── config.py                 # Core settings, Clinicians, Bedrock Tool Spec, System Prompts
├── calendar_service.py       # Google Calendar API v3 wrapper + Self-Healing Collision Recovery
├── stt.py                    # Faster-Whisper transcription engine
├── tts.py                    # Kokoro-82M pipeline + filler audio generation
├── llm.py                    # Bedrock Converse client & tool execution dispatcher
├── server.py                 # FastAPI WebSocket orchestrator & VAD loop
├── static/
│   ├── index.html            # Browser Softphone simulator & real-time telemetry dashboard
│   └── audio-processor.js    # AudioWorkletProcessor 16kHz PCM downsampler
├── stress_test/
│   ├── run_stress_test.py    # CLI stress test runner
│   ├── load_runner.py        # Asynchronous multi-caller load engine
│   ├── call_simulator.py     # Autonomous goal-driven conversational simulator
│   ├── system_monitor.py     # Zero-dependency Linux /proc CPU/RAM & GPU telemetry
│   ├── metrics.py            # Latency collector (TTFA, VAD, Tool)
│   ├── stress_config.py      # Roster of 150 clinic patients & Irish conversational scripts
│   └── BENCHMARK_REPORT.md   # Official stress benchmark report (50 & 100 concurrency)
├── CODE_REVIEW_CONTEXT.md    # Dedicated architectural context file for code review models
└── ANTIGRAVITY_CONTEXT.md
```

---

## 4. Key Engineering Fixes Already Implemented

1. **Self-Healing Slot Collision Recovery**:
   - `book_calendar_slot` immediately queries remaining open daily slots upon collision and steers the caller to alternate open times.
2. **Autonomous Multi-Week Schedule Traversal**:
   - When days/weeks fill up, Deirdre autonomously traverses forward up to 5 weeks to find open slots without looping.
3. **Lossless VAD FIFO & Grace-Period Barge-In**:
   - `pcm_fifo` processed in exact 512-sample (32ms) frames with $400\text{ms}$ acoustic grace period to prevent echo bleed.
4. **Fast Conversational Filler**:
   - Sub-200ms filler audio (*"Let me check that for you..."*) eliminates dead air during Bedrock and GCal API lookups.
5. **64-Worker ThreadPoolExecutor**:
   - Replaced default 8-worker thread pool in FastAPI to prevent blocking during 50+ concurrent requests.
6. **Zero-Dependency Linux `/proc` Telemetry**:
   - Accurate, real-time CPU and RAM monitoring on Ubuntu EC2 directly from `/proc/stat` and `/proc/meminfo`.

---

## 5. Tool Specifications & Clinical Routing Rules

### Clinician Directory & Calendar Color Coding
* **Dr. Yousuf** (Routine GP): Calendar `colorId: 9` (Blueberry)
* **Dentist Shailaja** (Dental): Calendar `colorId: 7` (Peacock)
* **Nurse Kelly** (Nurse visits / bloods / smears / vaccines): Calendar `colorId: 10` (Basil)

### Calendar Rules
* Operating hours: 09:00 to 17:00, Monday through Saturday.
* Slot length: Exact 15-minute intervals (32 slots per clinician per day).
* Out-of-hours redirect: D-Doc / K-Doc GP cooperative services.

### Bedrock Tools (`config.py`):
1. `check_calendar_slots(clinician, date, time_preference)`: Reads open slots from Google Calendar and returns suggested times.
2. `book_calendar_slot(clinician, date, slot_time, patient_name, patient_dob, appointment_category)`: Creates confirmed Google Calendar events with collision recovery.
3. `trigger_emergency_divert(emergency_category)`: Diverts red-flag symptoms to emergency services (`999` / `112`).

---

## 6. Official Benchmarks (AWS EC2 `g5.xlarge`)

* **50 Concurrent Callers (Soak Test, 302 Calls over 11.7 mins)**:
  - **100.0% Success Rate (302/302 calls)**, 0 failures, 0 timeouts.
  - **133 Confirmed Google Calendar Bookings**.
  - **Median TTFA**: **794 ms**, $p95 = 1.79\text{ s}$.
  - **VRAM Stability**: Flat at $3.15\text{ GB} - 3.21\text{ GB}$ (zero tensor leak).
* **100 Concurrent Callers (Ramp-Up Test)**:
  - **100.0% Success Rate (100/100 calls)**, throughput: **31.6 calls/min**.
  - **CPU Utilization**: Avg 67.6% | Peak 89.5% (4 vCPUs).
  - **VRAM**: Flat at 3.84 GB – 3.89 GB (15.8% of 24.5 GB).
