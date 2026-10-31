### Part 1: Export Code from EC2 to Git

Run these commands inside your EC2 terminal to initialize Git, ignore sensitive credentials, and push to your repository:

```bash
cd ~/clinic_ai

# 1. Initialize git repository
git init

# 2. Prevent sensitive credentials, virtual environments, and weights from being pushed
cat << 'EOF' > .gitignore
voice-env/
venv/
__pycache__/
*.pyc
service_account.json
*.pem
.env
.cache/
kokoro-v1_0.pth
*.wav
EOF

# 3. Add all modular files
git add .
git commit -m "feat: complete modular voice receptionist with Bedrock Qwen and Google Calendar"

# 4. Set your main branch and connect to your remote repo (GitHub/GitLab)
git branch -M main
# Replace with your actual git remote URL:
git remote add origin git@github.com:<YOUR_USERNAME>/<YOUR_REPO>.git
git push -u origin main

```

*(If using HTTPS with a Personal Access Token or SSH keys, ensure your GitHub/GitLab credentials are added to EC2 or push using `gh auth login`.)*

---

### Part 2: Markdown Context File for Antigravity

Save the file below in the root of your project as `ANTIGRAVITY_CONTEXT.md`. When opening the project in Antigravity, point the AI to this file to provide full context on what is working, the design decisions, and where to pick up development.

```markdown
# Star Dental & GP Clinic — Voice AI Receptionist

## 1. Executive Summary & Project Identity
* **Project Name**: Star Clinic Autonomous Voice Receptionist ("Deirdre")
* **Location/Practice**: Star Dental & GP Clinic, Clonsilla, Dublin 15, Ireland[cite: 1, 2]
* **Timezone**: `Europe/Dublin` (Irish Standard Time / GMT with daylight saving)[cite: 1, 2]
* **Jurisdiction & Compliance**: GDPR (Irish Data Protection Commission) & EU AI Act compliant[cite: 1]
  * **Transparency**: Automated AI identity disclosure on every call pickup[cite: 1, 2]
  * **Data Minimization**: Zero clinical symptoms stored in calendar payloads; only administrative categories (`Routine GP`, `Dental`, `Nurse Appointment`), Name, DOB, and Phone[cite: 1, 2]
  * **Data Residency**: All infrastructure and LLM inference strictly pinned to AWS Ireland (`eu-west-1`)[cite: 2]

---

## 2. Infrastructure & Technical Architecture


```

```
              ┌──────────────────────────────────────────────────┐
              │                 Browser Softphone                │
              │        (HTML5 Web Audio API / 16kHz PCM)         │
              └─────────────────────────┬────────────────────────┘
                                        │ WebSocket (/ws/call)
                                        ▼

```

┌────────────────────────────────────────────────────────────────────────────────────────┐
│ EC2 Instance: c7i.2xlarge (8 vCPU, 16GB RAM) | Dublin (eu-west-1)                     │
│                                                                                        │
│  ┌───────────────────────┐   ┌──────────────────────┐   ┌───────────────────────────┐  │
│  │   Silero VAD (CPU)    ├──►│ Faster-Whisper (CPU) ├──►│ Bedrock Converse Client   │  │
│  │ (32ms / 512-smpl FIFO)│   │  (small.en int8 8thr)│   │  (llm.py / Qwen 3 Coder)  │  │
│  └───────────────────────┘   └──────────────────────┘   └─────────────┬─────────────┘  │
│                                                                       │                │
│  ┌───────────────────────┐                                            │ AWS PrivateLink│
│  │   Kokoro-82M (CPU)    │◄───────────────────────────────────────────┤ (Port 443 VPC) │
│  │ (bf_isabella Hiberno) │                                            ▼                │
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
1. **Host**: AWS EC2 `c7i.2xlarge` in `eu-west-1` running Ubuntu 24.04 LTS.
2. **LLM Engine**: Amazon Bedrock via Converse API using `qwen.qwen3-coder-30b-a3b-v1:0`[cite: 1, 2].
   * *Architecture Note*: Evaluated `google.gemma-3-12b-it`, but migrated to `qwen.qwen3-coder-30b-a3b-v1:0` because Qwen provides native Bedrock `toolUse` execution without generating markdown backticks in text output.
   * *Network Route*: Private communication over AWS PrivateLink interface VPC Endpoint (`172.31.x.x:443`).
3. **STT (Speech-to-Text)**: `faster-whisper` (`small.en` model, CPU int8 quantization, 8 threads, ~890ms latency).
4. **TTS (Text-to-Speech)**: `Kokoro-82M` (voice: `bf_isabella` British/Hiberno accent, CPU execution RTF ~0.20x).
5. **VAD (Voice Activity Detection)**: `silero-vad` on CPU with a 512-sample (32ms) sliding FIFO buffer.
6. **Calendar Integration**: Google Calendar API v3 authenticated via Service Account (`service_account.json`). Target Calendar ID: `chaitanyakiran.peraka@gmail.com`.

---

## 3. Repository Directory Structure

```text
clinic_ai/
├── config.py           # Core settings, Clinicians, Bedrock Tool Spec, System Prompts
├── calendar_service.py # Google Calendar API v3 wrapper + Local Staging Queue
├── stt.py              # Faster-Whisper CPU int8 transcription engine
├── tts.py              # Kokoro-82M pipeline + filler audio generation
├── llm.py              # Bedrock Converse client & tool execution dispatcher
├── server.py           # FastAPI WebSocket orchestrator & VAD loop
├── static/
│   └── index.html      # Browser Softphone simulator & real-time telemetry dashboard
├── service_account.json# (Ignored in git) Google Cloud Service Account credentials
└── ANTIGRAVITY_CONTEXT.md

```

---

## 4. Key Engineering Fixes Already Implemented

1. **VPC Endpoint Port 443 Inbound Rule**:
* Resolved initial TCP timeout by adding HTTPS (port 443) inbound rule to the Interface VPC Endpoint Security Group (`172.31.16.231:443`).


2. **Audio Sample Rate Resampling**:
* Web browsers default to 44.1kHz or 48kHz. In `static/index.html`, a linear interpolation downsampler converts microphone input to clean 16kHz Float32 PCM before transmitting over WebSocket.


3. **Lossless VAD FIFO Buffer**:
* In `server.py`, incoming chunks enter a continuous NumPy sliding buffer `pcm_fifo` processed in exact 512-sample (32ms) frames with zero packet loss.


4. **VAD Recurrent State Reset**:
* Calling `vad_model.reset_states()` after every turn ensures silence drift is cleared and subsequent user utterances trigger instantly.


5. **Web Browser Secure Context Constraint**:
* Modern browsers restrict `navigator.mediaDevices.getUserMedia` to HTTPS or `http://localhost`. Testing must always use `http://localhost:8998` via SSH tunneling (`-L 8998:localhost:8998`).


6. **Date Grounding in Tool Calls**:
* Dynamic Dublin timezone injection into the system prompt ensures the LLM generates valid upcoming dates (`2026-10-31`, etc.) rather than defaulting to training data years.



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

1. `check_calendar_slots(clinician, date, time_preference)`: Reads open slots from Google Calendar and returns 2–3 suggested times.
2. `book_calendar_slot(clinician, date, slot_time, patient_name, patient_dob, appointment_category)`: Creates the 15-minute appointment on Google Calendar and logs confirmation.
3. `trigger_emergency_divert(emergency_category)`: Diverts red-flag symptoms (chest pain, acute breathlessness, FAST stroke signs, severe hemorrhage) to emergency services (`999` / `112`) and flashes an alert banner on the clinic dashboard.



---

## 6. Environment Variables & Runtime Commands

### Required Variables

```bash
export AWS_DEFAULT_REGION="eu-west-1"
export AWS_REGION="eu-west-1"
export BEDROCK_MODEL_ID="qwen.qwen3-coder-30b-a3b-v1:0"
export GOOGLE_CALENDAR_ID="chaitanyakiran.peraka@gmail.com"
export GOOGLE_SERVICE_ACCOUNT_FILE="/home/ubuntu/service_account.json"

```

### Starting the Server

```bash
cd ~/clinic_ai
source ~/voice-env/bin/activate
python -m uvicorn server:app --host 0.0.0.0 --port 8998

```

### SSH Port-Forward Tunnel (from Client Laptop)

```bash
ssh -i "<path-to-key>.pem" -L 8998:localhost:8998 ubuntu@<EC2-PUBLIC-IP>
# Open http://localhost:8998 in browser

```

---

## 7. Antigravity Next Steps & Roadmap

When continuing development inside Antigravity, focus on the following backlog items:

1. **Replace `ScriptProcessorNode` with `AudioWorklet**`:
* `static/index.html` currently uses deprecated `ScriptProcessorNode`. Migrate to an `AudioWorkletProcessor` running on a background audio thread to eliminate occasional UI-thread audio glitches.


2. **Persistent Database Layer**:
* Migrate the in-memory `KNOWN_PATIENTS` dictionary and `LOCAL_BOOKINGS` staging list to PostgreSQL (AWS RDS or local SQLite) with SQLAlchemy/Tortoise-ORM.


3. **Telephony Ingestion (Twilio / FreeSWITCH / Asterisk SIP)**:
* Bridge the WebSocket handler (`/ws/call`) to accept bidirectional G.711 / μ-law 8kHz audio streams from Twilio Media Streams or an Asterisk/FreeSWITCH SIP PBX trunk.


4. **Irish Practice Management System (PMS) Export**:
* Implement automated Healthlink / Socrates / Helix PMS export adapters for completed provisional bookings.



```

```
