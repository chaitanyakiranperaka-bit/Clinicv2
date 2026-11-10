import os
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from zoneinfo import ZoneInfo

from config import (
    DUBLIN_TZ,
    ALL_DAILY_SLOTS,
    DENTALLY_PRACTITIONERS,
    CLINICIANS
)
from dentally_client import dentally_client

def is_dentally_practitioner(clinician: str) -> bool:
    """Checks whether the clinician is handled via Dentally."""
    if not clinician:
        return False
    if clinician in DENTALLY_PRACTITIONERS:
        return True
    # Fuzzy match e.g. "Dentist Shailaja" or "Shailja"
    c_lower = clinician.lower()
    for name in DENTALLY_PRACTITIONERS:
        if name.lower() in c_lower or c_lower in name.lower():
            return True
    return False

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
    """Queries live practitioner availability from Dentally API for a given date.
    
    Converts UTC availability windows into discrete 15-minute Dublin-time appointment slots.
    Returns:
        List of HH:MM strings (e.g. ['09:00', '09:15', ...]) or None if fetch fails.
    """
    if not dentally_client.is_configured():
        return None

    prac_id = get_practitioner_uuid(clinician)
    if not prac_id:
        return None

    try:
        # Dentally availability endpoint accepts date_from and date_to (max 7 day span)
        windows = dentally_client.get_practitioner_availability(
            date_from=date_str,
            date_to=date_str,
            practitioner_ids=[prac_id]
        )
        
        utc_tz = ZoneInfo("UTC")
        slots = set()

        for win in windows:
            # start_time and finish_time are ISO 8601 strings in UTC (e.g. '2026-11-11T09:00:00Z')
            s_raw = win.get("start_time", "")
            f_raw = win.get("finish_time", "")
            if not s_raw or not f_raw:
                continue

            dt_start = datetime.fromisoformat(s_raw.replace("Z", "+00:00")).astimezone(DUBLIN_TZ)
            dt_finish = datetime.fromisoformat(f_raw.replace("Z", "+00:00")).astimezone(DUBLIN_TZ)

            # Generate 15-minute slot chunks within window
            cur = dt_start
            while cur + timedelta(minutes=15) <= dt_finish:
                time_str = cur.strftime("%H:%M")
                # Only include standard operating slots between 09:00 and 17:00
                if time_str in ALL_DAILY_SLOTS:
                    slots.add(time_str)
                cur += timedelta(minutes=15)

        # Filter out past slots if querying today
        now_dublin = datetime.now(DUBLIN_TZ)
        if date_str == now_dublin.strftime("%Y-%m-%d"):
            cutoff = (now_dublin + timedelta(minutes=15)).strftime("%H:%M")
            slots = {s for s in slots if s >= cutoff}

        return sorted(list(slots))

    except Exception as e:
        print(f"[Dentally Service Warning]: Failed to fetch live availability for {clinician} on {date_str}: {e}", flush=True)
        return None

def get_clinic_site_summary() -> Optional[Dict[str, Any]]:
    """Retrieves verified clinic site details from Dentally."""
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
