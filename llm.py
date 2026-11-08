import os
import json
import asyncio
from datetime import datetime, timedelta
import boto3
from botocore.config import Config
from config import AWS_REGION, BEDROCK_MODEL_ID, BEDROCK_TOOLS, DUBLIN_TZ, KNOWN_PATIENTS
import calendar_service

print(f"[INIT LLM] Connecting to Bedrock ({AWS_REGION} | {BEDROCK_MODEL_ID})...", flush=True)
boto_config = Config(connect_timeout=4, read_timeout=12, retries={"max_attempts": 1})
bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=boto_config)

def normalize_date(date_str: str, user_text: str = "") -> str:
    """Safely normalizes input date string to YYYY-MM-DD in Dublin timezone, preventing past dates and hallucinated weekdays."""
    now_dublin = datetime.now(DUBLIN_TZ)
    today_iso = now_dublin.strftime("%Y-%m-%d")

    # If the caller verbally requested a specific day/date, resolve it deterministically:
    detected_date = calendar_service.parse_date_preference(user_text, now_dublin) if user_text else None
    if detected_date:
        return detected_date

    if not date_str or not isinstance(date_str, str):
        return today_iso
    try:
        dt = datetime.strptime(date_str.strip(), "%Y-%m-%d").replace(tzinfo=DUBLIN_TZ)
        # Prevent past dates! If an LLM hallucinated a past date, fall back to today or next open clinic day
        if dt.date() < now_dublin.date():
            if now_dublin.weekday() == 6:
                return (now_dublin + timedelta(days=1)).strftime("%Y-%m-%d")
            return today_iso
        return dt.strftime("%Y-%m-%d")
    except Exception:
        return today_iso

async def execute_turn(messages: list, system_prompt: str, caller_phone: str, on_tool_log=None, on_booking=None, on_emergency=None, on_tool_start=None):
    try:
        response = await asyncio.to_thread(
            bedrock_client.converse,
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": system_prompt}],
            messages=messages,
            toolConfig=BEDROCK_TOOLS,
            inferenceConfig={"maxTokens": 140, "temperature": 0.1}
        )
    except Exception as e:
        print(f"[Bedrock Converse Error]: {e}", flush=True)
        return "I apologize, I am experiencing a brief system delay. Could you please repeat that?"

    output_msg = response["output"]["message"]
    messages.append(output_msg)

    has_tool_use = any("toolUse" in block for block in output_msg.get("content", []))
    if response.get("stopReason") == "tool_use" or has_tool_use:
        tool_results_content = []
        for block in output_msg["content"]:
            if "toolUse" in block:
                t_use = block["toolUse"]
                t_name = t_use["name"]
                t_id = t_use["toolUseId"]
                t_in = t_use.get("input", {})

                print(f"[TOOL TRIGGERED]: {t_name} with {t_in}", flush=True)
                if on_tool_start:
                    await on_tool_start(t_name)
                if on_tool_log:
                    await on_tool_log(f"{t_name}({json.dumps(t_in)})")

                matched = KNOWN_PATIENTS.get(caller_phone)

                last_user_text = ""
                for m in reversed(messages):
                    if m.get("role") == "user":
                        for c in m.get("content", []):
                            if isinstance(c, dict) and "text" in c:
                                last_user_text = c["text"]
                                break
                        if last_user_text:
                            break

                if t_name == "check_calendar_slots":
                    target_date = normalize_date(t_in.get("date"), last_user_text)
                    raw_pref = t_in.get("time_preference")
                    # If time_preference was not passed or is generic, check if the caller mentioned a time
                    if not raw_pref or raw_pref in ("any", "morning", "afternoon"):
                        detected_time = calendar_service.parse_time_preference(last_user_text)
                        if detected_time:
                            raw_pref = detected_time

                    res_data = await asyncio.to_thread(
                        calendar_service.check_calendar_slots,
                        t_in.get("clinician", "Dr. Yousuf"),
                        target_date,
                        raw_pref or "any"
                    )
                elif t_name == "book_calendar_slot":
                    target_date = normalize_date(t_in.get("date"), last_user_text)
                    res_data = await asyncio.to_thread(
                        calendar_service.book_calendar_slot,
                        t_in.get("clinician", "Dr. Yousuf"),
                        target_date,
                        t_in.get("slot_time", "09:00"),
                        t_in.get("patient_name", matched["name"] if matched else "Unknown"),
                        t_in.get("patient_dob", matched["dob"] if matched else "Unknown"),
                        caller_phone,
                        t_in.get("appointment_category", "Routine GP")
                    )
                    if res_data.get("success") and on_booking:
                        await on_booking(res_data["booking"])
                elif t_name == "trigger_emergency_divert":
                    cat = t_in.get("emergency_category", "Emergency")
                    if on_emergency:
                        await on_emergency(cat)
                    res_data = {"status": "Alert logged. Instruct caller immediately to dial 999 or 112."}
                else:
                    res_data = {"error": "Unknown tool"}

                tool_results_content.append({
                    "toolResult": {
                        "toolUseId": t_id,
                        "content": [{"json": res_data}]
                    }
                })

        messages.append({"role": "user", "content": tool_results_content})
        try:
            follow_up = await asyncio.to_thread(
                bedrock_client.converse,
                modelId=BEDROCK_MODEL_ID,
                system=[{"text": system_prompt}],
                messages=messages,
                toolConfig=BEDROCK_TOOLS,
                inferenceConfig={"maxTokens": 100, "temperature": 0.1}
            )
            output_msg = follow_up["output"]["message"]
            messages.append(output_msg)
        except Exception as e:
            print(f"[Bedrock Followup Error]: {e}", flush=True)
            return "I have updated the schedule, but had a brief network delay. Could you please confirm if you need anything else?"

    spoken_parts = [b["text"] for b in output_msg["content"] if "text" in b]
    return " ".join(spoken_parts).strip()
