import os
import re
from datetime import datetime, timedelta
from config import DUBLIN_TZ, GOOGLE_CALENDAR_ID, SERVICE_ACCOUNT_FILE, CLINICIANS, ALL_DAILY_SLOTS

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

LOCAL_BOOKINGS = []
_cached_service = None

def get_gcal_service():
    """Returns a cached Google Calendar service client or initializes a new one."""
    global _cached_service
    if _cached_service is not None:
        return _cached_service

    if GOOGLE_LIBS_AVAILABLE and os.path.exists(SERVICE_ACCOUNT_FILE) and GOOGLE_CALENDAR_ID:
        try:
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/calendar"]
            )
            _cached_service = build("calendar", "v3", credentials=creds, cache_discovery=False)
            return _cached_service
        except Exception as e:
            print(f"[GCal Init Error]: {e}", flush=True)
    return None

def list_booked_slots_for_date(clinician: str, date_str: str) -> list:
    booked = set()
    service = get_gcal_service()
    if service:
        try:
            # Query window from 08:00 to 18:00 to cover all daily appointments
            day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=8, minute=0, tzinfo=DUBLIN_TZ)
            day_end = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=18, minute=0, tzinfo=DUBLIN_TZ)
            events_result = service.events().list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            
            clinician_lower = clinician.lower()
            for ev in events_result.get("items", []):
                summary = ev.get("summary", "").lower()
                # Check for [Dr. Yousuf] tag or clinician name in summary
                if f"[{clinician_lower}]" in summary or clinician_lower in summary:
                    start_iso = ev["start"].get("dateTime", "")
                    if "T" in start_iso:
                        dt = datetime.fromisoformat(start_iso).astimezone(DUBLIN_TZ)
                        booked.add(dt.strftime("%H:%M"))
        except Exception as e:
            print(f"[GCal Query Error]: {e}", flush=True)

    for b in LOCAL_BOOKINGS:
        if b["clinician"] == clinician and b["date"] == date_str:
            booked.add(b["slot_time"])

    return sorted(list(booked))

def parse_time_preference(pref: str):
    """Extracts a target slot HH:MM from strings like '10:30', '1030', '10am', '2pm', '10'."""
    if not pref:
        return None
    pref = pref.lower().strip()
    if pref in ("morning", "afternoon", "any"):
        return None

    # 1. Standard HH:MM
    m1 = re.search(r"\b(\d{1,2}):(\d{2})\b", pref)
    if m1:
        return f"{int(m1.group(1)):02d}:{m1.group(2)}"

    # 2. 4-digit colloquial/military time e.g. '1030', '0915', '1430'
    m2 = re.search(r"\b([01]?\d|2[0-3])([0-5]\d)\b", pref)
    if m2:
        return f"{int(m2.group(1)):02d}:{m2.group(2)}"

    # 3. 10am, 2pm, 10 am
    m3 = re.search(r"\b(\d{1,2})\s*(am|pm)\b", pref)
    if m3:
        h = int(m3.group(1))
        if m3.group(2) == "pm" and h < 12:
            h += 12
        elif m3.group(2) == "am" and h == 12:
            h = 0
        return f"{h:02d}:00"

    # 4. Standalone hour e.g. 'at 10', '10'
    m4 = re.search(r"\b(?:at\s+)?(\d{1,2})\b", pref)
    if m4:
        h = int(m4.group(1))
        if 8 <= h <= 18:
            return f"{h:02d}:00"

    return None

def check_calendar_slots(clinician: str, date_str: str, time_preference: str = "any") -> dict:
    try:
        query_date = datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return {"available": False, "message": f"Invalid date format: {date_str}. Please use YYYY-MM-DD."}

    # 1. Clinic is closed on Sundays (weekday() == 6)
    if query_date.weekday() == 6:
        days_until_monday = (7 - query_date.weekday()) % 7 or 7
        next_monday = (query_date + timedelta(days=days_until_monday)).strftime("%Y-%m-%d")
        return {
            "available": False,
            "closed": True,
            "message": f"The clinic is closed on Sundays. Please offer Monday ({next_monday}) or advise D-Doc/K-Doc GP cooperative for urgent issues."
        }

    booked = list_booked_slots_for_date(clinician, date_str)
    
    # 2. Filter out already booked slots
    free_slots = [s for s in ALL_DAILY_SLOTS if s not in booked]

    # 3. If query date is today, filter out past slots (plus 15-minute buffer)
    now_dublin = datetime.now(DUBLIN_TZ)
    if date_str == now_dublin.strftime("%Y-%m-%d"):
        cutoff_dt = now_dublin + timedelta(minutes=15)
        cutoff_str = cutoff_dt.strftime("%H:%M")
        free_slots = [s for s in free_slots if s >= cutoff_str]

    if not free_slots:
        tomorrow_iso = (now_dublin + timedelta(days=1)).strftime("%Y-%m-%d")
        return {
            "available": False,
            "message": f"No remaining open slots for {clinician} on {date_str}. Suggest tomorrow ({tomorrow_iso}) or another date."
        }

    morning = [s for s in free_slots if int(s.split(":")[0]) < 13]
    afternoon = [s for s in free_slots if int(s.split(":")[0]) >= 13]

    pref = (time_preference or "any").lower().strip()
    target_slot = parse_time_preference(pref)

    if target_slot:
        exact_available = target_slot in free_slots

        def distance(s):
            h, m = map(int, s.split(":"))
            th, tm = map(int, target_slot.split(":"))
            return abs((h * 60 + m) - (th * 60 + tm))

        closest = sorted(free_slots, key=distance)[:3]
        if exact_available:
            suggested = [target_slot]
            status_msg = f"{target_slot} is AVAILABLE with {clinician} on {date_str}."
            instruction = (
                f"Tell the caller: 'Yes, {target_slot} is available with {clinician} on {date_str}. "
                "Would you like me to book that for you?' Wait for their explicit confirmation."
            )
        else:
            suggested = sorted(closest)
            status_msg = f"{target_slot} is NOT available with {clinician} on {date_str}. Closest alternative times are: {', '.join(suggested)}."
            instruction = (
                f"Tell the caller: '{target_slot} is not available with {clinician}, but I have {', '.join(suggested)} open. "
                "Would one of those times suit you?'"
            )
    elif "morning" in pref:
        suggested = morning[:3] if morning else afternoon[:3]
        status_msg = f"Available morning slots with {clinician}: {', '.join(suggested)}"
        instruction = f"Quote 2 or 3 of these morning times: {', '.join(suggested)}."
    elif "afternoon" in pref:
        suggested = afternoon[:3] if afternoon else morning[:3]
        status_msg = f"Available afternoon slots with {clinician}: {', '.join(suggested)}"
        instruction = f"Quote 2 or 3 of these afternoon times: {', '.join(suggested)}."
    else:
        suggested = (morning[:2] + afternoon[:2]) if (morning and afternoon) else free_slots[:3]
        status_msg = f"Available slots with {clinician}: {', '.join(suggested)}"
        instruction = f"Quote 2 or 3 of these times: {', '.join(suggested)}. Ask which time they prefer."

    return {
        "status": "success",
        "clinician": clinician,
        "date": date_str,
        "is_requested_time_available": bool(target_slot and target_slot in free_slots),
        "suggested_slots_to_quote": suggested,
        "all_open_slots": free_slots,
        "availability_verdict": status_msg,
        "instruction": instruction
    }

def book_calendar_slot(clinician: str, date_str: str, slot_time: str, patient_name: str, patient_dob: str, caller_phone: str, appointment_category: str) -> dict:
    slot_time = slot_time.strip()[:5]
    if slot_time not in ALL_DAILY_SLOTS:
        return {"success": False, "error": f"{slot_time} is outside clinic hours (09:00-17:00)."}

    try:
        appt_dt = datetime.strptime(f"{date_str} {slot_time}", "%Y-%m-%d %H:%M").replace(tzinfo=DUBLIN_TZ)
    except ValueError:
        return {"success": False, "error": f"Invalid date or slot format: {date_str} {slot_time}"}

    # Closed on Sundays
    if appt_dt.weekday() == 6:
        return {"success": False, "error": "The clinic is closed on Sundays."}

    # Check if slot is in the past
    now_dublin = datetime.now(DUBLIN_TZ)
    if appt_dt < now_dublin:
        return {"success": False, "error": f"{slot_time} on {date_str} has already passed."}

    booked = list_booked_slots_for_date(clinician, date_str)
    if slot_time in booked:
        return {"success": False, "error": f"{slot_time} with {clinician} on {date_str} is already booked."}

    start_dt = appt_dt
    end_dt = start_dt + timedelta(minutes=15)

    summary = f"[{clinician}] {patient_name} - {appointment_category}"
    description = (
        f"Patient: {patient_name}\nDOB: {patient_dob}\nPhone: {caller_phone}\nCategory: {appointment_category}\nStatus: Provisional AI Booking"
    )

    sync_status = "Local Staging Queue"
    service = get_gcal_service()
    if service:
        try:
            event_body = {
                "summary": summary,
                "description": description,
                "colorId": CLINICIANS.get(clinician, {}).get("colorId", "9"),
                "start": {"dateTime": start_dt.isoformat(), "timeZone": "Europe/Dublin"},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": "Europe/Dublin"},
            }
            created = service.events().insert(calendarId=GOOGLE_CALENDAR_ID, body=event_body).execute()
            sync_status = created.get("htmlLink", "Live Google Calendar")
            print(f"[GCAL EVENT CREATED]: {sync_status}", flush=True)
        except Exception as e:
            sync_status = f"Local Queue (GCal error: {str(e)[:30]})"

    record = {
        "clinician": clinician,
        "date": date_str,
        "slot_time": slot_time,
        "patient_name": patient_name,
        "patient_dob": patient_dob,
        "phone": caller_phone,
        "category": appointment_category,
        "sync_status": sync_status
    }
    LOCAL_BOOKINGS.append(record)
    return {"success": True, "booking": record}
