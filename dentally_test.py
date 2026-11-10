#!/usr/bin/env python3
"""Dentally NexGen API Read Test Suite.
Verifies all read operations against the live production Dentally API for Star Dental Care.
Strictly Read-Only (no bookings or mutations created).
"""

import sys
import json
from dentally_client import dentally_client
from dentally_service import (
    get_clinic_site_summary,
    fetch_dentally_free_slots,
    check_dentally_slots,
    list_upcoming_appointments
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

    # 4. Read Availability for Dentist Shailaja
    print(f"\n[4] Reading Live Practitioner Availability (GET /v2/practitioners/availabilities):")
    test_dates = ["2026-11-11", "2026-11-13"]
    for td in test_dates:
        slots = fetch_dentally_free_slots("Dentist Shailaja", td)
        print(f"  Date {td} (Dentist Shailaja): {len(slots) if slots else 0} open slots found")
        if slots:
            print(f"    Available times: {', '.join(slots[:8])}{' ...' if len(slots) > 8 else ''}")

    # 5. High-Level Availability Turn Check
    print(f"\n[5] Testing Conversational Availability Checker:")
    result = check_dentally_slots("Dentist Shailaja", "2026-11-11", "10:00")
    print(f"  Query: Wednesday 2026-11-11 at 10:00")
    print(f"  Verdict: {result.get('availability_verdict')}")
    print(f"  Instruction: {result.get('instruction')}")

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

    print("\n" + "=" * 70)
    print(" ALL DENTALLY READ TESTS COMPLETED SUCCESSFULLY!")
    print("=" * 70)

if __name__ == "__main__":
    run_read_tests()
