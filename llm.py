import os
import json
import asyncio
from datetime import datetime
import boto3
from botocore.config import Config
from config import AWS_REGION, BEDROCK_MODEL_ID, BEDROCK_TOOLS, DUBLIN_TZ, KNOWN_PATIENTS
import calendar_service

print(f"[INIT LLM] Connecting to Bedrock ({AWS_REGION} | {BEDROCK_MODEL_ID})...", flush=True)
boto_config = Config(connect_timeout=4, read_timeout=12, retries={"max_attempts": 1})
bedrock_client = boto3.client("bedrock-runtime", region_name=AWS_REGION, config=boto_config)

async def execute_turn(messages: list, system_prompt: str, caller_phone: str, on_tool_log=None, on_booking=None, on_emergency=None):
    response = await asyncio.to_thread(
        bedrock_client.converse,
        modelId=BEDROCK_MODEL_ID,
        system=[{"text": system_prompt}],
        messages=messages,
        toolConfig=BEDROCK_TOOLS,
        inferenceConfig={"maxTokens": 140, "temperature": 0.1}
    )

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
                if on_tool_log:
                    await on_tool_log(f"{t_name}({json.dumps(t_in)})")

                matched = KNOWN_PATIENTS.get(caller_phone)

                if t_name == "check_calendar_slots":
                    target_date = t_in.get("date", datetime.now(DUBLIN_TZ).strftime("%Y-%m-%d"))
                    if int(target_date.split("-")[0]) < 2026:
                        target_date = datetime.now(DUBLIN_TZ).strftime("%Y-%m-%d")
                    res_data = await asyncio.to_thread(
                        calendar_service.check_calendar_slots,
                        t_in.get("clinician", "Dr. Yousuf"),
                        target_date,
                        t_in.get("time_preference", "any")
                    )
                elif t_name == "book_calendar_slot":
                    target_date = t_in.get("date", datetime.now(DUBLIN_TZ).strftime("%Y-%m-%d"))
                    if int(target_date.split("-")[0]) < 2026:
                        target_date = datetime.now(DUBLIN_TZ).strftime("%Y-%m-%d")
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

    spoken_parts = [b["text"] for b in output_msg["content"] if "text" in b]
    return " ".join(spoken_parts).strip()
