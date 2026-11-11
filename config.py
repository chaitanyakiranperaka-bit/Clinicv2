import os
from typing import Optional
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
    "+353871112233": {"name": "Patrick Byrne", "dob": "05/11/1975"},
    "+353852223344": {"name": "Ciara Doyle", "dob": "19/04/1995"},
    "+353893334455": {"name": "Liam O'Connor", "dob": "30/01/1988"},
    "+353874445566": {"name": "Siobhan Walsh", "dob": "12/09/1984"},
    "+353865556677": {"name": "Conor Ryan", "dob": "03/07/1992"},
    "+353876667788": {"name": "Niamh O'Brien", "dob": "25/12/1986"},
    "+353857778899": {"name": "Eoin McCarthy", "dob": "17/06/1991"},
    "+353898889900": {"name": "Roisin Gallagher", "dob": "08/02/1989"},
    "+353871122334": {"name": "Colm Hayes", "dob": "11/05/1981"},
    "+353862233445": {"name": "Fiona Brennan", "dob": "28/07/1993"},
    "+353853344556": {"name": "Declan Murray", "dob": "04/10/1979"},
    "+353894455667": {"name": "Sinead Burke", "dob": "15/01/1987"},
    "+353875566778": {"name": "Brendan Clarke", "dob": "19/09/1983"},
    "+353866677889": {"name": "Maeve Kavanagh", "dob": "02/06/1994"},
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
                "description": "Call this tool whenever checking appointment availability OR whenever caller mentions ANY time (e.g. '10:30', '1030', 'morning', 'after 2pm'). Pass the caller's time into `time_preference`.",
                "inputSchema": {
                    "json": {
                        "type": "object",
                        "properties": {
                            "clinician": {"type": "string", "enum": ["Dr. Yousuf", "Dentist Shailaja", "Nurse Kelly"]},
                            "date": {"type": "string", "description": "Date in YYYY-MM-DD format."},
                            "time_preference": {"type": "string", "description": "The specific time mentioned by the caller (e.g. '10:30', '1030', '14:30', '10am') or preference ('morning', 'afternoon')."}
                        },
                        "required": ["clinician", "date"]
                    }
                }
            }
        },
        {
            "toolSpec": {
                "name": "book_calendar_slot",
                "description": "Call this tool ONLY AFTER you have explicitly quoted the exact clinician, date, and slot time to the caller and the caller has confirmed. You MUST provide the exact agreed `slot_time` (e.g. '10:00', '14:30') that was quoted to the caller. Never omit `slot_time`.",
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

def generate_calendar_reference(days_ahead: int = 14) -> str:
    now_dublin = datetime.now(DUBLIN_TZ)
    lines = [
        f"- Current Dublin Time: {now_dublin.strftime('%A, %d %B %Y %H:%M')}",
        f"- TODAY IS {now_dublin.strftime('%A, %d %B %Y')}. Any time earlier than {now_dublin.strftime('%H:%M')} today has ALREADY PASSED and CANNOT be booked."
    ]
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

def normalize_phone(phone: str) -> str:
    """Normalizes phone number string, handling URL query artifact where '+' was decoded as ' '."""
    if not phone:
        return ""
    cleaned = phone.strip()
    return cleaned if cleaned.startswith("+") else "+" + cleaned

def get_known_patient(phone: str) -> Optional[dict]:
    """Retrieves patient profile matching phone number regardless of leading '+' or space."""
    if not phone:
        return None
    p = normalize_phone(phone)
    if p in KNOWN_PATIENTS:
        return KNOWN_PATIENTS[p]
    without_plus = p.lstrip("+")
    for k, v in KNOWN_PATIENTS.items():
        if k.lstrip("+") == without_plus:
            return v
    return None

def build_system_prompt(caller_phone: str) -> str:
    cal_schedule = generate_calendar_reference(14)
    matched = get_known_patient(caller_phone)
    caller_ctx = (
        f"Caller is verified enrolled patient '{matched['name']}' (DOB: {matched['dob']}). When they select or agree to a slot, immediately execute book_calendar_slot using their enrolled details."
        if matched else
        f"Caller ID {caller_phone} is new. Ask for Full Name and DOB before booking."
    )

    return (
        "You are Deirdre, automated voice receptionist at Star Dental & GP Clinic in Clonsilla, Dublin 15, Ireland. "
        "Keep replies strictly to 1 or 2 natural, concise sentences. "
        "NEVER use emojis, emoticons, symbols, markdown, bullet points, or backticks. Speak strictly in plain spoken English words.\n\n"
        f"CALENDAR & DATE REFERENCE:\n"
        f"{cal_schedule}\n\n"
        f"- Operating Hours: Monday to Saturday 09:00 to 17:00. The clinic is CLOSED on Sundays (direct urgent issues to D-Doc/K-Doc).\n"
        f"- Caller Context: {caller_ctx}\n\n"
        "CLINICAL & FUNCTION-CALLING RULES:\n"
        "1. DATES & CALENDAR LOOKUP: When caller mentions any day (e.g. 'Monday', 'Tuesday', 'Friday', 'the 9th', '12th Nov'), consult the UPCOMING CALENDAR SCHEDULE above to find the exact YYYY-MM-DD date. NEVER guess or invent dates. Never book past dates or past times earlier today. Always quote the full day and date from the tool instruction (e.g. 'Friday, 13th November').\n"
        "2. AVAILABILITY: Whenever the caller mentions or asks about ANY time (e.g. '1030', '10:30', 'afternoon', 'You have a 1030 slot'), you MUST call `check_calendar_slots` with `time_preference` set to that time. Always strictly follow the tool's `availability_verdict` and `instruction`. If the tool says a slot is AVAILABLE, it IS available — never tell the caller it is unavailable!\n"
        "3. EXPLICIT CONFIRMATION BEFORE BOOKING: You MUST NEVER call `book_calendar_slot` without getting explicit confirmation first. "
        "When an available time is identified, explicitly quote the clinician, date, and time to the caller and ask for confirmation: "
        "'I have [Date] at [Time] available with [Clinician]. Would you like me to book that for you?' "
        "When the caller explicitly responds with confirmation (such as 'Yes', 'Please book it', 'Go ahead'), invoke `book_calendar_slot` passing the EXACT agreed clinician, date, and slot_time (e.g. '10:00', '14:30'). Never omit slot_time.\n"
        "4. RED FLAGS: If patient reports chest pain, breathlessness, stroke signs (FAST), or heavy bleeding, call `trigger_emergency_divert` and say: "
        "'This sounds like an emergency. Please hang up immediately and dial 999 or 112 for an ambulance.'\n"
        "5. ROUTING: Dr. Yousuf = Routine GP; Dentist Shailaja = Dental; Nurse Kelly = Bloods, smears, vaccines.\n"
        "6. TOOL EXECUTION: When you need to call a tool, invoke the tool directly. NEVER write or speak XML tags, parameters, code, or function names (such as <function=...>, <tool_call>, or JSON) in your spoken output. The caller must only hear your natural, spoken English words.\n"
        "7. NATURAL SPOKEN TIMES: When speaking times aloud, always use natural 12-hour conversational format (e.g. say '9 am' instead of '09:00', '9:15 am' instead of '09:15', '1 pm' instead of '13:00', '1:15 pm' instead of '13:15'). Never speak 24-hour military times or leading zeros.\n"
        "8. PAST TIME PROHIBITION: NEVER offer, suggest, quote, or attempt to book any slot that has already passed earlier today (before current Dublin time) or any past date. If a caller asks for a time that has already passed today, or if all slots for today are full, politely inform them that this time has already passed, and offer future open times today or tomorrow/next week. NEVER hallucinate or invent past times."
    )
