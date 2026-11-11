import os
from pathlib import Path

# Server Connection Settings
SERVER_HOST = os.getenv("STRESS_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("STRESS_PORT", "8998"))
WS_HOST = SERVER_HOST
WS_PORT = SERVER_PORT
WS_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}/ws/call"
STATUS_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/status"

# Audio Streaming Parameters (Native to Faster-Whisper & Silero VAD)
SAMPLE_RATE = 16000
FRAME_SIZE = 512              # 512 float32 samples = 32ms
FRAME_DURATION_SEC = FRAME_SIZE / SAMPLE_RATE

# Concurrency & Timeout Defaults
DEFAULT_CONCURRENCY = int(os.getenv("STRESS_CONCURRENCY", "5"))
DEFAULT_DURATION_SEC = int(os.getenv("STRESS_DURATION", "60"))
RAMP_UP_DELAY_SEC = float(os.getenv("STRESS_RAMP_UP_DELAY", "2.0"))
CALL_TIMEOUT_SEC = float(os.getenv("STRESS_CALL_TIMEOUT", "45.0"))

# Roster of 16 Enrolled Clinic Callers (Verified in config.py)
SIMULATED_CALLERS = [
    {"phone": "+353871234567", "name": "Sean Murphy", "dob": "14/03/1982", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353869876543", "name": "Aoife Kelly", "dob": "22/08/1990", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871112233", "name": "Patrick Byrne", "dob": "05/11/1975", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353852223344", "name": "Ciara Doyle", "dob": "19/04/1995", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353893334455", "name": "Liam O'Connor", "dob": "30/01/1988", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353874445566", "name": "Siobhan Walsh", "dob": "12/09/1984", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353865556677", "name": "Conor Ryan", "dob": "03/07/1992", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353876667788", "name": "Niamh O'Brien", "dob": "25/12/1986", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353857778899", "name": "Eoin McCarthy", "dob": "17/06/1991", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353898889900", "name": "Roisin Gallagher", "dob": "08/02/1989", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871122334", "name": "Colm Hayes", "dob": "11/05/1981", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353862233445", "name": "Fiona Brennan", "dob": "28/07/1993", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353853344556", "name": "Declan Murray", "dob": "04/10/1979", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353894455667", "name": "Sinead Burke", "dob": "15/01/1987", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353875566778", "name": "Brendan Clarke", "dob": "19/09/1983", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353866677889", "name": "Maeve Kavanagh", "dob": "02/06/1994", "clinician": "Dr. Yousuf", "category": "Routine GP"},
]

# 16 Distinct Conversational Test Scripts Across Doctors, Nurses, Days, and Slots
TEST_SCRIPTS = [
    {
        "id": "script_01",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s01_t1", "text": "Hi, this is Sean. I'd like to book an appointment with Dr. Yousuf on Monday at 10 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_02",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s02_t1", "text": "Hello, I need to see Nurse Kelly for blood tests on Tuesday morning at 9:30 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "That time sounds good, please go ahead and book it."}
        ]
    },
    {
        "id": "script_03",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s03_t1", "text": "Hi Deirdre, can I see Dr. Yousuf on Tuesday at 11 am?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_04",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s04_t1", "text": "Hello, I'd like to book Nurse Kelly on Wednesday morning at 10 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "That time works, please go ahead and book it."}
        ]
    },
    {
        "id": "script_05",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s05_t1", "text": "Hi Deirdre, what slots are open for Dr. Yousuf on Wednesday afternoon?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, two o'clock suits me perfectly, please book it."}
        ]
    },
    {
        "id": "script_06",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s06_t1", "text": "Hello, I'd like an appointment with Dr. Yousuf on Thursday morning at 10:30 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please book that for me."}
        ]
    },
    {
        "id": "script_07",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s07_t1", "text": "Hi, is Dr. Yousuf open on Thursday afternoon at 3 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, three o'clock suits me, please book it."}
        ]
    },
    {
        "id": "script_08",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s08_t1", "text": "Hello, I need to see Nurse Kelly on Friday morning at 11 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "That time is perfect, please book it."}
        ]
    },
    {
        "id": "script_09",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s09_t1", "text": "Hi, can I book Dr. Yousuf on Friday afternoon at 2:30 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_10",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s10_t1", "text": "Hello Deirdre, can I book Dr. Yousuf on Monday afternoon at 2:30 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please book that for me."}
        ]
    },
    {
        "id": "script_11",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s11_t1", "text": "Hi, I'd like to see Nurse Kelly on Tuesday afternoon at 2 pm."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, that suits me, please book it."}
        ]
    },
    {
        "id": "script_12",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s12_t1", "text": "Hello, can I book an appointment with Dr. Yousuf on Wednesday at 11:30 am?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_13",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s13_t1", "text": "Hi Deirdre, I need to see Dr. Yousuf on Thursday at 4 pm."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please go ahead and book that."}
        ]
    },
    {
        "id": "script_14",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s14_t1", "text": "Hello, is Nurse Kelly available on Friday morning at 9:45 am?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, that time works, please book it."}
        ]
    },
    {
        "id": "script_15",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s15_t1", "text": "Hi, can I book Dr. Yousuf on Friday afternoon at 3:30 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking."}
        ]
    },
    {
        "id": "script_16",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s16_t1", "text": "Hello Deirdre, I would like to see Dr. Yousuf on Monday at 11 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    }
]
