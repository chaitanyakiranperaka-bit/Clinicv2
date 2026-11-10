# Dentally NexGen API Integration — Production Test Environment (Read-Only)

## 1. Executive Summary & Separation of Concerns

* **Purpose**: Dedicated testing and verification environment for the **Dentally NexGen REST API (v2026-01-01)** against the live production practice **Star Dental Care** in Clonsilla, Dublin 15, Ireland.
* **Scope Constraint**: **STRICTLY READ-ONLY**. No appointments, records, or practice resources are created, updated, or deleted.
* **Isolation Architecture**:
  * **Main App (`server.py`, `calendar_service.py`, `config.py`)**: Runs pure Google Calendar integration for Routine GP (`Dr. Yousuf`) and Nurse Appointments (`Nurse Kelly`) on port `8998`. Contains zero Dentally imports or logic to prevent any confusion or regressions.
  * **Dentally Test App (`dentally_*`)**: Completely self-contained suite prefixed with `dentally_` running on port `8999` (or via CLI test runner).

---

## 2. Dentally Practice & API Credentials

| Parameter | Value | Description |
| :--- | :--- | :--- |
| **Practice Name** | Star Dental Care | Unit 3, Lidl, Clonsilla Road, Clonsilla, Dublin 15 (`D15 T0HE`) |
| **Practice Phone** | `+353 1 822 5686` | Main clinic telephone line |
| **Practice UUID** | `00b65f88-49df-48a3-b949-bc195e592593` | Multi-tenant tenant identifier passed via `X-Practice-Id` |
| **API Base URL** | `https://api.dentally.co` | Production UK endpoint |
| **Auth Endpoint** | `https://api.dentally.co/v2/oauth/token` | Auth0-backed client credentials exchange |
| **Client ID** | `i4lyH4DVaMuaGVXkUUzhvPjuWDNgQQT3ZvWkEbtsjAR20cGH` | Partner integration client ID |
| **Client Secret** | `bJEiC0egABhVlsaph85kEF3Ee5o1rbT8T5OraxpeWIV0tdBuoP8o0aFkAkmK9TW4` | Partner client secret |
| **API Version** | `2026-01-01` | Pinned revision header `Dentally-API-Version` |
| **Granted Scopes**| `practitioner:availability:read`<br>`appointment:read`<br>`appointment:write`<br>`site:read`<br>`calendar:read`<br>`identifier_mapping:read` | Fixed partner permissions |

---

## 3. Verified Live Clinical Roster & Reasons

### Active Dentally Practitioners
* **Dr. Shailja Sharma** (`Dentist Shailaja`): `16c136c6-f2f1-4fa9-9d7b-a5527539c506`
* **Dr. Reihaneh Afrasaiabi**: `1181fe00-8cda-4635-9677-8709e7b0e0ab`
* **Dr. Aubrey Agang**: `90541d1b-e9f2-4858-a8a1-384ca6a817fd`
* **Dr. Salma Naz**: `f1ab2bde-4aad-4f00-8366-02e492549126`
* **Dr. Sani Dangaji**: `28fe5c81-405f-4fed-a3ff-6383f6c1d2c1`

### Appointment Reasons Configured in Practice
* `Exam` (`0fcd17b7-8f9c-4ba7-b24c-58a57cc02d48`)
* `Exam + Scale & Polish` (`0308d5a1-ad59-44ea-b517-9cefd9c71e6a`)
* `Scale & Polish` (`fe07a610-f31f-4fc4-bb6a-1a4ae850380e`)
* `Broken Tooth` (`54216831-d01e-490b-b1b1-ec69af4887fe`)
* `Root Canal Treatment` (`41f3aa82-d60a-4136-a50a-54df1de7514d`)
* `Review` (`bc9edca1-9d6f-486a-a93b-1c34422fcfa7`)
* `Continuing Treatment` (`72893fe0-1c15-4219-ab0e-b1a2f740aa48`)

---

## 4. File Structure & Responsibilities

```
Clinicv2_mac/
│
├── ANTIGRAVITY_CONTEXT.md           # Core context for Google Calendar & GP/Nurse workflow
├── config.py                        # Pure Google Calendar and Bedrock setup (Port 8998)
├── calendar_service.py              # Pure Google Calendar and local staging service
├── server.py                        # Pure Google Calendar FastAPI server & WebSocket
│
├── dentally_ANTIGRAVITY_CONTEXT.md  # THIS FILE: Dedicated Dentally production context
├── dentally_config.py               # Dentally credentials, practice UUID, system prompt & tools
├── dentally_client.py               # Pure READ-ONLY HTTP client with token caching (24h TTL)
├── dentally_service.py              # Pure READ-ONLY business logic (availability, sites, appts)
├── dentally_server.py               # Standalone FastAPI test server & dashboard (Port 8999)
└── dentally_test.py                 # Standalone CLI verification test suite
```

---

## 5. Read Endpoints Implemented

1. **Authentication Token (`POST /v2/oauth/token`)**:
   * Token cached in memory for 86,400s (24 hours).
   * Refreshed proactively when remaining validity is $< 300\text{s}$.
2. **Practice Site (`GET /v2/sites`)**:
   * Retrieves clinic name, address (`Unit 3, Lidl, Clonsilla Road, Clonsilla, Dublin 15`), phone (`+353 1 822 5686`), website (`stardentalcare.ie`), and 7-day opening hours.
3. **Practitioner Availabilities (`GET /v2/practitioners/availabilities`)**:
   * Accepts `date_from`, `date_to` ($\le 7\text{ days}$ range), and `practitioner_ids[]`.
   * Converts UTC timestamps (`YYYY-MM-DDTHH:MM:SSZ`) to `Europe/Dublin` civil times.
   * Generates discrete 15-minute appointment slots (`09:00`, `09:15`, etc.) within clinic hours (09:00 - 17:00).
4. **Appointments List (`GET /v2/appointments`)**:
   * Retrieves recent and upcoming appointments with practitioner names, patient names, and visit reasons.
5. **Appointment Reasons (`GET /v2/appointment_reasons`)**:
   * Retrieves practice service catalog.
6. **Calendar Zones (`GET /v2/calendar_zones`)**:
   * Retrieves practice calendar zoning blocks.

---

## 6. How to Run & Verify

### Running the CLI Test Suite
```bash
python dentally_test.py
```
*Expected Result*: Verifies token acquisition, site reading, live Dentist Shailaja open slots, appointment list, and appointment reasons with a summary status code 0.

### Running the Standalone Dentally Test Server
```bash
python -m uvicorn dentally_server:app --host 0.0.0.0 --port 8999
```
* Access Test UI: `http://localhost:8999/`
* Health/Status endpoint: `http://localhost:8999/status`
* Site API: `http://localhost:8999/api/dentally/site`
* Live Availability API: `http://localhost:8999/api/dentally/availability?clinician=Dentist+Shailaja&date=2026-11-11&time=10:00`
* Appointments API: `http://localhost:8999/api/dentally/appointments?limit=5`

### Running the Main Google Calendar App (Unchanged)
```bash
python -m uvicorn server:app --host 0.0.0.0 --port 8998
```
* Operates completely independently with zero dependencies on Dentally.
