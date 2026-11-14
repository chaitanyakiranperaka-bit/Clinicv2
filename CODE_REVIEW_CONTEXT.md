# Star Dental & GP Clinic: Autonomous Voice Receptionist ("Deirdre")
## Comprehensive Architecture & Engineering Context for Code Review

---

## 1. System Identity, Clinic Persona & Regulatory Framework

* **Practice Identity:** Star Dental and GP Clinic, Clonsilla, Dublin 15, Ireland (`Europe/Dublin` timezone).
* **Receptionist Persona:** "Deirdre" — professional, warm, concise Irish clinic receptionist. Adheres strictly to natural spoken English: 1–2 sentences per turn, 12-hour conversational times (*"half ten in the morning"*, *"two forty-five in the afternoon"*), zero markdown or emojis in audio output.
* **Clinician Team & Routing:**
  - **Dr. Yousuf:** Routine GP consultations (`colorId: 9` Blueberry).
  - **Dentist Shailaja:** Dental checkups, toothaches, hygiene (`colorId: 7` Peacock).
  - **Nurse Kelly:** Routine nurse visits, blood tests, smear tests, vaccines (`colorId: 10` Basil).
* **Clinical Safety & Emergency Protocols:**
  - Automated Red-Flag Triage: Immediate diversion for acute symptoms (chest pain, stroke signs / FAST, severe shortness of breath, heavy bleeding) to emergency services (`999` / `112`) via `trigger_emergency_divert`.
* **Regulatory & Data Compliance:**
  - **EU AI Act:** Explicit automated AI disclosure on call pickup (*"Hello, welcome to Star Dental and GP Clinic... You are speaking with Deirdre..."*).
  - **GDPR / Irish DPC Data Minimization:** Zero medical symptoms or clinical narratives are saved to calendar entries. Calendar events store only patient administrative metadata: Name, Phone, DOB, and Category (`Routine GP`, `Dental`, `Nurse Appointment`).
  - **Data Sovereignty:** All AWS infrastructure and Bedrock model inferences are pinned to `eu-west-1` (Dublin, Ireland).

---

## 2. Infrastructure & End-to-End Pipeline

```
  [Browser Softphone / AudioWorklet (16kHz Float32 PCM)]
                           │
                           ▼ WebSocket (/ws/call)
┌─────────────────────────────────────────────────────────────────────────────────┐
│ AWS EC2 g5.xlarge (4 vCPUs, 16 GB RAM, NVIDIA A10G 24GB) | eu-west-1 (Dublin)   │
│                                                                                 │
│  1. Inbound Audio FIFO -> Dual-Threshold Silero VAD (Grace Period & Hysteresis) │
│  2. Faster-Whisper STT (CPU int8 / CUDA Float16)                                │
│  3. Conversational Fast-Filler Streaming ("Let me check that for you...")       │
│  4. Bedrock Converse Client (Qwen 30B MoE: qwen.qwen3-coder-30b-a3b-v1:0)      │
│  5. Self-Healing Tool Execution Engine (Google Calendar API v3 Service Account) │
│  6. Kokoro 82M Irish TTS Engine (af_heart, ~0.15s RTF)                          │
└─────────────────────────────────────────────────────────────────────────────────┘
                           │
                           ▼ Google Calendar API v3 / OAuth2 Service Account
[Live Google Calendar: chaitanyakiran.peraka@gmail.com (GP, Dental, Nurse Calendars)]
```

### Component Details
1. **Server Host:** AWS EC2 `g5.xlarge` (Ubuntu 22.04 LTS), FastAPI + Uvicorn with a customized `ThreadPoolExecutor(max_workers=64)` to eliminate default thread pool exhaustion under heavy concurrency.
2. **Audio Transport:** Bidirectional WebSocket (`/ws/call`). Client streams 16kHz Float32 PCM chunks via HTML5 `AudioWorkletProcessor`. Server streams back Base64-encoded 24kHz WAV packets.
3. **Voice Activity Detection (VAD):** `silero-vad` on CPU with connection-isolated recurrent states.
   - Dual-threshold model: High threshold ($0.72$, $224\text{ms}$ streak) with a $400\text{ms}$ acoustic grace period during bot speech to prevent echo bleed barge-ins; standard threshold ($0.52$, $96\text{ms}$ streak) when caller is expected to speak.
   - Hysteresis: Drops to $0.35$ probability once speech starts to avoid mid-sentence clipping.
   - Conversational silence cutoff: $38\text{ frames} \approx 1.22\text{s}$ before concluding a turn.
4. **Speech-to-Text (STT):** `faster-whisper` (`distil-large-v3` / `large-v3` / `small.en`). Includes backchannel detection (*"uh-huh"*, *"mhm"*) and noise artifact filtering (coughs, microphone pops).
5. **LLM Engine:** AWS Bedrock Converse API with `qwen.qwen3-coder-30b-a3b-v1:0`. Chosen for native tool-calling adherence, low latency, and zero markdown formatting artifacts in speech transcripts.
6. **Tool Execution & Calendar Sync:** Google Calendar API v3 with a service account (`service_account.json`). Manages 15-minute slot intervals between 09:00 and 17:00, Monday through Saturday.
7. **Text-to-Speech (TTS):** Kokoro 82M TTS using `af_heart` voice tuned for Irish receptionist cadence. Sentence-boundary chunking allows immediate first-sentence audio playback while remaining sentences synthesize in parallel.

---

## 3. Codebase File Map & Module Architecture

```text
Clinicv2/
├── config.py                 # System configuration, clinic rules, clinician directory,
│                             # Bedrock tool schemas, and Irish receptionist prompt builder.
├── server.py                 # FastAPI orchestrator, WebSocket lifecycle, VAD state machine,
│                             # barge-in handling, backchannel filtering, sentence streaming.
├── llm.py                    # AWS Bedrock Converse client, conversation memory manager,
│                             # tool execution dispatcher, dynamic date/time resolution.
├── calendar_service.py       # Google Calendar API v3 wrapper, slot availability query,
│                             # multi-week search, self-healing race-condition recovery.
├── stt.py                    # Faster-Whisper wrapper with model initialization & warmup.
├── tts.py                    # Kokoro-82M TTS pipeline, sentence tokenizer, filler audio caching.
├── static/
│   ├── index.html            # Web Softphone UI, audio visualizer, real-time diagnostic logs.
│   └── audio-processor.js    # AudioWorkletProcessor for low-latency 16kHz PCM streaming.
├── stress_test/
│   ├── run_stress_test.py    # Main CLI test runner (baseline, ramp_up, burst, soak).
│   ├── load_runner.py        # Asynchronous multi-caller load generator.
│   ├── call_simulator.py     # Autonomous, goal-driven conversational caller simulator.
│   ├── system_monitor.py     # Zero-dependency Linux /proc CPU/RAM & nvidia-smi GPU monitor.
│   ├── metrics.py            # Latency collector (TTFA, VAD, Tool) and report JSON exporter.
│   ├── stress_config.py      # Roster of 150 clinic patients, Dublin test scripts, fixtures.
│   └── BENCHMARK_REPORT.md   # Official stress benchmark report (50 & 100 concurrency).
└── dentally/                 # Prototype integration for Dentally Dental EHR API.
```

---

## 4. Key Engineering Innovations & Self-Healing Mechanisms

### 1. Self-Healing Race-Condition & Double-Booking Recovery
* **Problem:** Under high concurrency (50–100 simultaneous callers), multiple patients frequently select the same slot (e.g. `14:30`) within milliseconds.
* **Mechanism (`calendar_service.py` & `llm.py`):**
  When `book_calendar_slot` encounters an already-booked slot, instead of failing or entering an apology loop, it immediately queries remaining open slots for that day and injects an explicit conversational steering prompt:
  > *"Tell the caller: 'I apologize, but 14:30 was just taken. However, I have 09:00, 11:15, or 15:30 open on that day. Would one of those suit you?'"*
* **Result:** 100% of collided callers seamlessly recover and book an alternative open slot without human intervention.

### 2. Autonomous Multi-Week Forward Scheduling
* When a requested day is fully booked, the receptionist autonomously checks the next week ($D + 7$) and subsequent weeks. Under heavy soak testing, the agent successfully traversed up to 5 consecutive full weeks to find open slots in late December.

### 3. Dynamic Tool Argument Resolution (`llm.py`)
* Solves LLM historical hallucination where Bedrock might attempt to book a slot from a previous turn's rejected date.
* `resolve_agreed_date` prioritizes current tool arguments, validates Dublin timezone limits, and cross-references recent successful `check_calendar_slots` checks.

### 4. Abbreviation-Safe Sentence Splitting (`server.py`)
* Standard punctuation splitters break titles like `Dr. Yousuf` into `Dr.` and `Yousuf`, ruining TTS pronunciation.
* Regex mask protects `Dr.`, `Mr.`, `Ms.`, `St.`, `i.e.`, `e.g.` while preserving sentence-ending inflection (`?`, `!`, `.`).

### 5. Zero-Dependency Linux Resource Telemetry (`system_monitor.py`)
* Directly parses `/proc/stat` for exact CPU time differentials and `/proc/meminfo` for active RAM utilization without requiring third-party C-extensions or Python packages.

---

## 5. Verified Performance Benchmarks (AWS EC2 `g5.xlarge`)

| Test Scenario | Concurrency | Calls | Duration | Success Rate | Bookings | Median TTFA ($p50$) | $p95$ TTFA | CPU Usage | RAM Usage | GPU Compute | VRAM Used |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Concurrency Ramp-Up** | 50 calls | 50 | 132s | **100.0%** | 50 | **185 ms** | 1.02 s | 45.2% | 28.5% | 32.7% | 3.17 GB |
| **Enterprise Soak Test** | 50 calls | 302 | 703s | **100.0%** | 133 | **794 ms** | 1.79 s | 52.4% | 30.2% | 48.7% | 3.21 GB |
| **Peak Stress Test** | 100 calls | 100 | 190s | **100.0%** | 24 | **2,595 ms** | 4.64 s | 67.6% | 37.7% | 49.2% | 3.89 GB |

* **Memory Stability:** VRAM remained completely flat at $\sim 3.2\text{ GB} - 3.8\text{ GB}$ (out of 24.5 GB) over 11.7 minutes across 302 calls, proving zero tensor leakage.
* **Bottleneck Discovery:** At 100 concurrency, the p95 latency increase to 4.64s was traced directly to Google Calendar API HTTPS rate-limiting ($3.48\text{s}$ at p95) rather than local compute limits.

---

## 6. Targeted Areas for Code Review

When conducting a comprehensive review, evaluate the following specific dimensions:

1. **Asyncio & Concurrency Safety:**
   - Review `server.py` WebSocket loop: Is task cancellation completely clean when a caller interrupts mid-turn?
   - Are there any hidden race conditions in `pcm_fifo` concatenation or `asyncio.to_thread` executions?
   - Thread pool sizing: Is `max_workers=64` appropriate, or should STT/TTS use dedicated, separate pools?
2. **Error Handling & Resilience:**
   - Network failure modes: What happens if Google Calendar API returns `429 Too Many Requests` or `503 Service Unavailable`? Does the conversational fallback fail gracefully?
   - Bedrock client timeout resilience: Are the `connect_timeout=4`, `read_timeout=12` settings optimal?
3. **Data Security & Privacy (GDPR / HIPAA):**
   - Review data structures in `config.py` and `calendar_service.py` for PII leakage in logs or exceptions.
   - Are calendar event descriptions adequately sanitized?
4. **Latency & Performance Optimization:**
   - In-memory caching for Google Calendar: How to safely implement a short TTL (e.g. 15–30s) slot cache to eliminate the external API bottleneck during concurrency spikes without risking stale double-bookings?
   - Bedrock token streaming: Can sentence generation be pipelined directly to TTS sentence-by-sentence during LLM generation?
5. **Code Maintainability & Modularity:**
   - Clean separation of concerns between `llm.py` and `calendar_service.py`.
   - Preparation for multi-channel ingestion (e.g. bridging `/ws/call` with Twilio / FreeSWITCH SIP telephony).
