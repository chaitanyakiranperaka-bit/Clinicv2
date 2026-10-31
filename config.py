import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DUBLIN_TZ = ZoneInfo("Europe/Dublin")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "qwen.qwen3-coder-30b-a3b-v1:0")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "chaitanyakiran.peraka@gmail.com")
SERVICE_ACCOUNT_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "/home/ubuntu/service_account.json")

KNOWN_PATIENTS = {
    "+353871234567": {"name": "Sean Murphy", "dob": "14/03/1982"},
    "+353869876543": {"name": "Aoife Kelly", "dob": "22/08/1990"},
}

CLINICIANS = {
    "Dr. Yousuf": {"colorId": "9", "role": "Routine GP"},
    "Dentist Shailaja": {"colorId": "7", "role": "Dental"},
    "Nurse Kelly": {"colorId": "10", "role": "Nurse Appointment"},
}

ALL_DAILY_SLOTS = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in (0, 15, 30, 45)]

BEDROCK_TOOLS = {
    "tools": [
        {
            "toolSpec": {
                "name": "check_calendar_slots",
                "description": "Call this tool whenever checking what appointment times are available, OR when patient asks for a specific time/time of day (e.g. 'Do you have 10:00?', 'What about afternoon?'). Always call this tool to verify availability rather than assuming from previous answers.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "clinician": {"type": "string", "enum": ["Dr. Yousuf", "Dentist Shailaja", "Nurse Kelly"]},
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
                            "time_preference": {"type": "string", "description": "Specific time requested (e.g. '10:00', '14:30', '10am') or general preference ('morning', 'afternoon', 'any')."}
                        },
                        "required": ["clinician", "date"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "book_calendar_slot",
                "description": "Call this tool IMMEDIATELY when the patient confirms an appointment slot. Never confirm without calling this tool.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "clinician": {"type": "string", "enum": ["Dr. Yousuf", "Dentist Shailaja", "Nurse Kelly"]},
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
                            "slot_time": {"type": "string", "description": "Slot time from 09:00 to 16:45 (e.g. '09:30', '15:00')."},
                            "patient_name": {"type": "string"},
                            "patient_dob": {"type": "string"},
                            "appointment_category": {"type": "string", "enum": ["Routine GP", "Dental", "Nurse Appointment"]}
                        },
                        "required": ["clinician", "date", "slot_time", "patient_name", "patient_dob", "appointment_category"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "trigger_emergency_divert",
                "description": "Call this if patient reports acute red-flag symptoms.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "emergency_category": {"type": "string"}
                        },
                        "required": ["emergency_category"]
                    }
                }
            }
        }
    ]
}

def build_system_prompt(caller_phone: str) -> str:
    now_dublin = datetime.now(DUBLIN_TZ)
    today_iso = now_dublin.strftime("%Y-%m-%d")
    today_str = now_dublin.strftime("%A, %d %B %Y")
    tomorrow_dt = now_dublin + timedelta(days=1)
    tomorrow_iso = tomorrow_dt.strftime("%Y-%m-%d")
    tomorrow_str = tomorrow_dt.strftime("%A, %d %B %Y")

    matched = KNOWN_PATIENTS.get(caller_phone)
    caller_ctx = (
        f"Caller is known patient '{matched['name']}' (DOB: {matched['dob']}). Verify identity and confirm DOB before booking."
        if matched else
        f"Caller ID {caller_phone} is new. Ask for Full Name and DOB before booking."
    )

    return (
        "You are Deirdre, automated voice receptionist at Star Dental & GP Clinic in Clonsilla, Dublin 15, Ireland. "
        "Keep replies strictly to 1 or 2 natural, concise sentences. "
        "NEVER use emojis, emoticons, symbols, markdown, bullet points, or backticks. Speak strictly in plain spoken English words.\n\n"
        f"CALENDAR CONTEXT:\n"
        f"- Today is {today_str} (ISO: {today_iso}).\n"
        f"- Tomorrow is {tomorrow_str} (ISO: {tomorrow_iso}).\n"
        f"- Always use {today_iso} or {tomorrow_iso} for dates. Never use past years.\n"
        f"- Operating Hours: Monday to Saturday 09:00 to 17:00. The clinic is CLOSED on Sundays (direct urgent issues to D-Doc/K-Doc).\n"
        f"- Caller Context: {caller_ctx}\n\n"
        "CLINICAL & FUNCTION-CALLING RULES:\n"
        "1. AVAILABILITY: When patient asks for an appointment or a specific/different time (e.g. 'Do you have 10:00?', 'What about afternoon?'), ALWAYS invoke `check_calendar_slots` with their requested time or preference. Never assume or claim a time is unavailable without calling the tool.\n"
        "2. BOOKING: When patient agrees to a time, invoke `book_calendar_slot`. Do NOT claim an appointment is confirmed in text without calling the tool.\n"
        "3. RED FLAGS: If patient reports chest pain, breathlessness, stroke signs (FAST), or heavy bleeding, call `trigger_emergency_divert` and say: "
        "'This sounds like an emergency. Please hang up immediately and dial 999 or 112 for an ambulance.'\n"
        "4. ROUTING: Dr. Yousuf = Routine GP; Dentist Shailaja = Dental; Nurse Kelly = Bloods, smears, vaccines."
    )
