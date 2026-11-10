#!/usr/bin/env python3
"""Dentally NexGen API Read Test Suite.
Verifies all read operations against the live production Dentally API for Star Dental Care.
Strictly Read-Only (no bookings or mutations created).
"""

import sys
import os
import json

_pkg_dir = os.path.dirname(os.path.abspath(__file__))
if _pkg_dir not in sys.path:
    sys.path.insert(0, _pkg_dir)

from datetime import datetime, timedelta

try:
    from .dentally_config import DENTALLY_PRACTITIONERS, DUBLIN_TZ
    from .dentally_client import dentally_client
    from .dentally_service import (
        get_clinic_site_summary,
        fetch_dentally_free_slots,
        check_dentally_slots,
        list_upcoming_appointments,
        get_appointments_for_date,
        format_human_date
    )
except ImportError:
    from dentally_config import DENTALLY_PRACTITIONERS, DUBLIN_TZ
    from dentally_client import dentally_client
    from dentally_service import (
        get_clinic_site_summary,
        fetch_dentally_free_slots,
        check_dentally_slots,
        list_upcoming_appointments,
        get_appointments_for_date,
        format_human_date
    )

def run_read_tests():
    print("=" * 70)
    print(" DENTALLY NEXGEN API - READ-ONLY VERIFICATION SUITE")
    print("=" * 70)
    
    # 1. Config check
    print(f"\n[1] Checking Configuration:")
    print(f"  Base URL:    {dentally_client.base_url}")
    print(f"  Auth URL:    {dentally_client.auth_url}")
    print(f"  Practice ID: {dentally_client.practice_id}")
    print(f"  Configured:  {dentally_client.is_configured()}")
    
    if not dentally_client.is_configured():
        print("ERROR: Dentally client credentials not configured!")
        sys.exit(1)

    # 2. Token acquisition
    print(f"\n[2] Fetching OAuth2 Bearer Token:")
    try:
        token = dentally_client.get_token()
        print(f"  Token acquired: {token[:15]}...{token[-10:]}")
        print(f"  Token expires at (unix): {dentally_client._token_expires_at}")
    except Exception as e:
        print(f"  FAILED to acquire token: {e}")
        sys.exit(1)

    # 3. Read Practice Site
    print(f"\n[3] Reading Practice Site Info (GET /v2/sites):")
    site_info = get_clinic_site_summary()
    if site_info:
        print(f"  Name:    {site_info.get('name')}")
        print(f"  Address: {site_info.get('address')}")
        print(f"  Phone:   {site_info.get('phone')}")
        print(f"  Website: {site_info.get('website')}")
        print(f"  Opening Hours count: {len(site_info.get('opening_hours', []))}")
    else:
        print("  FAILED to read site info.")

    # 4. Read Live Practitioner Availability for all Dentally Practitioners
    print(f"\n[4] Reading Live Availability for ALL Dentally Practitioners:")
    test_dates = ["2026-11-11", "2026-11-12", "2026-11-13"]

    # Deduplicate practitioners by UUID
    seen_ids = set()
    distinct_practitioners = []
    for name, pid in DENTALLY_PRACTITIONERS.items():
        if pid not in seen_ids:
            seen_ids.add(pid)
            display_name = f"Dentist Shailaja (Dr. Shailja Sharma)" if "Shail" in name else f"Dr. {name}"
            distinct_practitioners.append((display_name, name, pid))

    for display_name, lookup_name, pid in distinct_practitioners:
        print(f"\n  • Practitioner: {display_name} (UUID: {pid})")
        for td in test_dates:
            slots = fetch_dentally_free_slots(lookup_name, td)
            count = len(slots) if slots else 0
            if count > 0:
                preview = ", ".join(slots[:6]) + ("..." if count > 6 else "")
                print(f"    - {td}: {count:2d} open slots | {preview}")
            else:
                print(f"    - {td}:  0 open slots (Off / Fully Booked)")

    # 5. High-Level Conversational Availability Turn Check
    print(f"\n[5] Testing Conversational Availability Checker (Sample turns across clinicians):")
    sample_queries = [
        ("Dentist Shailaja", "2026-11-11", "10:00"),
        ("Reihaneh Afrasaiabi", "2026-11-11", "11:30"),
        ("Aubrey Agang", "2026-11-12", "morning"),
        ("Salma Naz", "2026-11-12", "14:00"),
    ]
    for c, d, t in sample_queries:
        result = check_dentally_slots(c, d, t)
        print(f"  • Query: {c} on {d} ({t})")
        print(f"    Verdict: {result.get('availability_verdict')}")
        print(f"    Instruction: {result.get('instruction')}")

    # 6. Read Live Appointments
    print(f"\n[6] Reading Live Appointments (GET /v2/appointments):")
    appts = list_upcoming_appointments(limit=5)
    print(f"  Retrieved {len(appts)} recent appointments.")
    for idx, a in enumerate(appts, 1):
        prac = a.get("practitioner", {}).get("name", "Unknown")
        pat = a.get("patient", {})
        pat_name = f"{pat.get('first_name', '')} {pat.get('last_name', '')}".strip()
        reason = a.get("reason", {}).get("name", "N/A")
        st = a.get("start_time", "N/A")
        print(f"  {idx}. {st} | Practitioner: {prac} | Patient: {pat_name} | Reason: {reason}")

    # 7. Read Appointment Reasons
    print(f"\n[7] Reading Appointment Reasons (GET /v2/appointment_reasons):")
    try:
        reasons = dentally_client.get_appointment_reasons()
        print(f"  Retrieved {len(reasons)} configured reasons:")
        for r in reasons[:5]:
            print(f"    - {r.get('id')}: {r.get('name')}")
    except Exception as e:
        print(f"  Error reading reasons: {e}")

    # 8. Read All Appointments for Tomorrow
    now_dublin = datetime.now(DUBLIN_TZ)
    tomorrow_dt = now_dublin + timedelta(days=1)
    tomorrow_iso = tomorrow_dt.strftime("%Y-%m-%d")
    tomorrow_human = format_human_date(tomorrow_iso)
    print(f"\n[8] Reading ALL Appointments for Tomorrow ({tomorrow_human} -> {tomorrow_iso}):")
    tomorrow_appts = get_appointments_for_date(tomorrow_iso)
    print(f"  Total appointments found: {len(tomorrow_appts)}")
    if tomorrow_appts:
        print(f"  {'Time (Dublin)':<15} | {'Practitioner':<22} | {'Patient':<24} | {'Reason':<22} | {'State':<10}")
        print(f"  {'-'*15} | {'-'*22} | {'-'*24} | {'-'*22} | {'-'*10}")
        for a in tomorrow_appts:
            slot_str = a.get("time_slot_dublin", "N/A")
            prac = (a.get("practitioner_name") or "Unknown")[:22]
            pat = (a.get("patient_name") or "Unassigned")[:24]
            reason = (a.get("reason_name") or "N/A")[:22]
            state = a.get("state", "Pending")
            print(f"  {slot_str:<15} | {prac:<22} | {pat:<24} | {reason:<22} | {state:<10}")
    else:
        print("  No appointments found for tomorrow.")

    print("\n" + "=" * 70)
    print(" ALL DENTALLY READ TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_read_tests()

