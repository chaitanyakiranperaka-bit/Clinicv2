import os
import re
import copy
import json
import asyncio
from typing import Optional
from datetime import datetime, timedelta
import boto3
from botocore.config import Config
from config import AWS_REGION, BEDROCK_MODEL_ID, BEDROCK_TOOLS, DUBLIN_TZ, KNOWN_PATIENTS, get_known_patient
import calendar_service

print(f"[INIT LLM] Connecting to Bedrock ({AWS_REGION} | {BEDROCK_MODEL_ID})...", flush=True)
boto_config = Config(connect_timeout=4, read_timeout=12, retries={"max_attempts": 1})
bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=boto_config)

MAX_TOOL_HOPS = 4


def sanitize_conversation_history(messages: list) -> list:
    """
    Ensures conversation history strictly satisfies AWS Bedrock Converse API invariants:
    1. Every assistant toolUse block has a matching user toolResult block immediately following it.
    2. Every user toolResult block has a matching assistant toolUse block immediately preceding it.
    3. No empty content blocks or empty messages exist.
    4. Roles strictly alternate (user -> assistant -> user -> assistant), starting with user.
    """
    if not messages:
        return []

    cleaned = copy.deepcopy(messages)

    # Pass 1: Validate toolUse <-> toolResult pairing across adjacent messages
    for i, msg in enumerate(cleaned):
        content = msg.get("content", [])
        if not isinstance(content, list):
            msg["content"] = []
            continue

        if msg.get("role") == "assistant":
            next_msg = cleaned[i + 1] if i + 1 < len(cleaned) else None
            next_result_ids = set()
            if next_msg and next_msg.get("role") == "user":
                for b in next_msg.get("content", []):
                    if isinstance(b, dict) and "toolResult" in b:
                        tid = b["toolResult"].get("toolUseId")
                        if tid:
                            next_result_ids.add(tid)

            valid_blocks = []
            for b in content:
                if isinstance(b, dict) and "toolUse" in b:
                    tid = b["toolUse"].get("toolUseId")
                    if tid and tid in next_result_ids:
                        valid_blocks.append(b)
                elif isinstance(b, dict) and "text" in b:
                    if str(b["text"]).strip():
                        valid_blocks.append({"text": str(b["text"]).strip()})
            msg["content"] = valid_blocks

        elif msg.get("role") == "user":
            prev_msg = cleaned[i - 1] if i > 0 else None
            prev_use_ids = set()
            if prev_msg and prev_msg.get("role") == "assistant":
                for b in prev_msg.get("content", []):
                    if isinstance(b, dict) and "toolUse" in b:
                        tid = b["toolUse"].get("toolUseId")
                        if tid:
                            prev_use_ids.add(tid)

            valid_blocks = []
            for b in content:
                if isinstance(b, dict) and "toolResult" in b:
                    tid = b["toolResult"].get("toolUseId")
                    if tid and tid in prev_use_ids:
                        valid_blocks.append(b)
                elif isinstance(b, dict) and "text" in b:
                    if str(b["text"]).strip():
                        valid_blocks.append({"text": str(b["text"]).strip()})
            msg["content"] = valid_blocks

    # Filter out messages that became empty
    non_empty = [m for m in cleaned if m.get("content")]

    # Pass 2: Merge consecutive messages with the same role
    merged = []
    for m in non_empty:
        if merged and merged[-1]["role"] == m["role"]:
            merged[-1]["content"].extend(m["content"])
        else:
            merged.append(m)

    # Ensure conversation starts with a user message
    if merged and merged[0]["role"] != "user":
        merged.insert(0, {"role": "user", "content": [{"text": "Hello, I am calling the clinic."}]})

    return merged


def _fallback_speech_from_tool_result(res_data: Optional[dict]) -> str:
    """Produces a clean, natural spoken response directly from tool output if LLM follow-up fails or is empty."""
    if not res_data or not isinstance(res_data, dict):
        return "I have checked the schedule for you. How would you like to proceed?"

    if res_data.get("success") and "booking" in res_data:
        b = res_data["booking"]
        clinician = b.get("clinician", "the clinician")
        f_date = res_data.get("formatted_date") or b.get("formatted_date") or b.get("date", "")
        s_time = res_data.get("spoken_time") or b.get("spoken_time") or calendar_service.format_spoken_time(b.get("slot_time", ""))
        return f"I have booked your appointment with {clinician} for {f_date} at {s_time}. Is there anything else I can help you with today?"

    instr = res_data.get("instruction")
    if instr and isinstance(instr, str):
        clean_instr = re.sub(r"\s*CRITICAL:.*$", "", instr, flags=re.IGNORECASE | re.DOTALL)
        clean_instr = re.sub(r"^Tell the caller:\s*", "", clean_instr, flags=re.IGNORECASE).strip("'\" ")
        if clean_instr:
            return clean_instr

    verdict = res_data.get("availability_verdict") or res_data.get("message")
    if verdict and isinstance(verdict, str):
        return verdict

    err = res_data.get("error")
    if err and isinstance(err, str):
        return f"I apologize, {err} Would you prefer another time?"

    return "I have checked the schedule for you. Would you like me to check another time?"


def find_last_calendar_check(messages: list, target_date: str = "") -> Optional[dict]:
    """Retrieves the most recent check_calendar_slots (or slot collision) result data from conversation history."""
    fallback_match = None
    for m in reversed(messages):
        content = m.get("content", [])
        for block in content:
            if isinstance(block, dict):
                candidate = None
                # Native Bedrock toolResult format
                if "toolResult" in block:
                    for item in block["toolResult"].get("content", []):
                        if isinstance(item, dict) and "json" in item:
                            j = item["json"]
                            if isinstance(j, dict) and ("suggested_slots_to_quote" in j or "all_open_slots" in j or "availability_verdict" in j):
                                candidate = j
                                break
                # Text block with JSON
                elif "text" in block:
                    txt = block["text"]
                    if "Calendar check result:" in txt:
                        m_json = re.search(r"Calendar check result:\s*(\{.*\})", txt)
                        if m_json:
                            try:
                                candidate = json.loads(m_json.group(1))
                            except Exception:
                                pass

                if candidate:
                    if not target_date or candidate.get("date") == target_date:
                        return candidate
                    if fallback_match is None:
                        fallback_match = candidate
    return fallback_match


def normalize_date(date_str: str, user_text: str = "") -> str:
    """Safely normalizes input date string to YYYY-MM-DD in Dublin timezone, preventing past dates and past times."""
    now_dublin = datetime.now(DUBLIN_TZ)
    today_iso = now_dublin.strftime("%Y-%m-%d")

    # Prioritize explicit valid YYYY-MM-DD from tool argument when provided; otherwise infer from user_text
    detected_date = calendar_service.parse_date_preference(user_text, now_dublin) if user_text else None
    target = date_str or detected_date or today_iso

    try:
        dt = datetime.strptime(target.strip(), "%Y-%m-%d").replace(tzinfo=DUBLIN_TZ)
        # Advance any past dates by 7 days to next week
        while dt.date() < now_dublin.date():
            dt += timedelta(days=7)

        # If target date is today, check if caller requested a time that has already passed today
        if dt.date() == now_dublin.date() and user_text:
            pref_time = calendar_service.parse_time_preference(user_text)
            is_explicit_today = bool(re.search(r"\btoday\b", user_text.lower()))
            if pref_time and pref_time < now_dublin.strftime("%H:%M") and not is_explicit_today:
                dt += timedelta(days=7)

        return dt.strftime("%Y-%m-%d")
    except Exception:
        return detected_date or today_iso


def resolve_agreed_date(tool_input: dict, messages: list) -> str:
    """Extracts date from tool_input or scans conversation history backwards for the agreed date."""
    now_dublin = datetime.now(DUBLIN_TZ)
    today_iso = now_dublin.strftime("%Y-%m-%d")

    last_check = find_last_calendar_check(messages)
    raw_date = tool_input.get("date")

    # If the last check redirected a full/closed requested_date to the next available date, use the available date
    if last_check and last_check.get("date") and last_check.get("available"):
        if not raw_date or raw_date.strip() == last_check.get("requested_date"):
            return last_check["date"].strip()

    # 1. Prioritize explicit valid date provided in tool_input
    if raw_date:
        try:
            dt = datetime.strptime(raw_date.strip(), "%Y-%m-%d").replace(tzinfo=DUBLIN_TZ)
            while dt.date() < now_dublin.date():
                dt += timedelta(days=7)
            return dt.strftime("%Y-%m-%d")
        except Exception:
            pass

    # 2. Check if a recent check_calendar_slots tool execution confirmed a date
    if last_check and last_check.get("date"):
        try:
            check_dt = datetime.strptime(last_check["date"].strip(), "%Y-%m-%d").replace(tzinfo=DUBLIN_TZ)
            if check_dt.date() >= now_dublin.date():
                return last_check["date"]
        except Exception:
            pass

    # 3. Search backwards in messages
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
    return today_iso


def resolve_agreed_slot_time(tool_input: dict, messages: list, target_date: str = "") -> Optional[str]:
    """Extracts slot_time from tool_input, confirmed tool results, or conversation history.
    Returns None if no valid slot time can be determined (never defaults to an arbitrary time).
    """
    now_dublin = datetime.now(DUBLIN_TZ)
    today_iso = now_dublin.strftime("%Y-%m-%d")
    is_today = (target_date == today_iso)
    cutoff_str = now_dublin.strftime("%H:%M")

    # 1. If explicit slot_time provided in tool_input
    raw_slot = tool_input.get("slot_time")
    if raw_slot:
        parsed = calendar_service.parse_time_preference(raw_slot)
        if parsed and parsed in calendar_service.ALL_DAILY_SLOTS:
            if not is_today or parsed >= cutoff_str:
                return parsed

    # 2. Check the most recent user utterance FIRST (caller may have picked a specific slot like "11.45 am" or "2.15 pm")
    for m in reversed(messages):
        if m.get("role") == "user":
            content = m.get("content", [])
            for block in content:
                txt = ""
                if isinstance(block, dict) and "text" in block:
                    txt = block["text"]
                elif isinstance(block, str):
                    txt = block
                if txt:
                    parsed = calendar_service.parse_time_preference(txt)
                    if parsed and parsed in calendar_service.ALL_DAILY_SLOTS and (not is_today or parsed >= cutoff_str):
                        return parsed
            break

    # 3. Check the most recent check_calendar_slots / collision result for target_date
    last_check = find_last_calendar_check(messages, target_date=target_date)
    if last_check and (not target_date or not last_check.get("date") or last_check.get("date") == target_date):
        suggested = last_check.get("suggested_slots_to_quote", [])
        for s in suggested:
            if not is_today or s >= cutoff_str:
                return s
        all_open = last_check.get("all_open_slots", [])
        for s in all_open:
            if not is_today or s >= cutoff_str:
                return s

    # 4. Search backwards in conversation history for explicitly mentioned valid clinic slots
    for m in reversed(messages):
        content = m.get("content", [])
        for block in content:
            txt = ""
            if isinstance(block, dict) and "text" in block:
                txt = block["text"]
            elif isinstance(block, str):
                txt = block
            if txt and "Calendar check result:" not in txt:
                parsed = calendar_service.parse_time_preference(txt)
                if parsed and parsed in calendar_service.ALL_DAILY_SLOTS and (not is_today or parsed >= cutoff_str):
                    return parsed

    return None


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


def _extract_spoken_from_message(msg: dict) -> str:
    spoken_parts = []
    for b in msg.get("content", []):
        if isinstance(b, dict) and "text" in b:
            _, cl = extract_text_tool_calls(b["text"])
            if cl:
                spoken_parts.append(cl)
    return " ".join(spoken_parts).strip()


async def execute_turn(messages: list, system_prompt: str, caller_phone: str, on_tool_log=None, on_booking=None, on_emergency=None, on_tool_start=None, on_tool_result=None):
    # Work on a sanitized transactional copy so errors or cancellations never corrupt live conversation history
    working_messages = sanitize_conversation_history(messages)

    # Last user text for date/time inference
    last_user_text = ""
    for m in reversed(working_messages):
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
            await on_tool_start(t_name, t_in)

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
            target_date = resolve_agreed_date(t_in, working_messages)
            slot_time = resolve_agreed_slot_time(t_in, working_messages, target_date)
            clinician = t_in.get("clinician", "Dr. Yousuf")
            if not slot_time:
                # Never book an unconfirmed default time; check open slots for target_date and prompt caller
                check_res = await asyncio.to_thread(
                    calendar_service.check_calendar_slots,
                    clinician,
                    target_date,
                    "any"
                )
                if check_res.get("available") and check_res.get("suggested_slots_to_quote"):
                    res = {
                        "success": False,
                        "date": target_date,
                        "error": f"No specific time slot was confirmed for {target_date}.",
                        "suggested_slots_to_quote": check_res["suggested_slots_to_quote"],
                        "all_open_slots": check_res.get("all_open_slots", []),
                        "instruction": check_res["instruction"]
                    }
                else:
                    res = check_res
            else:
                patient_name = t_in.get("patient_name") or (matched["name"] if matched else "Caller")
                patient_dob = t_in.get("patient_dob") or (matched["dob"] if matched else "Unknown")
                cat = t_in.get("appointment_category") or "Routine GP"
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

        if on_tool_result:
            await on_tool_result(t_name, t_in, res)
        if on_tool_log:
            await on_tool_log(f"{t_name}({json.dumps(t_in)}) completed")
        return res

    try:
        response = await asyncio.to_thread(
            bedrock_client.converse,
            modelId=BEDROCK_MODEL_ID,
            system=[{"text": system_prompt}],
            messages=working_messages,
            toolConfig=BEDROCK_TOOLS,
            inferenceConfig={"maxTokens": 140, "temperature": 0.1}
        )
    except Exception as e:
        print(f"[Bedrock Converse Error]: {e}", flush=True)
        fallback_err = "I apologize, I am experiencing a brief system delay. Could you please repeat that?"
        working_messages.append({"role": "assistant", "content": [{"text": fallback_err}]})
        messages[:] = sanitize_conversation_history(working_messages)
        return fallback_err

    output_msg = response["output"]["message"]
    working_messages.append(output_msg)
    last_tool_result = None

    # Bounded Multi-Hop Tool Execution Loop (supports chained check -> check or check -> book calls)
    for hop in range(MAX_TOOL_HOPS):
        native_tool_calls = [
            {"toolUseId": b["toolUse"]["toolUseId"], "name": b["toolUse"]["name"], "input": b["toolUse"].get("input", {})}
            for b in output_msg.get("content", [])
            if isinstance(b, dict) and "toolUse" in b
        ]

        text_tool_calls = []
        for b in output_msg.get("content", []):
            if isinstance(b, dict) and "text" in b:
                calls, _ = extract_text_tool_calls(b["text"])
                text_tool_calls.extend(calls)

        # No more tool calls in output_msg -> return spoken response
        if not native_tool_calls and not text_tool_calls:
            spoken = _extract_spoken_from_message(output_msg)
            if not spoken and last_tool_result is not None:
                spoken = _fallback_speech_from_tool_result(last_tool_result)
                output_msg["content"] = [{"text": spoken}]
            messages[:] = sanitize_conversation_history(working_messages)
            return spoken

        # Case A: Native Bedrock toolUse blocks
        if native_tool_calls:
            tool_results_content = []
            for tc in native_tool_calls:
                res_data = await run_tool(tc["name"], tc["input"])
                last_tool_result = res_data
                tool_results_content.append({
                    "toolResult": {
                        "toolUseId": tc["toolUseId"],
                        "content": [{"json": res_data}]
                    }
                })
            working_messages.append({"role": "user", "content": tool_results_content})

            try:
                follow_up = await asyncio.to_thread(
                    bedrock_client.converse,
                    modelId=BEDROCK_MODEL_ID,
                    system=[{"text": system_prompt}],
                    messages=working_messages,
                    toolConfig=BEDROCK_TOOLS,
                    inferenceConfig={"maxTokens": 120, "temperature": 0.1}
                )
                output_msg = follow_up["output"]["message"]
                working_messages.append(output_msg)
                continue
            except Exception as e:
                print(f"[Bedrock Followup Error (hop {hop + 1})]: {e}", flush=True)
                spoken = _fallback_speech_from_tool_result(last_tool_result)
                working_messages.append({"role": "assistant", "content": [{"text": spoken}]})
                messages[:] = sanitize_conversation_history(working_messages)
                return spoken

        # Case B: Text-based tool calls (Qwen XML / JSON in plain text)
        elif text_tool_calls:
            # Strip raw tool tags from the assistant message in history
            cleaned_preamble = _extract_spoken_from_message(output_msg) or "Let me check that for you."
            working_messages[-1] = {"role": "assistant", "content": [{"text": cleaned_preamble}]}

            for tc in text_tool_calls:
                res_data = await run_tool(tc["name"], tc["input"])
                last_tool_result = res_data

                if tc["name"] == "book_calendar_slot" and res_data.get("success"):
                    spoken = _fallback_speech_from_tool_result(res_data)
                    working_messages[-1] = {"role": "assistant", "content": [{"text": spoken}]}
                    messages[:] = sanitize_conversation_history(working_messages)
                    return spoken

            verdict = (last_tool_result or {}).get("instruction") or (last_tool_result or {}).get("availability_verdict") or ""
            follow_msg = {
                "role": "user",
                "content": [{
                    "text": f"Calendar check result: {json.dumps(last_tool_result)}. Follow instruction: {verdict}. Respond to the caller in 1 natural sentence."
                }]
            }
            working_messages.append(follow_msg)
            try:
                follow_up = await asyncio.to_thread(
                    bedrock_client.converse,
                    modelId=BEDROCK_MODEL_ID,
                    system=[{"text": system_prompt}],
                    messages=working_messages,
                    toolConfig=BEDROCK_TOOLS,
                    inferenceConfig={"maxTokens": 100, "temperature": 0.1}
                )
                output_msg = follow_up["output"]["message"]
                working_messages.append(output_msg)
                continue
            except Exception as e:
                print(f"[Bedrock Text-Tool Followup Error (hop {hop + 1})]: {e}", flush=True)
                spoken = _fallback_speech_from_tool_result(last_tool_result)
                working_messages.append({"role": "assistant", "content": [{"text": spoken}]})
                messages[:] = sanitize_conversation_history(working_messages)
                return spoken

    # If MAX_TOOL_HOPS exhausted and output_msg still had pending tool calls or no text
    spoken = _extract_spoken_from_message(output_msg) or _fallback_speech_from_tool_result(last_tool_result)
    working_messages.append({"role": "assistant", "content": [{"text": spoken}]})
    messages[:] = sanitize_conversation_history(working_messages)
    return spoken
