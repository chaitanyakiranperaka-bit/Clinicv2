import os
from pathlib import Path
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

def _load_dotenv_if_present():
    """Lightweight zero-dependency .env loader that searches current & parent directories."""
    cur = Path(__file__).resolve().parent
    search_dirs = [cur, cur.parent, Path.cwd()]
    for d in search_dirs:
        env_file = d / ".env"
        if env_file.is_file():
            try:
                with open(env_file, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if line and not line.startswith("#") and "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip().strip("'\"")
                            if k and k not in os.environ:
                                os.environ[k] = v
                break
            except Exception:
                pass

_load_dotenv_if_present()

DUBLIN_TZ = ZoneInfo("Europe/Dublin")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "qwen.qwen3-coder-30b-a3b-v1:0")

# ==============================================================================
# DENTALLY NEXGEN API (v2026-01-01) - TEST PRODUCTION CONFIGURATION
# STRICTLY READ-ONLY ACCESS (No write operations)
# Credentials loaded from .env or system environment (NEVER hardcoded in source)
# ==============================================================================
DENTALLY_BASE_URL = os.getenv("DENTALLY_BASE_URL", "https://api.dentally.co")
DENTALLY_AUTH_URL = os.getenv("DENTALLY_AUTH_URL", f"{DENTALLY_BASE_URL}/v2/oauth/token")
DENTALLY_CLIENT_ID = os.getenv("DENTALLY_CLIENT_ID", "")
DENTALLY_CLIENT_SECRET = os.getenv("DENTALLY_CLIENT_SECRET", "")
DENTALLY_PRACTICE_ID = os.getenv("DENTALLY_PRACTICE_ID", "")
DENTALLY_API_VERSION = "2026-01-01"
DENTALLY_SERVER_PORT = int(os.getenv("DENTALLY_SERVER_PORT", "8999"))

# Known Live Practitioners at Star Dental Care
DENTALLY_PRACTITIONERS = {
    "Dentist Shailaja": "16c136c6-f2f1-4fa9-9d7b-a5527539c506",
    "Shailja Sharma": "16c136c6-f2f1-4fa9-9d7b-a5527539c506",
    "Reihaneh Afrasaiabi": "1181fe00-8cda-4635-9677-8709e7b0e0ab",
    "Aubrey Agang": "90541d1b-e9f2-4858-a8a1-384ca6a817fd",
    "Salma Naz": "f1ab2bde-4aad-4f00-8366-02e492549126",
    "Sani Dangaji": "28fe5c81-405f-4fed-a3ff-6383f6c1d2c1",
}

ALL_DAILY_SLOTS = [f"{h:02d}:{m:02d}" for h in range(9, 17) for m in (0, 15, 30, 45)]

# Known Patients for Test Inbound Calls
KNOWN_PATIENTS = {
    "+353871234567": {"name": "Sean Murphy", "dob": "14/03/1982"},
    "+353869876543": {"name": "Aoife Kelly", "dob": "22/08/1990"},
}

# ==============================================================================
# BEDROCK TOOLS FOR DENTALLY (STRICTLY READ-ONLY)
# ==============================================================================
DENTALLY_BEDROCK_TOOLS = {
    "tools": [
        {
            "toolSpec": {
                "name": "check_dentally_slots",
                "description": "Call this tool whenever checking appointment availability OR whenever caller mentions ANY dental time (e.g. '10:00', 'morning', 'after 2pm'). Pass the caller's time into `time_preference`.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "clinician": {
                                "type": "string",
                                "enum": ["Dentist Shailaja", "Reihaneh Afrasaiabi", "Aubrey Agang", "Salma Naz", "Sani Dangaji"],
                                "description": "The dental practitioner."
                            },
                            "date": {
                                "type": "string",
                                "description": "Date in YYYY-MM-DD format."
                            },
                            "time_preference": {
                                "type": "string",
                                "description": "The specific time mentioned by the caller (e.g. '10:00', '14:30', '10am') or preference ('morning', 'afternoon', 'any')."
                            }
                        },
                        "required": ["clinician", "date"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "get_clinic_details",
                "description": "Call this tool if the caller asks about the clinic address, opening hours, phone number, or location.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "query_topic": {
                                "type": "string",
                                "enum": ["address", "opening_hours", "contact", "all"],
                                "description": "The specific information requested."
                            }
                        },
                        "required": ["query_topic"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "trigger_emergency_divert",
                "description": "Call this if patient reports acute red-flag symptoms (severe dental hemorrhage, acute facial trauma, airway compromise).",
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

def generate_dentally_calendar_reference(days_ahead: int = 14) -> str:
    now_dublin = datetime.now(DUBLIN_TZ)
    lines = [f"- Current Dublin Time: {now_dublin.strftime('%A, %d %B %Y %H:%M')}"]
    lines.append("- UPCOMING 14-DAY CALENDAR SCHEDULE (Use this EXACT mapping of Day-of-Week to Date):")
    for i in range(days_ahead):
        dt = now_dublin + timedelta(days=i)
        iso = dt.strftime("%Y-%m-%d")
        day_num = dt.day
        if 11 <= day_num <= 13:
            suf = "th"
        else:
            suf = {1: "st", 2: "nd", 3: "rd"}.get(day_num % 10, "th")
        full_str = dt.strftime(f"%A, {day_num}{suf} %B %Y")
        tag = ""
        if i == 0:
            tag = " [TODAY]"
        elif i == 1:
            tag = " [TOMORROW]"
        if dt.weekday() == 6:
            tag += " (CLINIC CLOSED - SUNDAY)"
        lines.append(f"  * {full_str} -> {iso}{tag}")
    return "\n".join(lines)

def build_dentally_system_prompt(caller_phone: str) -> str:
    cal_schedule = generate_dentally_calendar_reference(14)
    matched = KNOWN_PATIENTS.get(caller_phone)
    caller_ctx = (
        f"Caller is known patient '{matched['name']}' (DOB: {matched['dob']})."
        if matched else
        f"Caller ID {caller_phone} is a new patient."
    )

    return (
        "You are Deirdre, automated voice receptionist at Star Dental Care in Clonsilla, Dublin 15, Ireland. "
        "Keep replies strictly to 1 or 2 natural, concise sentences. "
        "NEVER use emojis, emoticons, symbols, markdown, bullet points, or backticks. Speak strictly in plain spoken English words.\n\n"
        f"CALENDAR & DATE REFERENCE:\n"
        f"{cal_schedule}\n\n"
        "- Practice: Star Dental Care, Unit 3 Lidl, Clonsilla Road, Clonsilla, Dublin 15.\n"
        f"- Caller Context: {caller_ctx}\n\n"
        "CLINICAL & FUNCTION-CALLING RULES:\n"
        "1. DATES & CALENDAR LOOKUP: When caller mentions any day (e.g. 'Monday', 'Wednesday', 'Friday', 'the 11th'), consult the UPCOMING CALENDAR SCHEDULE above to find the exact YYYY-MM-DD date. NEVER guess or invent dates. Never book past dates. Always quote the full day and date from the tool instruction.\n"
        "2. LIVE AVAILABILITY LOOKUP: Whenever the caller mentions or asks about ANY time or date, you MUST call `check_dentally_slots` with `clinician` and `date`. Always strictly follow the tool's `availability_verdict` and `instruction`. If the tool says a slot is available, quote it to the caller in natural 12-hour conversational format (e.g. '10 am' or '12:30 pm').\n"
        "3. READ-ONLY TEST MODE: In this phase, we are confirming live practitioner schedules and appointment times. If the caller asks to book, confirm the availability and let them know our reception team is holding the provisional slot.\n"
        "4. CLINIC INFO: If caller asks for address, opening hours, or directions, invoke `get_clinic_details`.\n"
        "5. RED FLAGS: If patient reports severe facial swelling impacting breathing, uncontrollable dental bleeding, or acute trauma, call `trigger_emergency_divert` and say: "
        "'This sounds like an emergency. Please hang up immediately and dial 999 or 112 for an ambulance.'\n"
        "6. TOOL EXECUTION: When you need to call a tool, invoke the tool directly. NEVER write or speak XML tags, parameters, code, or function names (such as <function=...>, <tool_call>, or JSON) in your spoken output. The caller must only hear your natural, spoken English words.\n"
        "7. NATURAL SPOKEN TIMES: When speaking times aloud, always use natural 12-hour conversational format (e.g. say '9 am' instead of '09:00', '9:15 am' instead of '09:15', '1 pm' instead of '13:00', '1:15 pm' instead of '1:15 pm')."
    )

