import os

# Server Connection
SERVER_HOST = os.getenv("STRESS_SERVER_HOST", "127.0.0.1")
SERVER_PORT = int(os.getenv("STRESS_SERVER_PORT", "8998"))
WS_URL = f"ws://{SERVER_HOST}:{SERVER_PORT}/ws/call"
STATUS_URL = f"http://{SERVER_HOST}:{SERVER_PORT}/status"

# Audio Streaming Parameters (matches Silero VAD & Faster-Whisper expectations)
SAMPLE_RATE = 16000
FRAME_SIZE = 512          # 512 samples per frame (32ms at 16kHz)
FRAME_DURATION_SEC = FRAME_SIZE / SAMPLE_RATE  # 0.032s

# Test Scenarios Defaults
DEFAULT_CONCURRENCY = int(os.getenv("STRESS_CONCURRENCY", "5"))
DEFAULT_DURATION_SEC = int(os.getenv("STRESS_DURATION", "60"))
RAMP_UP_DELAY_SEC = float(os.getenv("STRESS_RAMP_UP_DELAY", "2.0"))
CALL_TIMEOUT_SEC = float(os.getenv("STRESS_CALL_TIMEOUT", "45.0"))

# Roster of Simulated Callers (Using Google Calendar GP and Nurse profiles)
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
]

# Conversational Test Scripts
TEST_SCRIPTS = [
    {
        "id": "gp_booking_flow",
        "name": "Standard GP Appointment Booking with Dr. Yousuf",
        "clinician": "Dr. Yousuf",
        "turns": [
            {
                "turn_index": 1,
                "text": "Hi, this is Sean. I'd like to book an appointment with Dr. Yousuf on Monday at 10 am.",
                "expected_tool": "check_calendar_slots"
            },
            {
                "turn_index": 2,
                "text": "Yes, please confirm that booking for me.",
                "expected_tool": "book_calendar_slot"
            }
        ]
    },
    {
        "id": "nurse_check_flow",
        "name": "Nurse Appointment Availability Check with Nurse Kelly",
        "clinician": "Nurse Kelly",
        "turns": [
            {
                "turn_index": 1,
                "text": "Hello, I need to see Nurse Kelly for blood tests on Tuesday morning.",
                "expected_tool": "check_calendar_slots"
            },
            {
                "turn_index": 2,
                "text": "That time sounds good, please go ahead and book it.",
                "expected_tool": "book_calendar_slot"
            }
        ]
    },
    {
        "id": "slot_query_alternative",
        "name": "Alternative Slot Query and Confirmation with Dr. Yousuf",
        "clinician": "Dr. Yousuf",
        "turns": [
            {
                "turn_index": 1,
                "text": "Hi Deirdre, what slots are open for Dr. Yousuf on Wednesday afternoon?",
                "expected_tool": "check_calendar_slots"
            },
            {
                "turn_index": 2,
                "text": "Yes, two o'clock suits me perfectly, please book it.",
                "expected_tool": "book_calendar_slot"
            }
        ]
    }
]

