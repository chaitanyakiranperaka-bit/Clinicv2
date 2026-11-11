import os
import re
import json
import asyncio
from datetime import datetime, timedelta
import boto3
from botocore.config import Config
from config import AWS_REGION, BEDROCK_MODEL_ID, BEDROCK_TOOLS, DUBLIN_TZ, KNOWN_PATIENTS, get_known_patient
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

def resolve_agreed_slot_time(tool_input: dict, messages: list) -> str:
    """Extracts slot_time from tool_input or scans conversation history backwards for the agreed time."""
    raw_slot = tool_input.get("slot_time")
    if raw_slot:
        parsed = calendar_service.parse_time_preference(raw_slot)
        if parsed:
            return parsed

    # If missing from tool_input, search backwards in conversation history for the quoted time
    for m in reversed(messages):
        content = m.get("content", [])
        for block in content:
            txt = ""
            if isinstance(block, dict) and "text" in block:
                txt = block["text"]
            elif isinstance(block, str):
                txt = block
            if txt:
                parsed = calendar_service.parse_time_preference(txt)
                if parsed:
                    return parsed
    return "09:00"

def resolve_agreed_date(tool_input: dict, messages: list) -> str:
    """Extracts date from tool_input or scans conversation history backwards for the agreed date."""
    now_dublin = datetime.now(DUBLIN_TZ)
    raw_date = tool_input.get("date")
    if raw_date:
        try:
            dt = datetime.strptime(raw_date.strip(), "%Y-%m-%d").replace(tzinfo=DUBLIN_TZ)
            if dt.date() >= now_dublin.date():
                return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    for m in reversed(messages):
        content = m.get("content", [])
        for block in content:
            txt = ""
            if isinstance(block, dict) and "text" in block:
                txt = block["text"]
            elif isinstance(block, str):
                txt = block
            if txt:
                parsed = calendar_service.parse_date_preference(txt, now_dublin)
                if parsed:
                    return parsed
    return now_dublin.strftime("%Y-%m-%d")

def extract_text_tool_calls(text: str):
    """
    Extracts XML-style (<function=NAME> <parameter=KEY> VAL </parameter> </function>)
    or JSON-style (<tool_call> {...} </tool_call>) tool calls that Qwen models
    sometimes emit in plain text blocks when Converse API does not intercept them.
    Returns (tool_calls_list, clean_spoken_text).
    """
    if not text or not isinstance(text, str):
        return [], ""

    tool_calls = []
    clean_text = text

    # 1. XML format: <function=NAME> <parameter=KEY> VAL </parameter> </function>
    xml_matches = list(re.finditer(r"<function=([a-zA-Z0-9_]+)>(.*?)</function>(?:\s*</tool_call>)?", clean_text, re.DOTALL))
    for m in xml_matches:
        t_name = m.group(1).strip()
        body = m.group(2)
        params = {}
        for pm in re.finditer(r"<parameter=([a-zA-Z0-9_]+)>(.*?)</parameter>", body, re.DOTALL):
            params[pm.group(1).strip()] = pm.group(2).strip()
        tool_calls.append({"name": t_name, "input": params})

    if xml_matches:
        clean_text = re.sub(r"(?:<tool_call>)?\s*<function=.*?>(.*?)</function>(?:\s*</tool_call>)?", "", clean_text, flags=re.DOTALL)

    # 2. JSON format: <tool_call> {...} </tool_call>
    json_matches = list(re.finditer(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", clean_text, re.DOTALL))
    for jm in json_matches:
        try:
            data = json.loads(jm.group(1))
            t_name = data.get("name") or data.get("tool")
            t_args = data.get("arguments") or data.get("parameters") or data.get("input") or {}
            if t_name:
                tool_calls.append({"name": t_name, "input": t_args})
        except Exception:
            pass

    if json_matches:
        clean_text = re.sub(r"<tool_call>\s*\{.*?\}\s*</tool_call>", "", clean_text, flags=re.DOTALL)

    # 3. Clean any residual tool tags
    clean_text = re.sub(r"</?tool_call>", "", clean_text)
    clean_text = re.sub(r"<function=[^>]+>", "", clean_text)
    clean_text = re.sub(r"</?function>", "", clean_text)
    clean_text = re.sub(r"</?parameter(?:=[^>]+)?>", "", clean_text)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()

    return tool_calls, clean_text

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

    # 1. Native Bedrock toolUse blocks
    native_tool_calls = [
        {"toolUseId": b["toolUse"]["toolUseId"], "name": b["toolUse"]["name"], "input": b["toolUse"].get("input", {})}
        for b in output_msg.get("content", [])
        if "toolUse" in b
    ]

    # 2. Text-based tool calls from Qwen XML/JSON in plain text
    text_tool_calls = []
    preamble_spoken_parts = []
    for b in output_msg.get("content", []):
        if "text" in b:
            calls, clean_t = extract_text_tool_calls(b["text"])
            text_tool_calls.extend(calls)
            if clean_t:
                preamble_spoken_parts.append(clean_t)

    # Last user text for date/time inference
    last_user_text = ""
    for m in reversed(messages):
        if m.get("role") == "user":
            for c in m.get("content", []):
                if isinstance(c, dict) and "text" in c:
                    last_user_text = c["text"]
                    break
            if last_user_text:
                break

    matched = get_known_patient(caller_phone)

    async def run_tool(t_name: str, t_in: dict):
        print(f"[TOOL TRIGGERED]: {t_name} with {t_in}", flush=True)
        if on_tool_start:
            await on_tool_start(t_name)

        res = None
        if t_name == "check_calendar_slots":
            target_date = normalize_date(t_in.get("date"), last_user_text)
            raw_pref = t_in.get("time_preference")
            if not raw_pref or raw_pref in ("any", "morning", "afternoon"):
                detected_time = calendar_service.parse_time_preference(last_user_text)
                if detected_time:
                    raw_pref = detected_time
            res = await asyncio.to_thread(
                calendar_service.check_calendar_slots,
                t_in.get("clinician", "Dr. Yousuf"),
                target_date,
                raw_pref or "any"
            )
        elif t_name == "book_calendar_slot":
            target_date = resolve_agreed_date(t_in, messages)
            slot_time = resolve_agreed_slot_time(t_in, messages)
            patient_name = t_in.get("patient_name") or (matched["name"] if matched else "Caller")
            patient_dob = t_in.get("patient_dob") or (matched["dob"] if matched else "Unknown")
            cat = t_in.get("appointment_category") or "Routine GP"
            clinician = t_in.get("clinician", "Dr. Yousuf")
            res = await asyncio.to_thread(
                calendar_service.book_calendar_slot,
                clinician,
                target_date,
                slot_time,
                patient_name,
                patient_dob,
                caller_phone,
                cat
            )
            if res.get("success") and on_booking:
                await on_booking(res["booking"])
        elif t_name == "trigger_emergency_divert":
            cat = t_in.get("emergency_category", "Emergency")
            if on_emergency:
                await on_emergency(cat)
            res = {"status": "Alert logged. Instruct caller immediately to dial 999 or 112."}
        else:
            res = {"error": f"Unknown tool {t_name}"}

        if on_tool_log:
            await on_tool_log(f"{t_name}({json.dumps(t_in)}) completed")
        return res

    # Branch 1: Native Bedrock toolUse
    if native_tool_calls:
        tool_results_content = []
        for tc in native_tool_calls:
            res_data = await run_tool(tc["name"], tc["input"])
            tool_results_content.append({
                "toolResult": {
                    "toolUseId": tc["toolUseId"],
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

        spoken_parts = []
        for b in output_msg.get("content", []):
            if "text" in b:
                _, cl = extract_text_tool_calls(b["text"])
                if cl:
                    spoken_parts.append(cl)
        return " ".join(spoken_parts).strip()

    # Branch 2: Text-based tool calls (Qwen XML / JSON in plain text)
    elif text_tool_calls:
        for tc in text_tool_calls:
            res_data = await run_tool(tc["name"], tc["input"])

            if tc["name"] == "book_calendar_slot":
                if res_data.get("success"):
                    clinician_booked = res_data["booking"].get("clinician", tc["input"].get("clinician", "Dr. Yousuf"))
                    date_booked = res_data.get("formatted_date", tc["input"].get("date"))
                    time_booked = res_data.get("spoken_time") or calendar_service.format_spoken_time(res_data["booking"].get("slot_time", "10:00"))
                    spoken = (
                        f"Your appointment with {clinician_booked} has been "
                        f"booked for {date_booked} at "
                        f"{time_booked}. Is there anything else I can assist you with today?"
                    )
                else:
                    err = res_data.get("error", "that slot could not be booked")
                    spoken = f"I apologize, {err}. Would you prefer another time?"
                messages[-1] = {"role": "assistant", "content": [{"text": spoken}]}
                return spoken

            elif tc["name"] == "check_calendar_slots":
                verdict = res_data.get("instruction") or res_data.get("availability_verdict")
                follow_msg = {
                    "role": "user",
                    "content": [{
                        "text": f"Calendar check result: {json.dumps(res_data)}. Follow instruction: {verdict}. Tell the caller the availability in 1 natural sentence."
                    }]
                }
                messages.append(follow_msg)
                try:
                    follow_up = await asyncio.to_thread(
                        bedrock_client.converse,
                        modelId=BEDROCK_MODEL_ID,
                        system=[{"text": system_prompt}],
                        messages=messages,
                        inferenceConfig={"maxTokens": 80, "temperature": 0.1}
                    )
                    f_msg = follow_up["output"]["message"]
                    messages.append(f_msg)
                    spoken_parts = []
                    for b in f_msg.get("content", []):
                        if "text" in b:
                            _, cl = extract_text_tool_calls(b["text"])
                            if cl:
                                spoken_parts.append(cl)
                    if spoken_parts:
                        return " ".join(spoken_parts).strip()
                except Exception as e:
                    print(f"[Bedrock Slot Followup Error]: {e}", flush=True)

                fallback_text = res_data.get("instruction", res_data.get("availability_verdict", "I found an available slot."))
                clean_fallback = re.sub(r"^Tell the caller:\s*", "", fallback_text, flags=re.IGNORECASE).strip("'\" ")
                messages[-1] = {"role": "assistant", "content": [{"text": clean_fallback}]}
                return clean_fallback

    # Branch 3: Standard text response
    spoken_parts = []
    for b in output_msg.get("content", []):
        if "text" in b:
            _, cl = extract_text_tool_calls(b["text"])
            if cl:
                spoken_parts.append(cl)
    return " ".join(spoken_parts).strip()
