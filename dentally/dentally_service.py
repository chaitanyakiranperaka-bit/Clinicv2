import re
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from zoneinfo import ZoneInfo

try:
    from .dentally_config import (
        DUBLIN_TZ,
        ALL_DAILY_SLOTS,
        DENTALLY_PRACTITIONERS
    )
    from .dentally_client import dentally_client
except ImportError:
    from dentally_config import (
        DUBLIN_TZ,
        ALL_DAILY_SLOTS,
        DENTALLY_PRACTITIONERS
    )
    from dentally_client import dentally_client

def format_spoken_time(slot_str: str) -> str:
    """Converts 24h HH:MM string to natural spoken format:
    '09:00' -> '9 am', '13:15' -> '1:15 pm'
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

def parse_time_preference(pref: str) -> Optional[str]:
    """Extracts target HH:MM from strings like '10:00', '1030', '10am', '2pm'."""
    if not pref:
        return None
    p = pref.lower().strip()
    if p in ("morning", "afternoon", "any"):
        return None

    m1 = re.search(r"\b(\d{1,2}):(\d{2})\b", p)
    if m1:
        return f"{int(m1.group(1)):02d}:{m1.group(2)}"

    m2 = re.search(r"\b([01]?\d|2[0-3])([0-5]\d)\b", p)
    if m2:
        return f"{int(m2.group(1)):02d}:{m2.group(2)}"

    m3 = re.search(r"\b(\d{1,2})\s*(am|pm)\b", p)
    if m3:
        h = int(m3.group(1))
        if m3.group(2) == "pm" and h < 12:
            h += 12
        elif m3.group(2) == "am" and h == 12:
            h = 0
        return f"{h:02d}:00"

    m4 = re.search(r"\b(?:at\s+)?(\d{1,2})\b", p)
    if m4:
        h = int(m4.group(1))
        if 8 <= h <= 18:
            return f"{h:02d}:00"

    return None

def get_practitioner_uuid(clinician: str) -> Optional[str]:
    """Resolves clinician name to Dentally practitioner UUID."""
    if clinician in DENTALLY_PRACTITIONERS:
        return DENTALLY_PRACTITIONERS[clinician]
    c_lower = clinician.lower()
    for name, uuid in DENTALLY_PRACTITIONERS.items():
        if name.lower() in c_lower or c_lower in name.lower():
            return uuid
    return None

def fetch_dentally_free_slots(clinician: str, date_str: str) -> Optional[List[str]]:
    """READ: Queries live practitioner availability from Dentally API for a given date.
    
    Converts UTC availability windows into discrete 15-minute Dublin-time appointment slots.
    """
    if not dentally_client.is_configured():
        return None

    prac_id = get_practitioner_uuid(clinician)
    if not prac_id:
        return None

    try:
        windows = dentally_client.get_practitioner_availability(
            date_from=date_str,
            date_to=date_str,
            practitioner_ids=[prac_id]
        )
        
        slots = set()
        for win in windows:
            s_raw = win.get("start_time", "")
            f_raw = win.get("finish_time", "")
            if not s_raw or not f_raw:
                continue

            dt_start = datetime.fromisoformat(s_raw.replace("Z", "+00:00")).astimezone(DUBLIN_TZ)
            dt_finish = datetime.fromisoformat(f_raw.replace("Z", "+00:00")).astimezone(DUBLIN_TZ)

            cur = dt_start
            while cur + timedelta(minutes=15) <= dt_finish:
                time_str = cur.strftime("%H:%M")
                if time_str in ALL_DAILY_SLOTS:
                    slots.add(time_str)
                cur += timedelta(minutes=15)

        now_dublin = datetime.now(DUBLIN_TZ)
        if date_str == now_dublin.strftime("%Y-%m-%d"):
            cutoff = (now_dublin + timedelta(minutes=15)).strftime("%H:%M")
            slots = {s for s in slots if s >= cutoff}

        return sorted(list(slots))

    except Exception as e:
        print(f"[Dentally Service Warning]: Failed to fetch live availability for {clinician} on {date_str}: {e}", flush=True)
        return None

def check_dentally_slots(clinician: str, date_str: str, time_preference: str = "any") -> Dict[str, Any]:
    """READ: High-level availability checker for Dentally test app turns."""
    try:
        query_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=DUBLIN_TZ)
    except ValueError:
        return {"available": False, "message": f"Invalid date format: {date_str}. Please use YYYY-MM-DD."}

    formatted_date = format_human_date(date_str)

    # Sunday check (clinic closed)
    if query_date.weekday() == 6:
        return {
            "available": False,
            "closed": True,
            "date": date_str,
            "formatted_date": formatted_date,
            "message": f"Star Dental Care is closed on Sundays ({formatted_date}). Please offer Monday."
        }

    free_slots = fetch_dentally_free_slots(clinician, date_str)
    if free_slots is None:
        return {
            "available": False,
            "date": date_str,
            "formatted_date": formatted_date,
            "message": f"Unable to reach Dentally availability service for {clinician} on {formatted_date}."
        }

    if not free_slots:
        return {
            "available": False,
            "date": date_str,
            "formatted_date": formatted_date,
            "message": f"No open clinical slots found in Dentally for {clinician} on {formatted_date}."
        }

    pref = (time_preference or "any").lower().strip()
    target_slot = parse_time_preference(pref)

    morning = [s for s in free_slots if int(s.split(":")[0]) < 13]
    afternoon = [s for s in free_slots if int(s.split(":")[0]) >= 13]

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
            instruction = (
                f"Tell the caller: 'Yes, {target_spoken} is available with {clinician} on {formatted_date}. "
                "Would you like me to hold that time for you?'"
            )
        else:
            suggested = sorted(closest)
            suggested_spoken = [format_spoken_time(s) for s in suggested]
            status_msg = f"{target_spoken} is NOT available with {clinician} on {formatted_date}. Closest open times in Dentally are: {', '.join(suggested_spoken)}."
            instruction = (
                f"Tell the caller: '{target_spoken} is not available with {clinician} on {formatted_date}, but I have {', '.join(suggested_spoken)} open in our schedule. "
                "Would one of those times suit you?'"
            )
    elif "morning" in pref:
        suggested = morning[:3] if morning else afternoon[:3]
        suggested_spoken = [format_spoken_time(s) for s in suggested]
        status_msg = f"Available morning slots in Dentally with {clinician} on {formatted_date}: {', '.join(suggested_spoken)}"
        instruction = f"Quote these morning times on {formatted_date}: {', '.join(suggested_spoken)}."
    elif "afternoon" in pref:
        suggested = afternoon[:3] if afternoon else morning[:3]
        suggested_spoken = [format_spoken_time(s) for s in suggested]
        status_msg = f"Available afternoon slots in Dentally with {clinician} on {formatted_date}: {', '.join(suggested_spoken)}"
        instruction = f"Quote these afternoon times on {formatted_date}: {', '.join(suggested_spoken)}."
    else:
        suggested = (morning[:2] + afternoon[:2]) if (morning and afternoon) else free_slots[:3]
        suggested_spoken = [format_spoken_time(s) for s in suggested]
        status_msg = f"Available slots in Dentally with {clinician} on {formatted_date}: {', '.join(suggested_spoken)}"
        instruction = f"Quote 2 or 3 of these times on {formatted_date}: {', '.join(suggested_spoken)}. Ask which time they prefer."

    return {
        "status": "success",
        "clinician": clinician,
        "date": date_str,
        "formatted_date": formatted_date,
        "is_requested_time_available": bool(target_slot and target_slot in free_slots),
        "suggested_slots_to_quote": suggested,
        "all_open_slots": free_slots,
        "availability_verdict": status_msg,
        "instruction": instruction
    }

def get_clinic_site_summary() -> Optional[Dict[str, Any]]:
    """READ: Retrieves verified clinic site details from Dentally."""
    if not dentally_client.is_configured():
        return None
    try:
        site = dentally_client.get_primary_site()
        if site:
            addr = site.get("address", {})
            full_addr = f"{addr.get('address_line_1', '')}, {addr.get('address_line_2', '')}, {addr.get('locality', '')} {addr.get('postal_code', '')}".strip()
            return {
                "name": site.get("name"),
                "address": full_addr,
                "phone": site.get("contact_details", {}).get("phone_number"),
                "email": site.get("contact_details", {}).get("email_address"),
                "website": site.get("contact_details", {}).get("website_url"),
                "opening_hours": site.get("opening_hours", [])
            }
    except Exception as e:
        print(f"[Dentally Service Site Fetch Error]: {e}", flush=True)
    return None

def list_upcoming_appointments(limit: int = 10) -> List[Dict[str, Any]]:
    """READ: Retrieves recent/upcoming appointments from Dentally."""
    if not dentally_client.is_configured():
        return []
    try:
        res = dentally_client.get_appointments(limit=limit)
        return res.get("data", [])
    except Exception as e:
        print(f"[Dentally Appointments Read Error]: {e}", flush=True)
        return []

