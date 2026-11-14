import os
from typing import Optional
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

DUBLIN_TZ = ZoneInfo("Europe/Dublin")
AWS_REGION = os.getenv("AWS_DEFAULT_REGION", "eu-west-1")
BEDROCK_MODEL_ID = os.getenv("BEDROCK_MODEL_ID", "qwen.qwen3-coder-30b-a3b-v1:0")
GOOGLE_CALENDAR_ID = os.getenv("GOOGLE_CALENDAR_ID", "chaitanyakiran.peraka@gmail.com")

def _resolve_service_account_path() -> str:
    env_path = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")
    if env_path and os.path.exists(env_path):
        return env_path
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_sa = os.path.join(base_dir, "service_account.json")
    if os.path.exists(project_sa):
        return project_sa
    home_sa = "/home/ubuntu/service_account.json"
    if os.path.exists(home_sa):
        return home_sa
    cwd_sa = os.path.abspath("service_account.json")
    if os.path.exists(cwd_sa):
        return cwd_sa
    return home_sa

SERVICE_ACCOUNT_FILE = _resolve_service_account_path()

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
    "+353871000001": {"name": "Cillian Murphy", "dob": "25/05/1976"},
    "+353871000002": {"name": "Saoirse Ronan", "dob": "12/04/1994"},
    "+353871000003": {"name": "Paul Mescal", "dob": "02/02/1996"},
    "+353871000004": {"name": "Barry Keoghan", "dob": "18/10/1992"},
    "+353871000005": {"name": "Colin Farrell", "dob": "31/05/1976"},
    "+353871000006": {"name": "Domhnall Gleeson", "dob": "12/05/1983"},
    "+353871000007": {"name": "Andrew Scott", "dob": "21/10/1976"},
    "+353871000008": {"name": "Ruth Negga", "dob": "07/01/1982"},
    "+353871000009": {"name": "Kerry Condon", "dob": "09/01/1983"},
    "+353871000010": {"name": "Aisling Bea", "dob": "16/03/1984"},
    "+353871000011": {"name": "Graham Norton", "dob": "04/04/1963"},
    "+353871000012": {"name": "Dara O Briain", "dob": "04/02/1972"},
    "+353871000013": {"name": "Brian O'Driscoll", "dob": "21/01/1979"},
    "+353871000014": {"name": "Katie Taylor", "dob": "02/07/1986"},
    "+353871000015": {"name": "Johnny Sexton", "dob": "11/07/1985"},
    "+353871000016": {"name": "Roy Keane", "dob": "10/08/1971"},
    "+353871000017": {"name": "Robbie Keane", "dob": "08/07/1980"},
    "+353871000018": {"name": "Shane Lowry", "dob": "02/04/1987"},
    "+353871000019": {"name": "Rory McIlroy", "dob": "04/05/1989"},
    "+353871000020": {"name": "Padraig Harrington", "dob": "31/08/1971"},
    "+353871000021": {"name": "Niamh Kavanagh", "dob": "13/02/1968"},
    "+353871000022": {"name": "Sinead O'Connor", "dob": "08/12/1966"},
    "+353871000023": {"name": "Enya Brennan", "dob": "17/05/1961"},
    "+353871000024": {"name": "Hozier Byrne", "dob": "17/03/1990"},
    "+353871000025": {"name": "Niall Horan", "dob": "13/09/1993"},
    "+353871000026": {"name": "Ronan Keating", "dob": "03/03/1977"},
    "+353871000027": {"name": "Aidan Turner", "dob": "19/06/1983"},
    "+353871000028": {"name": "Pierce Brosnan", "dob": "16/05/1953"},
    "+353871000029": {"name": "Brendan Gleeson", "dob": "29/03/1955"},
    "+353871000030": {"name": "Liam Neeson", "dob": "07/06/1952"},
    "+353871000031": {"name": "Kenneth Branagh", "dob": "10/12/1960"},
    "+353871000032": {"name": "Jamie Dornan", "dob": "01/05/1982"},
    "+353871000033": {"name": "Robert Sheehan", "dob": "07/01/1988"},
    "+353871000034": {"name": "Jack Reynor", "dob": "23/01/1992"},
    "+353871000035": {"name": "Domhnall O'Donoghue", "dob": "07/07/1980"},
    "+353871000036": {"name": "Mark Sheehan", "dob": "29/10/1976"},
    "+353871000037": {"name": "Glen Hansard", "dob": "21/04/1970"},
    "+353871000038": {"name": "Damien Rice", "dob": "07/12/1973"},
    "+353871000039": {"name": "David Gray", "dob": "13/06/1968"},
    "+353871000040": {"name": "Van Morrison", "dob": "31/08/1945"},
    "+353871000041": {"name": "Gavin James", "dob": "05/07/1991"},
    "+353871000042": {"name": "Dermot Kennedy", "dob": "13/12/1991"},
    "+353871000043": {"name": "James Vincent McMorrow", "dob": "14/01/1983"},
    "+353871000044": {"name": "Mick Flannery", "dob": "28/11/1983"},
    "+353871000045": {"name": "Fionn Whitehead", "dob": "18/07/1997"},
    "+353871000046": {"name": "Barry Ward", "dob": "20/09/1980"},
    "+353871000047": {"name": "Chris O'Dowd", "dob": "09/10/1979"},
    "+353871000048": {"name": "Peter Coonan", "dob": "02/10/1984"},
    "+353871000049": {"name": "Killian Scott", "dob": "06/07/1985"},
    "+353871000050": {"name": "Allen Leech", "dob": "18/05/1981"},
    "+353871000051": {"name": "Aidan Gillen", "dob": "24/04/1968"},
    "+353871000052": {"name": "Liam Cunningham", "dob": "02/06/1961"},
    "+353871000053": {"name": "Colm Meaney", "dob": "30/05/1953"},
    "+353871000054": {"name": "David O'Hara", "dob": "09/07/1965"},
    "+353871000055": {"name": "Stuart Townsend", "dob": "15/12/1972"},
    "+353871000056": {"name": "Jonathan Rhys Meyers", "dob": "27/07/1977"},
    "+353871000057": {"name": "Milo O'Shea", "dob": "02/06/1926"},
    "+353871000058": {"name": "Gabriel Byrne", "dob": "12/05/1950"},
    "+353871000059": {"name": "Stephen Rea", "dob": "31/10/1946"},
    "+353871000060": {"name": "Ciaran Hinds", "dob": "09/02/1953"},
    "+353871000061": {"name": "Michael McElhatton", "dob": "12/09/1963"},
    "+353871000062": {"name": "Conleth Hill", "dob": "24/11/1964"},
    "+353871000063": {"name": "Jack Gleeson", "dob": "20/05/1992"},
    "+353871000064": {"name": "Art Parkinson", "dob": "19/10/2001"},
    "+353871000065": {"name": "Daniel Day-Lewis", "dob": "29/04/1957"},
    "+353871000066": {"name": "Barry McGuigan", "dob": "28/02/1961"},
    "+353871000067": {"name": "Steve Collins", "dob": "21/07/1964"},
    "+353871000068": {"name": "Bernard Dunne", "dob": "12/02/1980"},
    "+353871000069": {"name": "Carl Frampton", "dob": "21/02/1987"},
    "+353871000070": {"name": "Michael Conlan", "dob": "19/11/1991"},
    "+353871000071": {"name": "Kellie Harrington", "dob": "11/12/1989"},
    "+353871000072": {"name": "Ken Doherty", "dob": "17/09/1969"},
    "+353871000073": {"name": "Dennis Taylor", "dob": "19/01/1949"},
    "+353871000074": {"name": "Tony McCoy", "dob": "04/05/1974"},
    "+353871000075": {"name": "Ruby Walsh", "dob": "14/05/1979"},
    "+353871000076": {"name": "Paul Carberry", "dob": "14/08/1974"},
    "+353871000077": {"name": "Davy Russell", "dob": "27/06/1979"},
    "+353871000078": {"name": "Rachael Blackmore", "dob": "11/07/1989"},
    "+353871000079": {"name": "Sonny Bill Williams", "dob": "03/08/1985"},
    "+353871000080": {"name": "Paul O'Connell", "dob": "20/10/1979"},
    "+353871000081": {"name": "Ronan O'Gara", "dob": "07/03/1977"},
    "+353871000082": {"name": "Peter O'Mahony", "dob": "17/09/1989"},
    "+353871000083": {"name": "Conor Murray", "dob": "20/04/1989"},
    "+353871000084": {"name": "Tadhg Furlong", "dob": "14/11/1992"},
    "+353871000085": {"name": "James Ryan", "dob": "24/07/1996"},
    "+353871000086": {"name": "Caelan Doris", "dob": "02/04/1998"},
    "+353871000087": {"name": "Josh van der Flier", "dob": "25/04/1993"},
    "+353871000088": {"name": "Garry Ringrose", "dob": "26/01/1995"},
    "+353871000089": {"name": "Robbie Henshaw", "dob": "12/06/1993"},
    "+353871000090": {"name": "Mack Hansen", "dob": "27/03/1998"},
    "+353871000091": {"name": "Hugo Keenan", "dob": "18/06/1996"},
    "+353871000092": {"name": "Dan Sheehan", "dob": "17/09/1998"},
    "+353871000093": {"name": "Andrew Porter", "dob": "17/01/1996"},
    "+353871000094": {"name": "Finlay Bealham", "dob": "09/10/1991"},
    "+353871000095": {"name": "Jamison Gibson-Park", "dob": "23/02/1992"},
    "+353871000096": {"name": "Bundee Aki", "dob": "07/04/1990"},
    "+353871000097": {"name": "Cian Healy", "dob": "07/10/1987"},
    "+353871000098": {"name": "Keith Earls", "dob": "02/10/1987"},
    "+353871000099": {"name": "Simon Zebo", "dob": "16/03/1990"},
    "+353871000100": {"name": "Denis Leamy", "dob": "27/11/1981"},
    "+353871000101": {"name": "Donncha O'Callaghan", "dob": "24/03/1979"},
    "+353871000102": {"name": "David Wallace", "dob": "08/07/1976"},
    "+353871000103": {"name": "Gordon D'Arcy", "dob": "10/02/1980"},
    "+353871000104": {"name": "Geordan Murphy", "dob": "19/04/1978"},
    "+353871000105": {"name": "Girvan Dempsey", "dob": "02/10/1975"},
    "+353871000106": {"name": "Malcolm O'Kelly", "dob": "19/07/1974"},
    "+353871000107": {"name": "Shane Horgan", "dob": "18/07/1978"},
    "+353871000108": {"name": "Denis Hickie", "dob": "13/02/1976"},
    "+353871000109": {"name": "John Hayes", "dob": "02/11/1973"},
    "+353871000110": {"name": "Peter Clohessy", "dob": "22/03/1966"},
    "+353871000111": {"name": "Mick Galwey", "dob": "08/10/1966"},
    "+353871000112": {"name": "Anthony Foley", "dob": "16/10/1973"},
    "+353871000113": {"name": "Willie John McBride", "dob": "06/06/1940"},
    "+353871000114": {"name": "Mike Gibson", "dob": "03/12/1942"},
    "+353871000115": {"name": "Fergus Slattery", "dob": "12/02/1949"},
    "+353871000116": {"name": "Ollie Campbell", "dob": "05/03/1954"},
    "+353871000117": {"name": "Ciaran Fitzgerald", "dob": "04/06/1952"},
    "+353871000118": {"name": "Moss Keane", "dob": "27/07/1948"},
    "+353871000119": {"name": "Tony Ward", "dob": "08/10/1954"},
    "+353871000120": {"name": "Hugo MacNeill", "dob": "16/09/1958"},
    "+353871000121": {"name": "Michael Bradley", "dob": "17/11/1962"},
    "+353871000122": {"name": "Brendan Mullin", "dob": "30/10/1963"},
    "+353871000123": {"name": "Keith Wood", "dob": "27/01/1972"},
    "+353871000124": {"name": "Conor O'Shea", "dob": "21/10/1970"},
    "+353871000125": {"name": "Eric Elwood", "dob": "26/02/1969"},
    "+353871000126": {"name": "Victor Costello", "dob": "23/10/1970"},
    "+353871000127": {"name": "David Humphreys", "dob": "10/09/1971"},
    "+353871000128": {"name": "Paddy Wallace", "dob": "27/08/1979"},
    "+353871000129": {"name": "Marcus Horan", "dob": "07/09/1977"},
    "+353871000130": {"name": "Jerry Flannery", "dob": "17/10/1978"},
    "+353871000131": {"name": "Alan Quinlan", "dob": "24/07/1974"},
    "+353871000132": {"name": "Stephen Ferris", "dob": "02/08/1985"},
    "+353871000133": {"name": "Luke Fitzgerald", "dob": "13/09/1987"},
    "+353871000134": {"name": "Tommy Bowe", "dob": "22/02/1984"},
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
