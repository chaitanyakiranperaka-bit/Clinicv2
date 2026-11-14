# Autonomous Voice Receptionist: Verified Stress & Soak Benchmark Report

**Clinic System:** Star Dental and GP Clinic, Clonsilla, Dublin 15  
**Receptionist Persona:** Deirdre (Autonomous AI Clinic Voice Receptionist)  
**Infrastructure Stack:**
- **Host:** AWS EC2 `g5.xlarge` (`eu-west-1` Dublin, Ubuntu 22.04 LTS, 4 vCPUs, 15 GB usable RAM, NVIDIA A10G 24 GB GPU)
- **VAD Engine:** Silero VAD (CPU, 512-sample / 32 ms frame window, dual-threshold hysteresis)
- **STT Engine:** Faster-Whisper (`small.en`, CUDA `float16`)
- **LLM Reasoning & Function Calling:** AWS Bedrock Converse API (`qwen.qwen3-coder-30b-a3b-v1:0`)
- **Speech Synthesis (TTS):** Kokoro-82M (`bf_isabella`, 24 kHz WAV)
- **Calendar Sync:** Live Google Calendar API v3 (OAuth2 Service Account for Dr. Yousuf, Dentist Shailaja, and Nurse Kelly)

---

## Executive Summary

Following architectural hardening (bounded multi-hop tool execution loop, per-session turn lock and cancellation cleanup, conversation history sanitization, removal of default time fallbacks, and EU AI Act Art. 50 greeting disclosure), four benchmark scenarios were executed sequentially against the live clinic stack on AWS EC2.

Across **261 total concurrent calls** (`c10`, `c50`, `c100` ramp-up tests and a `c50` sustained soak test) and **1,848 live Google Calendar tool executions**:
- **Call Completion Rate:** **100.0%** (261 / 261 calls completed cleanly with **0 failed calls** and **0 timed-out calls**).
- **Multi-Week Calendar Traversal:** Because the live Google Calendar accumulated ~300 booked appointments across November and December during testing, callers routinely traversed 4 to 6 consecutive fully-booked weeks (`2026-11-16` through `2026-12-28`) before reaching open slots or hitting the simulator's 8-turn cap.
- **Hardware Envelope on `g5.xlarge`:**
  - **CPU (4 vCPUs):** Averaged `19.1%` at `c10`, `57.4%`–`61.6%` at `c50`, and `66.0%` (peak `89.3%`) at `c100`.
  - **System RAM (15 GB):** Averaged `20.6%` to `36.9%` (peaking at `40.8%` / ~6.1 GB).
  - **NVIDIA A10G GPU:** Compute averaged `17.2%` to `49.2%` (peaking at `85.0%`), with VRAM remaining between `2,005.5 MiB` and `3,483.0 MiB` (< `14.2%` of 24,576 MiB) and GPU temperatures between `27.6°C` and `36.0°C`.

---

## 1. Verified Benchmark Summary Table

All figures below are taken verbatim from the generated benchmark artifacts in `stress_test/results/`:

| Scenario | Mode | Target Concurrency | Duration | Total Calls | Completed (0 Fail / 0 Timeout) | GCal Bookings Created | Tool Calls (Check / Book) | Throughput | TTFA Mean / $p50$ / $p95$ | GCal Latency Mean / $p50$ / $p95$ | CPU Avg / Peak | RAM Avg / Peak | GPU Avg / Peak | VRAM Avg / Peak (MiB) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Run 1: Warmup Ramp-Up** | `ramp_up` | **10 calls** (+5 / 2s) | 89.00s | 10 | **10 (100%)** | 5 | 77 (72 / 5) | 6.7 calls/min | 0.007s / 0.001s / 0.048s | 0.545s / 0.500s / 1.114s | 19.1% / 67.3% | 20.6% / 21.5% | 17.2% / 70.0% | 2005.5 / 2207.0 |
| **Run 2: Clinic Load Ramp-Up** | `ramp_up` | **50 calls** (+5 / 2s) | 129.78s | 50 | **50 (100%)** | 13 | 365 (344 / 21) | 23.1 calls/min | 0.369s / 0.322s / 0.893s | 0.827s / 0.757s / 1.344s | 57.4% / 100.0% | 27.1% / 29.7% | 44.9% / 85.0% | 2916.9 / 3253.0 |
| **Run 3: Peak Stress Ramp-Up** | `ramp_up` | **100 calls** (+5 / 2s) | 193.92s | 100 | **100 (100%)** | 12 | 620 (583 / 37) | **30.9 calls/min** | 2.475s / 2.836s / 4.577s | 1.788s / 1.670s / 3.502s | 66.0% / 89.3% | 29.3% / 33.3% | 46.3% / 81.0% | 2959.0 / 3339.0 |
| **Run 4: Sustained Soak Test** | `soak` | **50 calls** (200s window) | 269.08s | 101 | **101 (100%)** | 17 | 786 (746 / 40) | 22.5 calls/min | 1.948s / 2.063s / 5.373s | 0.583s / 0.520s / 1.172s | 61.6% / 90.8% | 36.9% / 40.8% | 49.2% / 85.0% | 3367.1 / 3483.0 |

> **Measurement Note on TTFA & Booking Counts:**
> 1. **TTFA Metric Definition:** In `stress_test/metrics.py`, `ttfa` is computed as `max(0.0, first_audio_at - speech_ended_at)`, where `speech_ended_at` marks the end of streaming the caller's WAV fixture (which includes `1.35s` of trailing silence) and `first_audio_at` records the first audio packet received from the server (including pre-synthesized conversational filler audio for scheduling queries). At low concurrency (`c10`), the server often finishes VAD detection (`1.22s` silence threshold) and streams the filler audio before the final `0.13s` of trailing silence finishes sending, clamping `ttfa` near `0.001s`.
> 2. **Booking Count vs. Calendar Saturation:** Because tests ran against a single live Google Calendar without wiping prior events between runs, mid-November through mid-December dates became progressively saturated (~300 total events). Callers requesting filled dates had to check 4–6 consecutive weeks before finding an open slot, causing many calls to reach the simulator's 8-turn safety limit (`len(turns) >= 8`) and hang up cleanly before completing a booking.

---

## 2. Detailed Run Reports

### Run 1: Concurrency 10 Ramp-Up
- **Command:** `python stress_test/run_stress_test.py --mode ramp_up --concurrency 10 --step 5 --step-delay 2.0`
- **Artifact:** `stress_ramp_up_c10_20261114_221250.json`

```text
 Test Duration:        89.0s
 Total Calls:          10
 Successful Calls:     10 (100.0%)
 Failed Calls:         0
 Timed Out Calls:      0
 Google Cal Bookings:  5
 Throughput:           6.7 calls/min
------------------------------------------------------------------------------
 LATENCY BREAKDOWN: Time to First Audio (TTFA):
   • Mean: 0.007s  |  Min: 0.0s  |  Max: 0.19s
   • p50 (Median): 0.001s  |  p90: 0.002s  |  p95: 0.048s  |  p99: 0.19s
------------------------------------------------------------------------------
 GOOGLE CALENDAR TOOL EXECUTION LATENCY:
   • Mean: 0.545s  |  p50: 0.5s  |  p95: 1.114s  |  Max: 1.28s
------------------------------------------------------------------------------
 TOOL CALLS & RESPONSES (77 total executions):
   • check_calendar_slots: 72 executions
   • book_calendar_slot:   5 executions
------------------------------------------------------------------------------
 HARDWARE UTILIZATION PROFILE (AWS EC2):
   • CPU Usage:     Avg 19.1%  |  Peak 67.3% (4 vCPUs)
   • System RAM:    Avg 20.6%  |  Peak 21.5% (15 GB)
   • NVIDIA A10G:   Avg 17.2%  |  Peak 70.0%
   • VRAM Used:     Avg 2005.5 MiB  |  Peak 2207.0 MiB / 24,576 MiB
   • GPU Temp:      Avg 27.6°C  |  Peak 31.0°C
```

---

### Run 2: Concurrency 50 Ramp-Up
- **Command:** `python stress_test/run_stress_test.py --mode ramp_up --concurrency 50 --step 5 --step-delay 2.0`
- **Artifact:** `stress_ramp_up_c50_20261114_221753.json`

```text
 Test Duration:        129.78s
 Total Calls:          50
 Successful Calls:     50 (100.0%)
 Failed Calls:         0
 Timed Out Calls:      0
 Google Cal Bookings:  13
 Throughput:           23.1 calls/min
------------------------------------------------------------------------------
 LATENCY BREAKDOWN: Time to First Audio (TTFA):
   • Mean: 0.369s  |  Min: 0.0s  |  Max: 1.147s
   • p50 (Median): 0.322s  |  p90: 0.765s  |  p95: 0.893s  |  p99: 1.05s
------------------------------------------------------------------------------
 GOOGLE CALENDAR TOOL EXECUTION LATENCY:
   • Mean: 0.827s  |  p50: 0.757s  |  p95: 1.344s  |  Max: 1.982s
------------------------------------------------------------------------------
 TOOL CALLS & RESPONSES (365 total executions):
   • check_calendar_slots: 344 executions
   • book_calendar_slot:   21 executions
------------------------------------------------------------------------------
 HARDWARE UTILIZATION PROFILE (AWS EC2):
   • CPU Usage:     Avg 57.4%  |  Peak 100.0% (4 vCPUs)
   • System RAM:    Avg 27.1%  |  Peak 29.7% (15 GB)
   • NVIDIA A10G:   Avg 44.9%  |  Peak 85.0%
   • VRAM Used:     Avg 2916.9 MiB  |  Peak 3253.0 MiB / 24,576 MiB
   • GPU Temp:      Avg 31.5°C  |  Peak 35.0°C
```

---

### Run 3: Concurrency 100 Ramp-Up (Peak Stress)
- **Command:** `python stress_test/run_stress_test.py --mode ramp_up --concurrency 100 --step 5 --step-delay 2.0`
- **Artifact:** `stress_ramp_up_c100_20261114_223841.json`

```text
 Test Duration:        193.92s
 Total Calls:          100
 Successful Calls:     100 (100.0%)
 Failed Calls:         0
 Timed Out Calls:      0
 Google Cal Bookings:  12
 Throughput:           30.9 calls/min
------------------------------------------------------------------------------
 LATENCY BREAKDOWN: Time to First Audio (TTFA):
   • Mean: 2.475s  |  Min: 0.0s  |  Max: 5.831s
   • p50 (Median): 2.836s  |  p90: 4.378s  |  p95: 4.577s  |  p99: 5.005s
------------------------------------------------------------------------------
 GOOGLE CALENDAR TOOL EXECUTION LATENCY:
   • Mean: 1.788s  |  p50: 1.67s  |  p95: 3.502s  |  Max: 4.476s
------------------------------------------------------------------------------
 TOOL CALLS & RESPONSES (620 total executions):
   • check_calendar_slots: 583 executions
   • book_calendar_slot:   37 executions
------------------------------------------------------------------------------
 HARDWARE UTILIZATION PROFILE (AWS EC2):
   • CPU Usage:     Avg 66.0%  |  Peak 89.3% (4 vCPUs)
   • System RAM:    Avg 29.3%  |  Peak 33.3% (15 GB)
   • NVIDIA A10G:   Avg 46.3%  |  Peak 81.0%
   • VRAM Used:     Avg 2959.0 MiB  |  Peak 3339.0 MiB / 24,576 MiB
   • GPU Temp:      Avg 32.1°C  |  Peak 35.0°C
```

---

### Run 4: Concurrency 50 Sustained Soak Test (200s Active Window / 269s Total)
- **Command:** `python stress_test/run_stress_test.py --mode soak --concurrency 50 --duration 200`
- **Artifact:** `stress_soak_c50_20261114_224703.json`

```text
 Test Duration:        269.08s
 Total Calls:          101
 Successful Calls:     101 (100.0%)
 Failed Calls:         0
 Timed Out Calls:      0
 Google Cal Bookings:  17
 Throughput:           22.5 calls/min
------------------------------------------------------------------------------
 LATENCY BREAKDOWN: Time to First Audio (TTFA):
   • Mean: 1.948s  |  Min: 0.0s  |  Max: 7.632s
   • p50 (Median): 2.063s  |  p90: 3.82s  |  p95: 5.373s  |  p99: 7.138s
------------------------------------------------------------------------------
 GOOGLE CALENDAR TOOL EXECUTION LATENCY:
   • Mean: 0.583s  |  p50: 0.52s  |  p95: 1.172s  |  Max: 1.881s
------------------------------------------------------------------------------
 TOOL CALLS & RESPONSES (786 total executions):
   • check_calendar_slots: 746 executions
   • book_calendar_slot:   40 executions
------------------------------------------------------------------------------
 HARDWARE UTILIZATION PROFILE (AWS EC2):
   • CPU Usage:     Avg 61.6%  |  Peak 90.8% (4 vCPUs)
   • System RAM:    Avg 36.9%  |  Peak 40.8% (15 GB)
   • NVIDIA A10G:   Avg 49.2%  |  Peak 85.0%
   • VRAM Used:     Avg 3367.1 MiB  |  Peak 3483.0 MiB / 24,576 MiB
   • GPU Temp:      Avg 33.2°C  |  Peak 36.0°C
```

---

## 3. Architectural & Bottleneck Findings

1. **Multi-Hop Tool Loop & History Sanitization Resilience:**
   - Across 1,848 tool executions in these 4 runs, zero turns failed with Bedrock `ValidationException` or corrupted conversation state.
   - Callers seamlessly hopped across 5 consecutive full weeks (`2026-11-30` -> `2026-12-07` -> `2026-12-14` -> `2026-12-21` -> `2026-12-28`).
2. **Primary Concurrency Bottlenecks at 50–100 Callers:**
   - **Global STT/TTS Locks:** `stt.py` (`stt_lock`) and `tts.py` (`tts_lock`) serialize GPU inference across threads. In Run 4 (`c50` soak), GCal tool latency remained low ($p50 = 0.52\text{s}$, $p95 = 1.17\text{s}$), while TTFA rose to $p50 = 2.06\text{s}$, $p95 = 5.37\text{s}$ due to callers queuing on `stt_lock` before turn processing and `tts_lock` during synthesis.
   - **Event-Loop VAD Execution:** Per-frame Silero VAD inference on the main event loop drives 4-vCPU utilization to `57%`–`66%` average (`89%`–`100%` peak) at 50–100 concurrent calls.
   - **VRAM Headroom:** Peak VRAM usage across all tests was only `3,483 MiB` (`14.2%` of 24 GB), meaning the A10G GPU has ample memory to host multiple unlocked STT/TTS worker instances to remove lock contention.
