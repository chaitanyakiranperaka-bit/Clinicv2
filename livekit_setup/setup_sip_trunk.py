#!/usr/bin/env python3
"""
Configures LiveKit Inbound SIP Trunk & Dispatch Rule for VoIPLine.ie.
Usage:
    python livekit_setup/setup_sip_trunk.py --phone +35317267740
"""
import argparse
import asyncio
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from config import LIVEKIT_URL, LIVEKIT_API_KEY, LIVEKIT_API_SECRET, normalize_phone
from livekit import api


def _get_public_ip() -> str:
    for url in ("http://checkip.amazonaws.com", "https://ifconfig.me/ip"):
        try:
            with urllib.request.urlopen(url, timeout=3) as resp:
                return resp.read().decode("utf-8").strip()
        except Exception:
            pass
    return "<YOUR_EC2_PUBLIC_IP>"


def _phone_variants(phone: str) -> list:
    """Returns E.164 (+353...), stripped (353...), and Irish national (0...) variants so any SIP To header matches."""
    e164 = normalize_phone(phone)
    variants = []
    for candidate in (
        e164,
        e164.lstrip("+"),
        ("0" + e164[4:]) if e164.startswith("+353") else phone.strip(),
        phone.strip(),
    ):
        if candidate and candidate not in variants:
            variants.append(candidate)
    return variants


async def configure_voipline_sip(phone: str, auth_user: str = "", auth_pass: str = ""):
    if not LIVEKIT_API_KEY or not LIVEKIT_API_SECRET:
        print("❌ Error: LIVEKIT_API_KEY and LIVEKIT_API_SECRET must be set in .env first.")
        print("   Run: bash livekit_setup/install_livekit_ubuntu.sh")
        sys.exit(1)

    lk_http_url = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")
    lkapi = api.LiveKitAPI(url=lk_http_url, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)

    try:
        numbers = _phone_variants(phone)
        print(f"[1/3] Cleaning up any old clinic SIP trunks & dispatch rules on {lk_http_url}...")

        existing_rules = await lkapi.sip.list_dispatch_rule(api.ListSIPDispatchRuleRequest())
        for r in existing_rules.items:
            if r.name == "star-clinic-deirdre-dispatch":
                await lkapi.sip.delete_dispatch_rule(
                    api.DeleteSIPDispatchRuleRequest(sip_dispatch_rule_id=r.sip_dispatch_rule_id)
                )

        existing_trunks = await lkapi.sip.list_inbound_trunk(api.ListSIPInboundTrunkRequest())
        for t in existing_trunks.items:
            if t.name == "voipline-ie-inbound":
                await lkapi.sip.delete_trunk(
                    api.DeleteSIPTrunkRequest(sip_trunk_id=t.sip_trunk_id)
                )

        print(f"[2/3] Creating Inbound SIP Trunk for VoIPLine.ie numbers: {numbers}...")
        trunk_info = api.SIPInboundTrunkInfo(
            name="voipline-ie-inbound",
            numbers=numbers,
            auth_username=auth_user or "",
            auth_password=auth_pass or "",
            krisp_enabled=False,
        )
        trunk = await lkapi.sip.create_inbound_trunk(
            api.CreateSIPInboundTrunkRequest(trunk=trunk_info)
        )
        print(f"  ✓ Created Inbound Trunk ID: {trunk.sip_trunk_id}")

        print("[3/3] Creating SIP Dispatch Rule (routes each caller into room 'sip-<caller>')...")
        dispatch_req = api.CreateSIPDispatchRuleRequest(
            name="star-clinic-deirdre-dispatch",
            trunk_ids=[trunk.sip_trunk_id],
            rule=api.SIPDispatchRule(
                dispatch_rule_individual=api.SIPDispatchRuleIndividual(
                    room_prefix="sip-",
                )
            ),
        )
        dispatch = await lkapi.sip.create_dispatch_rule(dispatch_req)
        print(f"  ✓ Created Dispatch Rule ID: {dispatch.sip_dispatch_rule_id}")

        pub_ip = _get_public_ip()
        e164_num = numbers[0]
        print("\n" + "=" * 78)
        print(" ✅ VOIPLINE.IE SIP TRUNK REGISTERED IN LIVEKIT!")
        print("=" * 78)
        print(f" • Clinic Phone Number:      {e164_num} (accepts: {', '.join(numbers)})")
        print(f" • Inbound Trunk ID:         {trunk.sip_trunk_id}")
        print(f" • Dispatch Rule ID:         {dispatch.sip_dispatch_rule_id}")
        print("-" * 78)
        print(" 👉 PASTE THIS SIP URI INTO YOUR VOIPLINE.IE PORTAL (Call Flow -> SIP URI):")
        print(f"    {e164_num}@{pub_ip}:5060")
        print(f"    (or full URI: sip:{e164_num}@{pub_ip}:5060)")
        print("=" * 78)
    finally:
        await lkapi.aclose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Register VoIPLine.ie Inbound SIP Trunk in LiveKit")
    parser.add_argument("--phone", required=True, help="VoIPLine.ie phone number (e.g. +35317267740 or 017267740)")
    parser.add_argument("--auth-user", default="", help="Optional SIP auth username")
    parser.add_argument("--auth-pass", default="", help="Optional SIP auth password")
    args = parser.parse_args()
    asyncio.run(configure_voipline_sip(args.phone, args.auth_user, args.auth_pass))
