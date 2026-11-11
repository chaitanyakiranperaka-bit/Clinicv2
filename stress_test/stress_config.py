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
    {"phone": "+353871000001", "name": "Cillian Murphy", "dob": "25/05/1976", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000002", "name": "Saoirse Ronan", "dob": "12/04/1994", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000003", "name": "Paul Mescal", "dob": "02/02/1996", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000004", "name": "Barry Keoghan", "dob": "18/10/1992", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000005", "name": "Colin Farrell", "dob": "31/05/1976", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000006", "name": "Domhnall Gleeson", "dob": "12/05/1983", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000007", "name": "Andrew Scott", "dob": "21/10/1976", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000008", "name": "Ruth Negga", "dob": "07/01/1982", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000009", "name": "Kerry Condon", "dob": "09/01/1983", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000010", "name": "Aisling Bea", "dob": "16/03/1984", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000011", "name": "Graham Norton", "dob": "04/04/1963", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000012", "name": "Dara O Briain", "dob": "04/02/1972", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000013", "name": "Brian O'Driscoll", "dob": "21/01/1979", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000014", "name": "Katie Taylor", "dob": "02/07/1986", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000015", "name": "Johnny Sexton", "dob": "11/07/1985", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000016", "name": "Roy Keane", "dob": "10/08/1971", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000017", "name": "Robbie Keane", "dob": "08/07/1980", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000018", "name": "Shane Lowry", "dob": "02/04/1987", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000019", "name": "Rory McIlroy", "dob": "04/05/1989", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000020", "name": "Padraig Harrington", "dob": "31/08/1971", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000021", "name": "Niamh Kavanagh", "dob": "13/02/1968", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000022", "name": "Sinead O'Connor", "dob": "08/12/1966", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000023", "name": "Enya Brennan", "dob": "17/05/1961", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000024", "name": "Hozier Byrne", "dob": "17/03/1990", "clinician": "Dr. Yousuf", "category": "Routine GP"},
]

# 40 Distinct Conversational Test Scripts Across Doctors, Nurses, Days, and Slots
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
    },
    {
        "id": "script_17",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s17_t1", "text": "Hi, can I book an appointment with Dr. Yousuf on Monday at 9:15 am?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_18",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s18_t1", "text": "Hello Deirdre, I need to see Nurse Kelly on Monday morning at 10:30 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_19",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s19_t1", "text": "Hi Deirdre, could I see Dr. Yousuf on Monday at 11:45 am?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_20",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s20_t1", "text": "Hello, can I book Nurse Kelly on Monday afternoon at 2:15 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_21",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s21_t1", "text": "Hi, I need an appointment with Dr. Yousuf on Monday at 3:15 pm."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_22",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s22_t1", "text": "Hello, is Nurse Kelly open on Monday afternoon at 4:15 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_23",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s23_t1", "text": "Hi Deirdre, can I book Dr. Yousuf on Tuesday morning at 9:15 am?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_24",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s24_t1", "text": "Hello, I would like to see Nurse Kelly on Tuesday at 10:45 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_25",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s25_t1", "text": "Hi, can I see Dr. Yousuf on Tuesday morning at 11:45 am?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_26",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s26_t1", "text": "Hello Deirdre, is Nurse Kelly free on Tuesday afternoon at 3:15 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_27",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s27_t1", "text": "Hi, I need an appointment with Dr. Yousuf on Tuesday at 3:45 pm."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_28",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s28_t1", "text": "Hello, could I see Dr. Yousuf on Tuesday afternoon at 4:30 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_29",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s29_t1", "text": "Hi Deirdre, I would like to book Nurse Kelly on Wednesday morning at 9:15 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_30",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s30_t1", "text": "Hello, can I see Nurse Kelly on Wednesday morning at 11:15 am?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_31",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s31_t1", "text": "Hi, can I book Dr. Yousuf on Wednesday afternoon at 2:15 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_32",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s32_t1", "text": "Hello Deirdre, I need to see Dr. Yousuf on Wednesday at 3:30 pm."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_33",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s33_t1", "text": "Hi, could I book Dr. Yousuf on Wednesday afternoon at 4:15 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_34",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s34_t1", "text": "Hello, I would like to see Nurse Kelly on Thursday morning at 9:15 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_35",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s35_t1", "text": "Hi Deirdre, can I book Dr. Yousuf on Thursday morning at 11:15 am?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_36",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s36_t1", "text": "Hello, is Nurse Kelly available on Thursday afternoon at 2:30 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_37",
        "clinician": "Nurse Kelly",
        "turns": [
            {"turn_index": 1, "turn_key": "s37_t1", "text": "Hi, could I book Nurse Kelly on Thursday afternoon at 4:30 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_38",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s38_t1", "text": "Hello Deirdre, can I see Dr. Yousuf on Friday morning at 9:15 am?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_39",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s39_t1", "text": "Hi, I need an appointment with Dr. Yousuf on Friday at 10:15 am."},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    },
    {
        "id": "script_40",
        "clinician": "Dr. Yousuf",
        "turns": [
            {"turn_index": 1, "turn_key": "s40_t1", "text": "Hello, can I book Dr. Yousuf on Friday afternoon at 4:15 pm?"},
            {"turn_index": 2, "turn_key": "confirm_std", "text": "Yes, please confirm that booking for me."}
        ]
    }
]
