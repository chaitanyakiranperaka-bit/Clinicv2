import os
import re
import threading
from datetime import datetime, timedelta
from config import DUBLIN_TZ, GOOGLE_CALENDAR_ID, SERVICE_ACCOUNT_FILE, CLINICIANS, ALL_DAILY_SLOTS

try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_LIBS_AVAILABLE = True
except ImportError:
    GOOGLE_LIBS_AVAILABLE = False

LOCAL_BOOKINGS = []
_local_bookings_lock = threading.Lock()
_cached_creds = None
_creds_lock = threading.Lock()
_thread_local = threading.local()

def get_creds():
    """Thread-safe cached credentials loader."""
    global _cached_creds
    if _cached_creds is None:
        with _creds_lock:
            if _cached_creds is None and os.path.exists(SERVICE_ACCOUNT_FILE):
                _cached_creds = service_account.Credentials.from_service_account_file(
                    SERVICE_ACCOUNT_FILE, scopes=["https://www.googleapis.com/auth/calendar"]
                )
    return _cached_creds

def get_gcal_service():
    """Returns a thread-isolated Google Calendar client.
    googleapiclient (httplib2) is NOT thread-safe for shared sockets.
    Using threading.local ensures each OS thread has its own isolated connection pool.
    """
    if not (GOOGLE_LIBS_AVAILABLE and os.path.exists(SERVICE_ACCOUNT_FILE) and GOOGLE_CALENDAR_ID):
        return None

    if hasattr(_thread_local, "service") and _thread_local.service is not None:
        return _thread_local.service

    try:
        creds = get_creds()
        if creds is None:
            return None
        service = build("calendar", "v3", credentials=creds, cache_discovery=False)
        _thread_local.service = service
        return service
    except Exception as e:
        print(f"[GCal Init Error]: {e}", flush=True)
        return None

def list_booked_slots_for_date(clinician: str, date_str: str) -> list:
    booked = set()
    service = get_gcal_service()
    if service:
        try:
            # Query window from 00:00 to 23:59 to cover all daily appointments and all-day blocks
            day_start = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=0, minute=0, second=0, tzinfo=DUBLIN_TZ)
            day_end = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=23, minute=59, second=59, tzinfo=DUBLIN_TZ)
            events_result = service.events().list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=day_start.isoformat(),
                timeMax=day_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=250
            ).execute()
            
            clinician_lower = clinician.lower()
            clinician_keywords = [clinician_lower, f"[{clinician_lower}]"]
            if "nurse" in clinician_lower:
                clinician_keywords.extend(["nurse kelly", "kelly", "nurse appointment", "nurse"])
            elif "dentist" in clinician_lower or "shailaja" in clinician_lower:
                clinician_keywords.extend(["dentist shailaja", "shailaja", "dental"])
            elif "yousuf" in clinician_lower or "dr" in clinician_lower:
                clinician_keywords.extend(["dr. yousuf", "yousuf", "dr yousuf", "routine gp", "gp"])

            for ev in events_result.get("items", []):
                summary = ev.get("summary", "").lower()
                desc = ev.get("description", "").lower()
                combined = f"{summary} {desc}"

                is_clinician = any(k in combined for k in clinician_keywords)
                is_clinic_wide = any(k in summary for k in ("closed", "holiday", "all staff", "unavailable", "out of office", "maintenance"))

                if is_clinician or is_clinic_wide:
                    start_data = ev.get("start", {})
                    end_data = ev.get("end", {})

                    # 1. All-Day Event (e.g. date: "2026-11-17")
                    if "date" in start_data and not start_data.get("dateTime"):
                        ev_start = start_data["date"]
                        ev_end = end_data.get("date", ev_start)
                        if ev_start <= date_str < ev_end or ev_start == date_str:
                            for s in ALL_DAILY_SLOTS:
                                booked.add(s)

                    # 2. Timed Event (e.g. dateTime: "2026-11-17T09:30:00+00:00")
                    elif "dateTime" in start_data:
                        start_iso = start_data["dateTime"]
                        end_iso = end_data.get("dateTime")
                        if "T" in start_iso:
                            dt_start = datetime.fromisoformat(start_iso).astimezone(DUBLIN_TZ)
                            if end_iso and "T" in end_iso:
                                dt_end = datetime.fromisoformat(end_iso).astimezone(DUBLIN_TZ)
                            else:
                                dt_end = dt_start + timedelta(minutes=15)

                            # Block all 15-minute slots spanned by this appointment or block
                            curr = dt_start
                            while curr < dt_end:
                                if curr.strftime("%Y-%m-%d") == date_str:
                                    booked.add(curr.strftime("%H:%M"))
                                curr += timedelta(minutes=15)
        except Exception as e:
            _thread_local.service = None
            print(f"[GCal Query Error]: {e}", flush=True)

    with _local_bookings_lock:
        for b in LOCAL_BOOKINGS:
            if b["clinician"] == clinician and b["date"] == date_str:
                booked.add(b["slot_time"])

    return sorted(list(booked))


def find_next_available_day_slots(clinician: str, start_dt: datetime, max_days: int = 21) -> tuple:
    """Scans up to `max_days` forward from `start_dt` in a single Google Calendar range query
    to find the earliest open clinic day (Mon-Sat) that has at least one free slot.
    Returns (date_iso, free_slots_list) or (None, []).
    """
    now_dublin = datetime.now(DUBLIN_TZ)
    today_iso = now_dublin.strftime("%Y-%m-%d")
    cutoff_str = (now_dublin + timedelta(minutes=15)).strftime("%H:%M")

    base_dt = max(start_dt, now_dublin)
    candidate_dates = []
    for offset in range(1, max_days + 1):
        cand_dt = base_dt + timedelta(days=offset)
        if cand_dt.weekday() == 6:  # Skip Sundays
            continue
        candidate_dates.append(cand_dt.strftime("%Y-%m-%d"))

    if not candidate_dates:
        return None, []

    booked_by_date = {d_iso: set() for d_iso in candidate_dates}
    service = get_gcal_service()
    if service:
        try:
            range_start = datetime.strptime(candidate_dates[0], "%Y-%m-%d").replace(
                hour=0, minute=0, second=0, tzinfo=DUBLIN_TZ
            )
            range_end = datetime.strptime(candidate_dates[-1], "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=DUBLIN_TZ
            )
            events_result = service.events().list(
                calendarId=GOOGLE_CALENDAR_ID,
                timeMin=range_start.isoformat(),
                timeMax=range_end.isoformat(),
                singleEvents=True,
                orderBy="startTime",
                maxResults=2500
            ).execute()

            clinician_lower = clinician.lower()
            clinician_keywords = [clinician_lower, f"[{clinician_lower}]"]
            if "nurse" in clinician_lower:
                clinician_keywords.extend(["nurse kelly", "kelly", "nurse appointment", "nurse"])
            elif "dentist" in clinician_lower or "shailaja" in clinician_lower:
                clinician_keywords.extend(["dentist shailaja", "shailaja", "dental"])
            elif "yousuf" in clinician_lower or "dr" in clinician_lower:
                clinician_keywords.extend(["dr. yousuf", "yousuf", "dr yousuf", "routine gp", "gp"])

            for ev in events_result.get("items", []):
                summary = ev.get("summary", "").lower()
                desc = ev.get("description", "").lower()
                combined = f"{summary} {desc}"

                is_clinician = any(k in combined for k in clinician_keywords)
                is_clinic_wide = any(k in summary for k in ("closed", "holiday", "all staff", "unavailable", "out of office", "maintenance"))

                if is_clinician or is_clinic_wide:
                    start_data = ev.get("start", {})
                    end_data = ev.get("end", {})

                    if "date" in start_data and not start_data.get("dateTime"):
                        ev_start = start_data["date"]
                        ev_end = end_data.get("date", ev_start)
                        for d_iso in candidate_dates:
                            if ev_start <= d_iso < ev_end or ev_start == d_iso:
                                booked_by_date[d_iso].update(ALL_DAILY_SLOTS)
                    elif "dateTime" in start_data:
                        start_iso = start_data["dateTime"]
                        end_iso = end_data.get("dateTime")
                        if "T" in start_iso:
                            dt_start = datetime.fromisoformat(start_iso).astimezone(DUBLIN_TZ)
                            if end_iso and "T" in end_iso:
                                dt_end = datetime.fromisoformat(end_iso).astimezone(DUBLIN_TZ)
                            else:
                                dt_end = dt_start + timedelta(minutes=15)

                            curr = dt_start
                            while curr < dt_end:
                                d_key = curr.strftime("%Y-%m-%d")
                                if d_key in booked_by_date:
                                    booked_by_date[d_key].add(curr.strftime("%H:%M"))
                                curr += timedelta(minutes=15)
        except Exception as e:
            _thread_local.service = None
            print(f"[GCal Range Query Error]: {e}", flush=True)

    with _local_bookings_lock:
        for b in LOCAL_BOOKINGS:
            b_date = b.get("date")
            if b.get("clinician") == clinician and b_date in booked_by_date:
                booked_by_date[b_date].add(b["slot_time"])

    for d_iso in candidate_dates:
        booked_set = booked_by_date[d_iso]
        free = [s for s in ALL_DAILY_SLOTS if s not in booked_set]
        if d_iso == today_iso:
            free = [s for s in free if s >= cutoff_str]
        if free:
            return d_iso, free

    return None, []

def parse_time_preference(pref: str):
    """Extracts a target slot HH:MM from strings like '10:30', '10.30', '11.45 am', '10am', '2pm', '10'."""
    if not pref:
        return None
    pref = pref.lower().strip()
    if pref in ("morning", "afternoon", "any"):
        return None

    # 1. Standard HH:MM or HH.MM with optional am/pm (e.g. '11:45', '11.45 am', '9.30am', '2.15 pm', '11.30')
    m1 = re.search(r"\b(\d{1,2})[:.](\d{2})\s*(am|pm)?\b", pref)
    if m1:
        h = int(m1.group(1))
        mins = m1.group(2)
        period = m1.group(3)
        if period == "pm" and h < 12:
            h += 12
        elif period == "am" and h == 12:
            h = 0
        return f"{h:02d}:{mins}"

    # 2. Standalone hour with am/pm e.g. '10am', '2pm', '10 am'
    m2 = re.search(r"\b(\d{1,2})\s*(am|pm)\b", pref)
    if m2:
        h = int(m2.group(1))
        if m2.group(2) == "pm" and h < 12:
            h += 12
        elif m2.group(2) == "am" and h == 12:
            h = 0
        return f"{h:02d}:00"

    # 3. 4-digit colloquial/military time e.g. '1030', '0915', '1430' (exclude years like 1982, 2015, 2026)
    m3 = re.search(r"(?<![/\-\d])\b(0[89]|1[0-7])(00|15|30|45)\b(?![/\-\d])", pref)
    if m3:
        return f"{int(m3.group(1)):02d}:{m3.group(2)}"

    # 4. Standalone hour: bare number like '10' or explicitly 'at 10' (exclude dates like '12/05/1983' or '16th')
    if re.fullmatch(r"\d{1,2}", pref):
        h = int(pref)
        if 8 <= h <= 18:
            return f"{h:02d}:00"
    m4 = re.search(r"\bat\s+(\d{1,2})(?!\s*(?:st|nd|rd|th|/|-))\b", pref)
    if m4:
        h = int(m4.group(1))
        if 8 <= h <= 18:
            return f"{h:02d}:00"

    return None

def format_spoken_time(slot_str: str) -> str:
    """Converts 24h HH:MM string to natural spoken format:
    '09:00' -> '9 am'
    '09:15' -> '9:15 am'
    '13:00' -> '1 pm'
    '13:15' -> '1:15 pm'
    """
    if not slot_str or not isinstance(slot_str, str):
        return slot_str
    m = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", slot_str.strip())
    if not m:
        return slot_str
    h = int(m.group(1))
    mins = int(m.group(2))
    period = "am" if h < 12 else "pm"
    h12 = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
    if mins == 0:
        return f"{h12} {period}"
    return f"{h12}:{mins:02d} {period}"

def format_human_date(date_str: str) -> str:
    """Formats '2026-11-13' as 'Friday, 13th November 2026'."""
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        day = dt.day
        if 11 <= day <= 13:
            suf = "th"
        else:
            suf = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
        return dt.strftime(f"%A, {day}{suf} %B %Y")
    except Exception:
        return date_str

WEEKDAYS = {
    "monday": 0, "mon": 0,
    "tuesday": 1, "tue": 1, "tues": 1,
    "wednesday": 2, "wed": 2,
    "thursday": 3, "thu": 3, "thur": 3, "thurs": 3,
    "friday": 4, "fri": 4,
    "saturday": 5, "sat": 5,
    "sunday": 6, "sun": 6
}

def parse_date_preference(text: str, base_dt: datetime = None) -> str:
    """Deterministically extracts target YYYY-MM-DD from caller queries like:
    - 'on Friday', 'this Friday', 'next Monday', 'Tuesday'
    - 'today', 'tomorrow', 'day after tomorrow'
    - 'the 9th', '12th Nov', '13th', 'on the 12th'
    """
    if not text:
        return None
    if base_dt is None:
        base_dt = datetime.now(DUBLIN_TZ)

    t = text.lower().strip()

    # 1. Today / Tomorrow / Day after tomorrow
    if re.search(r"\bday after tomorrow\b", t):
        return (base_dt + timedelta(days=2)).strftime("%Y-%m-%d")
    if re.search(r"\btomorrow\b", t):
        return (base_dt + timedelta(days=1)).strftime("%Y-%m-%d")
    if re.search(r"\btoday\b", t):
        return base_dt.strftime("%Y-%m-%d")

    # 2. Weekdays
    for name, wday in WEEKDAYS.items():
        pattern = r"\b(?:this\s+|next\s+|coming\s+)?(" + name + r")\b"
        m = re.search(pattern, t)
        if m:
            is_next = bool(re.search(r"\bnext\s+" + name + r"\b", t))
            cur_wday = base_dt.weekday()
            diff = (wday - cur_wday) % 7
            if diff == 0:
                diff = 7
            if is_next and diff < 7:
                diff += 7
            target = base_dt + timedelta(days=diff)
            return target.strftime("%Y-%m-%d")

    # 3. Explicit day of month: e.g. "the 12th", "12th nov", "nov 12", "12th", "9th", "10th"
    m_day = re.search(r"\b(?:the\s+)?([1-9]|[12]\d|3[01])(?:st|nd|rd|th)?(?:\s+(?:of\s+)?(jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*)?\b", t)
    if m_day:
        day_num = int(m_day.group(1))
        month_word = m_day.group(2)
        has_ordinal = any(ord_s in t for ord_s in [f"{day_num}st", f"{day_num}nd", f"{day_num}rd", f"{day_num}th"])
        if has_ordinal or month_word or f"the {day_num}" in t or re.search(r"\bon\s+" + str(day_num) + r"\b", t):
            target_year = base_dt.year
            target_month = base_dt.month
            if month_word:
                months = ["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"]
                for idx, m_prefix in enumerate(months, 1):
                    if month_word.startswith(m_prefix):
                        target_month = idx
                        break
            try:
                candidate = datetime(target_year, target_month, day_num, tzinfo=DUBLIN_TZ)
                if candidate.date() < base_dt.date() and not month_word:
                    if target_month == 12:
                        candidate = datetime(target_year + 1, 1, day_num, tzinfo=DUBLIN_TZ)
                    else:
                        candidate = datetime(target_year, target_month + 1, day_num, tzinfo=DUBLIN_TZ)
                return candidate.strftime("%Y-%m-%d")
            except Exception:
                pass

    return None

def check_calendar_slots(clinician: str, date_str: str, time_preference: str = "any") -> dict:
    try:
        query_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=DUBLIN_TZ)
    except ValueError:
        return {"available": False, "message": f"Invalid date format: {date_str}. Please use YYYY-MM-DD."}

    original_date_str = date_str
    original_formatted_date = format_human_date(date_str)
    formatted_date = original_formatted_date
    now_dublin = datetime.now(DUBLIN_TZ)
    redirected = False
    redirect_prefix = ""

    # 1. Past dates or Sundays: automatically scan forward to the next open day with free slots
    if query_date.date() < now_dublin.date() or query_date.weekday() == 6:
        scan_start = (now_dublin - timedelta(days=1)) if query_date.date() < now_dublin.date() else query_date
        next_date_iso, free_slots = find_next_available_day_slots(clinician, scan_start, max_days=21)
        if not next_date_iso:
            return {
                "status": "error",
                "available": False,
                "date": date_str,
                "formatted_date": formatted_date,
                "suggested_slots_to_quote": [],
                "all_open_slots": [],
                "availability_verdict": f"No open slots found for {clinician} over the next 3 weeks.",
                "instruction": f"Tell the caller: 'I apologize, but {clinician} has no open appointments available over the next three weeks.'",
                "message": f"No open slots found for {clinician}."
            }
        redirected = True
        if query_date.weekday() == 6:
            redirect_prefix = f"The clinic is closed on Sundays ({original_formatted_date}). "
        else:
            redirect_prefix = f"{original_formatted_date} has already passed. "
        date_str = next_date_iso
        formatted_date = format_human_date(date_str)
    else:
        booked = list_booked_slots_for_date(clinician, date_str)
        free_slots = [s for s in ALL_DAILY_SLOTS if s not in booked]

        # If query date is today, filter out past slots (plus 15-minute buffer)
        if date_str == now_dublin.strftime("%Y-%m-%d"):
            cutoff_dt = now_dublin + timedelta(minutes=15)
            cutoff_str = cutoff_dt.strftime("%H:%M")
            free_slots = [s for s in free_slots if s >= cutoff_str]

        # Automatically scan forward to the next available date with free slots instead of looping day-by-day
        if not free_slots:
            next_date_iso, next_free_slots = find_next_available_day_slots(clinician, query_date, max_days=21)
            if not next_date_iso:
                return {
                    "status": "error",
                    "available": False,
                    "date": date_str,
                    "formatted_date": formatted_date,
                    "suggested_slots_to_quote": [],
                    "all_open_slots": [],
                    "availability_verdict": f"No open slots found for {clinician} over the next 3 weeks.",
                    "instruction": f"Tell the caller: 'I apologize, but {clinician} has no open appointments available over the next three weeks.'",
                    "message": f"No open slots found for {clinician}."
                }
            redirected = True
            date_str = next_date_iso
            formatted_date = format_human_date(date_str)
            free_slots = next_free_slots

    morning = [s for s in free_slots if int(s.split(":")[0]) < 13]
    afternoon = [s for s in free_slots if int(s.split(":")[0]) >= 13]

    pref = (time_preference or "any").lower().strip()
    target_slot = parse_time_preference(pref)

    if target_slot:
        target_spoken = format_spoken_time(target_slot)
        exact_available = target_slot in free_slots

        def distance(s):
            h, m = map(int, s.split(":"))
            th, tm = map(int, target_slot.split(":"))
            return abs((h * 60 + m) - (th * 60 + tm))

        closest = sorted(free_slots, key=distance)[:3]
        if exact_available:
            suggested = [target_slot]
            status_msg = f"{target_spoken} is AVAILABLE with {clinician} on {formatted_date}."
            if redirected:
                instruction = (
                    f"Tell the caller: '{redirect_prefix}The earliest available day with {clinician} is {formatted_date}, and {target_spoken} is open. "
                    f"Would you like me to book {target_spoken} on {formatted_date} for you?' Wait for their explicit confirmation."
                )
            else:
                instruction = (
                    f"Tell the caller: 'Yes, {target_spoken} is available with {clinician} on {formatted_date}. "
                    "Would you like me to book that for you?' Wait for their explicit confirmation."
                )
        else:
            suggested = sorted(closest)
            suggested_spoken = [format_spoken_time(s) for s in suggested]
            first_spoken = suggested_spoken[0]
            other_spoken = ", ".join(suggested_spoken[1:])
            other_clause = f", or I also have {other_spoken}" if other_spoken else ""
            is_today = (date_str == now_dublin.strftime("%Y-%m-%d"))
            target_in_past = (is_today and target_slot < now_dublin.strftime("%H:%M"))
            if redirected:
                status_msg = f"Earliest available date with {clinician} is {formatted_date}. Open slots: {', '.join(suggested_spoken)}."
                instruction = (
                    f"Tell the caller: '{redirect_prefix}The earliest available appointment with {clinician} is on {formatted_date} at {first_spoken}{other_clause}. "
                    f"Would you like me to book {first_spoken} on {formatted_date} for you?'"
                )
            elif target_in_past:
                status_msg = f"{target_spoken} has ALREADY PASSED today ({formatted_date}). Closest remaining open times today are: {', '.join(suggested_spoken)}."
                instruction = (
                    f"Tell the caller: '{target_spoken} has already passed today ({formatted_date}), but I have {first_spoken} open later today{other_clause}. "
                    f"Would you like me to book {first_spoken} for you?'"
                )
            else:
                status_msg = f"{target_spoken} is NOT available with {clinician} on {formatted_date}. Closest alternative times on {formatted_date} are: {', '.join(suggested_spoken)}."
                instruction = (
                    f"Tell the caller: '{target_spoken} is not available with {clinician} on {formatted_date}, but I have {first_spoken} open{other_clause}. "
                    f"Would you like me to book {first_spoken} for you?'"
                )
    elif "morning" in pref:
        suggested = morning[:3] if morning else afternoon[:3]
        suggested_spoken = [format_spoken_time(s) for s in suggested]
        first_spoken = suggested_spoken[0]
        other_spoken = ", ".join(suggested_spoken[1:])
        other_clause = f", or I also have {other_spoken}" if other_spoken else ""
        status_msg = f"Available morning slots with {clinician} on {formatted_date}: {', '.join(suggested_spoken)}"
        instruction = (
            f"Tell the caller: '{redirect_prefix}The earliest available morning appointment with {clinician} is on {formatted_date} at {first_spoken}{other_clause}. "
            f"Would you like me to book {first_spoken} on {formatted_date} for you?'"
        )
    elif "afternoon" in pref:
        suggested = afternoon[:3] if afternoon else morning[:3]
        suggested_spoken = [format_spoken_time(s) for s in suggested]
        first_spoken = suggested_spoken[0]
        other_spoken = ", ".join(suggested_spoken[1:])
        other_clause = f", or I also have {other_spoken}" if other_spoken else ""
        status_msg = f"Available afternoon slots with {clinician} on {formatted_date}: {', '.join(suggested_spoken)}"
        instruction = (
            f"Tell the caller: '{redirect_prefix}The earliest available afternoon appointment with {clinician} is on {formatted_date} at {first_spoken}{other_clause}. "
            f"Would you like me to book {first_spoken} on {formatted_date} for you?'"
        )
    else:
        suggested = (morning[:2] + afternoon[:2]) if (morning and afternoon) else free_slots[:3]
        suggested_spoken = [format_spoken_time(s) for s in suggested]
        first_spoken = suggested_spoken[0]
        other_spoken = ", ".join(suggested_spoken[1:])
        other_clause = f", or I also have {other_spoken}" if other_spoken else ""
        status_msg = f"Available slots with {clinician} on {formatted_date}: {', '.join(suggested_spoken)}"
        instruction = (
            f"Tell the caller: '{redirect_prefix}The earliest available appointment with {clinician} is on {formatted_date} at {first_spoken}{other_clause}. "
            f"Would you like me to book {first_spoken} on {formatted_date} for you?'"
        )

    return {
        "status": "success",
        "available": True,
        "clinician": clinician,
        "requested_date": original_date_str,
        "date": date_str,
        "formatted_date": formatted_date,
        "is_requested_time_available": bool(target_slot and target_slot in free_slots and not redirected),
        "earliest_slot": suggested[0] if suggested else None,
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
        next_date_iso, next_free = find_next_available_day_slots(clinician, now_dublin, max_days=21)
        if next_date_iso and next_free:
            next_fmt = format_human_date(next_date_iso)
            first_slot = next_free[0]
            first_spoken = format_spoken_time(first_slot)
            return {
                "success": False,
                "date": next_date_iso,
                "suggested_slots_to_quote": next_free[:3],
                "all_open_slots": next_free,
                "error": f"{slot_time} on {date_str} has already passed.",
                "instruction": f"Tell the caller: 'I apologize, but {format_spoken_time(slot_time)} on {format_human_date(date_str)} has already passed. The earliest available slot is {first_spoken} on {next_fmt}. Would you like me to book that for you?'"
            }
        tomorrow_iso = (now_dublin + timedelta(days=1)).strftime("%Y-%m-%d")
        tomorrow_fmt = format_human_date(tomorrow_iso)
        return {
            "success": False,
            "error": f"{slot_time} on {date_str} has already passed.",
            "instruction": f"Tell the caller: 'I apologize, but {format_spoken_time(slot_time)} on {format_human_date(date_str)} has already passed. Would you like me to book an appointment for tomorrow ({tomorrow_fmt}) instead?'"
        }

    booked = list_booked_slots_for_date(clinician, date_str)
    if slot_time in booked:
        today_iso = now_dublin.strftime("%Y-%m-%d")
        cutoff_str = now_dublin.strftime("%H:%M")
        all_open = [s for s in ALL_DAILY_SLOTS if s not in booked and (date_str != today_iso or s >= cutoff_str)]
        suggested = all_open[:3]
        if suggested:
            first_spoken = format_spoken_time(suggested[0])
            other_spoken = ", ".join(format_spoken_time(s) for s in suggested[1:])
            other_clause = f", or {other_spoken}" if other_spoken else ""
            return {
                "success": False,
                "date": date_str,
                "error": f"{slot_time} with {clinician} on {date_str} is already booked.",
                "suggested_slots_to_quote": suggested,
                "all_open_slots": all_open,
                "instruction": f"Tell the caller: 'I apologize, but {format_spoken_time(slot_time)} was just taken. However, I have {first_spoken}{other_clause} open on {format_human_date(date_str)}. Would you like me to book {first_spoken} for you?'"
            }
        else:
            next_date_iso, next_free = find_next_available_day_slots(clinician, appt_dt, max_days=21)
            if next_date_iso and next_free:
                next_fmt = format_human_date(next_date_iso)
                next_suggested = next_free[:3]
                first_spoken = format_spoken_time(next_suggested[0])
                return {
                    "success": False,
                    "date": next_date_iso,
                    "error": f"{slot_time} with {clinician} on {date_str} is already booked, and no remaining slots exist on that date.",
                    "suggested_slots_to_quote": next_suggested,
                    "all_open_slots": next_free,
                    "instruction": f"Tell the caller: 'I apologize, but {format_spoken_time(slot_time)} was just taken and {format_human_date(date_str)} is now full. However, I have {first_spoken} open on {next_fmt}. Would you like me to book that for you?'"
                }
            return {
                "success": False,
                "date": date_str,
                "error": f"{slot_time} with {clinician} on {date_str} is already booked, and no remaining slots exist on that date.",
                "suggested_slots_to_quote": [],
                "all_open_slots": [],
                "instruction": f"Tell the caller: 'I apologize, but {format_spoken_time(slot_time)} was just taken and all other appointments for {format_human_date(date_str)} are full.'"
            }

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
            _thread_local.service = None
            sync_status = f"Local Queue (GCal error: {str(e)[:30]})"

    formatted_date = format_human_date(date_str)
    spoken_time = format_spoken_time(slot_time)
    record = {
        "clinician": clinician,
        "date": date_str,
        "formatted_date": formatted_date,
        "slot_time": slot_time,
        "spoken_time": spoken_time,
        "patient_name": patient_name,
        "patient_dob": patient_dob,
        "phone": caller_phone,
        "category": appointment_category,
        "sync_status": sync_status
    }
    with _local_bookings_lock:
        LOCAL_BOOKINGS.append(record)
    return {
        "success": True,
        "booking": record,
        "formatted_date": formatted_date,
        "spoken_time": spoken_time,
        "message": f"Successfully booked {appointment_category} with {clinician} on {formatted_date} at {spoken_time} for {patient_name}.",
        "instruction": f"Tell the caller: 'I have booked your appointment with {clinician} for {formatted_date} at {spoken_time}. Is there anything else I can help you with today?'"
    }
