import os
from datetime import datetime, timedelta
from config import DUBLIN_TZ, GOOGLE_CALENDAR_ID, SERVICE_ACCOUNT_FILE, CLINICIANS, ALL_DAILY_SLOTS

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

LOCAL_BOOKINGS = []

def get_gcal_service():
    if GOOGLE_LIBS_AVAILABLE and os.path.exists(SERVICE_ACCOUNT_FILE) and GOOGLE_CALENDAR_ID:
        try:
            creds = service_account.Credentials.from_service_account_file(
                SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/calendar"]
            )
            return build("calendar", "v3", credentials=creds, cache_discovery=False)
        except Exception as e:
            print(f"[GCal Init Error]: {e}", flush=True)
    return None

def list_booked_slots_for_date(clinician: str, date_str: str) -> list:
    booked = set()
    service = get_gcal_service()
    if service:
        try:
            day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=9, minute=0, tzinfo=DUBLIN_TZ)
            day_end = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=17, minute=0, tzinfo=DUBLIN_TZ)
            events_result = service.events().list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy="startTime"
            ).execute()
            for ev in events_result.get("items", []):
                summary = ev.get("summary", "")
                if f"[{clinician}]" in summary:
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

def check_calendar_slots(clinician: str, date_str: str, time_preference: str = "any") -> dict:
    booked = list_booked_slots_for_date(clinician, date_str)
    free_slots = [s for s in ALL_DAILY_SLOTS if s not in booked]

    if not free_slots:
        return {"available": False, "message": f"No open slots for {clinician} on {date_str}."}

    morning = [s for s in free_slots if int(s.split(":")[0]) < 13]
    afternoon = [s for s in free_slots if int(s.split(":")[0]) >= 13]

    pref = (time_preference or "any").lower()
    if "morning" in pref:
        suggested = morning[:3]
    elif "afternoon" in pref:
        suggested = afternoon[:3]
    else:
        suggested = morning[:2] + afternoon[:2]

    return {
        "status": "success",
        "clinician": clinician,
        "date": date_str,
        "suggested_slots_to_quote": suggested,
        "instruction": "Speak 2 or 3 of these times to the patient now."
    }

def book_calendar_slot(clinician: str, date_str: str, slot_time: str, patient_name: str, patient_dob: str, caller_phone: str, appointment_category: str) -> dict:
    slot_time = slot_time.strip()[:5]
    if slot_time not in ALL_DAILY_SLOTS:
        return {"success": False, "error": f"{slot_time} is outside clinic hours (09:00-17:00)."}

    booked = list_booked_slots_for_date(clinician, date_str)
    if slot_time in booked:
        return {"success": False, "error": f"{slot_time} with {clinician} on {date_str} is already booked."}

    start_dt = datetime.strptime(f"{date_str} {slot_time}", "%Y-%m-%d %H:%M").replace(tzinfo=DUBLIN_TZ)
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
