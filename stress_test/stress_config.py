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
CALL_TIMEOUT_SEC = float(os.getenv("STRESS_CALL_TIMEOUT", "65.0"))

# Roster of 150 Enrolled Clinic Callers (Verified in config.py)
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
    {"phone": "+353871000025", "name": "Niall Horan", "dob": "13/09/1993", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000026", "name": "Ronan Keating", "dob": "03/03/1977", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000027", "name": "Aidan Turner", "dob": "19/06/1983", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000028", "name": "Pierce Brosnan", "dob": "16/05/1953", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000029", "name": "Brendan Gleeson", "dob": "29/03/1955", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000030", "name": "Liam Neeson", "dob": "07/06/1952", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000031", "name": "Kenneth Branagh", "dob": "10/12/1960", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000032", "name": "Jamie Dornan", "dob": "01/05/1982", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000033", "name": "Robert Sheehan", "dob": "07/01/1988", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000034", "name": "Jack Reynor", "dob": "23/01/1992", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000035", "name": "Domhnall O'Donoghue", "dob": "07/07/1980", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000036", "name": "Mark Sheehan", "dob": "29/10/1976", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000037", "name": "Glen Hansard", "dob": "21/04/1970", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000038", "name": "Damien Rice", "dob": "07/12/1973", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000039", "name": "David Gray", "dob": "13/06/1968", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000040", "name": "Van Morrison", "dob": "31/08/1945", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000041", "name": "Gavin James", "dob": "05/07/1991", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000042", "name": "Dermot Kennedy", "dob": "13/12/1991", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000043", "name": "James Vincent McMorrow", "dob": "14/01/1983", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000044", "name": "Mick Flannery", "dob": "28/11/1983", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000045", "name": "Fionn Whitehead", "dob": "18/07/1997", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000046", "name": "Barry Ward", "dob": "20/09/1980", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000047", "name": "Chris O'Dowd", "dob": "09/10/1979", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000048", "name": "Peter Coonan", "dob": "02/10/1984", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000049", "name": "Killian Scott", "dob": "06/07/1985", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000050", "name": "Allen Leech", "dob": "18/05/1981", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000051", "name": "Aidan Gillen", "dob": "24/04/1968", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000052", "name": "Liam Cunningham", "dob": "02/06/1961", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000053", "name": "Colm Meaney", "dob": "30/05/1953", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000054", "name": "David O'Hara", "dob": "09/07/1965", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000055", "name": "Stuart Townsend", "dob": "15/12/1972", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000056", "name": "Jonathan Rhys Meyers", "dob": "27/07/1977", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000057", "name": "Milo O'Shea", "dob": "02/06/1926", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000058", "name": "Gabriel Byrne", "dob": "12/05/1950", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000059", "name": "Stephen Rea", "dob": "31/10/1946", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000060", "name": "Ciaran Hinds", "dob": "09/02/1953", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000061", "name": "Michael McElhatton", "dob": "12/09/1963", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000062", "name": "Conleth Hill", "dob": "24/11/1964", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000063", "name": "Jack Gleeson", "dob": "20/05/1992", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000064", "name": "Art Parkinson", "dob": "19/10/2001", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000065", "name": "Daniel Day-Lewis", "dob": "29/04/1957", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000066", "name": "Barry McGuigan", "dob": "28/02/1961", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000067", "name": "Steve Collins", "dob": "21/07/1964", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000068", "name": "Bernard Dunne", "dob": "12/02/1980", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000069", "name": "Carl Frampton", "dob": "21/02/1987", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000070", "name": "Michael Conlan", "dob": "19/11/1991", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000071", "name": "Kellie Harrington", "dob": "11/12/1989", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000072", "name": "Ken Doherty", "dob": "17/09/1969", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000073", "name": "Dennis Taylor", "dob": "19/01/1949", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000074", "name": "Tony McCoy", "dob": "04/05/1974", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000075", "name": "Ruby Walsh", "dob": "14/05/1979", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000076", "name": "Paul Carberry", "dob": "14/08/1974", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000077", "name": "Davy Russell", "dob": "27/06/1979", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000078", "name": "Rachael Blackmore", "dob": "11/07/1989", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000079", "name": "Sonny Bill Williams", "dob": "03/08/1985", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000080", "name": "Paul O'Connell", "dob": "20/10/1979", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000081", "name": "Ronan O'Gara", "dob": "07/03/1977", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000082", "name": "Peter O'Mahony", "dob": "17/09/1989", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000083", "name": "Conor Murray", "dob": "20/04/1989", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000084", "name": "Tadhg Furlong", "dob": "14/11/1992", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000085", "name": "James Ryan", "dob": "24/07/1996", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000086", "name": "Caelan Doris", "dob": "02/04/1998", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000087", "name": "Josh van der Flier", "dob": "25/04/1993", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000088", "name": "Garry Ringrose", "dob": "26/01/1995", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000089", "name": "Robbie Henshaw", "dob": "12/06/1993", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000090", "name": "Mack Hansen", "dob": "27/03/1998", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000091", "name": "Hugo Keenan", "dob": "18/06/1996", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000092", "name": "Dan Sheehan", "dob": "17/09/1998", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000093", "name": "Andrew Porter", "dob": "17/01/1996", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000094", "name": "Finlay Bealham", "dob": "09/10/1991", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000095", "name": "Jamison Gibson-Park", "dob": "23/02/1992", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000096", "name": "Bundee Aki", "dob": "07/04/1990", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000097", "name": "Cian Healy", "dob": "07/10/1987", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000098", "name": "Keith Earls", "dob": "02/10/1987", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000099", "name": "Simon Zebo", "dob": "16/03/1990", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000100", "name": "Denis Leamy", "dob": "27/11/1981", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000101", "name": "Donncha O'Callaghan", "dob": "24/03/1979", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000102", "name": "David Wallace", "dob": "08/07/1976", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000103", "name": "Gordon D'Arcy", "dob": "10/02/1980", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000104", "name": "Geordan Murphy", "dob": "19/04/1978", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000105", "name": "Girvan Dempsey", "dob": "02/10/1975", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000106", "name": "Malcolm O'Kelly", "dob": "19/07/1974", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000107", "name": "Shane Horgan", "dob": "18/07/1978", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000108", "name": "Denis Hickie", "dob": "13/02/1976", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000109", "name": "John Hayes", "dob": "02/11/1973", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000110", "name": "Peter Clohessy", "dob": "22/03/1966", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000111", "name": "Mick Galwey", "dob": "08/10/1966", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000112", "name": "Anthony Foley", "dob": "16/10/1973", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000113", "name": "Willie John McBride", "dob": "06/06/1940", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000114", "name": "Mike Gibson", "dob": "03/12/1942", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000115", "name": "Fergus Slattery", "dob": "12/02/1949", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000116", "name": "Ollie Campbell", "dob": "05/03/1954", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000117", "name": "Ciaran Fitzgerald", "dob": "04/06/1952", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000118", "name": "Moss Keane", "dob": "27/07/1948", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000119", "name": "Tony Ward", "dob": "08/10/1954", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000120", "name": "Hugo MacNeill", "dob": "16/09/1958", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000121", "name": "Michael Bradley", "dob": "17/11/1962", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000122", "name": "Brendan Mullin", "dob": "30/10/1963", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000123", "name": "Keith Wood", "dob": "27/01/1972", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000124", "name": "Conor O'Shea", "dob": "21/10/1970", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000125", "name": "Eric Elwood", "dob": "26/02/1969", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000126", "name": "Victor Costello", "dob": "23/10/1970", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000127", "name": "David Humphreys", "dob": "10/09/1971", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000128", "name": "Paddy Wallace", "dob": "27/08/1979", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000129", "name": "Marcus Horan", "dob": "07/09/1977", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000130", "name": "Jerry Flannery", "dob": "17/10/1978", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000131", "name": "Alan Quinlan", "dob": "24/07/1974", "clinician": "Dr. Yousuf", "category": "Routine GP"},
    {"phone": "+353871000132", "name": "Stephen Ferris", "dob": "02/08/1985", "clinician": "Dentist Shailaja", "category": "Dental"},
    {"phone": "+353871000133", "name": "Luke Fitzgerald", "dob": "13/09/1987", "clinician": "Nurse Kelly", "category": "Nurse Appointment"},
    {"phone": "+353871000134", "name": "Tommy Bowe", "dob": "22/02/1984", "clinician": "Dr. Yousuf", "category": "Routine GP"},
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
            {"turn_index": 2, "turn_key": "s06_t2", "text": "The first slot, 9 am works for me, please go ahead and book it."}
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
            {"turn_index": 1, "turn_key": "s21_t1", "text": "Hi, I need an appointment with Dr. Yousuf on Wednesday morning at 10:15 am."},
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
