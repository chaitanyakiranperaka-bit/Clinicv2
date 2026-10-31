import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from google.oauth2 import service_account
from googleapiclient.discovery import build

KEY_FILE = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "/home/ubuntu/service_account.json")
CAL_ID = os.getenv("GOOGLE_CALENDAR_ID", "")

print(f"1. Checking Key File: {KEY_FILE}")
if not os.path.exists(KEY_FILE):
    print("   ❌ Key file NOT found on this EC2 machine!\n")
else:
    print("   ✅ Key file exists.")

print(f"2. Checking Calendar ID: '{CAL_ID}'")
if not CAL_ID or CAL_ID == "YOUR_CALENDAR_ID@group.calendar.google.com":
    print("   ❌ GOOGLE_CALENDAR_ID is empty or unset in environment!\n")
else:
    print(f"   ✅ Calendar ID is set: {CAL_ID}")

if os.path.exists(KEY_FILE) and CAL_ID:
    try:
        print("3. Attempting to authenticate with Google API...")
        creds = service_account.Credentials.from_service_account_file(
            KEY_FILE, scopes=["https://www.googleapis.com/auth/calendar"]
        )
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        
        # Test inserting a dummy 15-minute slot
        dublin_tz = ZoneInfo("Europe/Dublin")
        now = datetime.now(dublin_tz)
        test_start = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        test_end = test_start + timedelta(minutes=15)
        
        event = {
            "summary": "[TEST] Clinic Receptionist Integration Test",
            "start": {"dateTime": test_start.isoformat(), "timeZone": "Europe/Dublin"},
            "end": {"dateTime": test_end.isoformat(), "timeZone": "Europe/Dublin"},
        }
        res = service.events().insert(calendarId=CAL_ID, body=event).execute()
        print(f"   ✅ SUCCESS! Event created on Google Calendar: {res.get('htmlLink')}")
    except Exception as e:
        print(f"   ❌ Google Calendar API failed: {e}")
