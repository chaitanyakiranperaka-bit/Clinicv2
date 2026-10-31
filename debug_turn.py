import boto3
import json

client = boto3.client("bedrock-runtime", region_name="eu-west-1")

system_prompt = (
    "You are Deirdre at Star Dental & GP Clinic in Dublin. "
    "MANDATORY: When the patient confirms a booking, you must trigger the `book_calendar_slot` tool. "
    "Never write `book_calendar_slot` in plain text. Execute the tool."
)

tools = [
    {
        "toolSpec": {
            "name": "book_calendar_slot",
            "description": "Book a 15-minute slot.",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "clinician": {"type": "string"},
                        "date": {"type": "string"},
                        "slot_time": {"type": "string"},
                        "patient_name": {"type": "string"},
                        "patient_dob": {"type": "string"},
                        "appointment_category": {"type": "string"}
                    },
                    "required": ["clinician", "date", "slot_time", "patient_name", "patient_dob", "appointment_category"]
                }
            }
        }
    }
]

messages = [
    {"role": "user", "content": [{"text": "Can you book me an appointment with GP?"}]},
    {"role": "assistant", "content": [{"text": "We have Friday at 15:00 available with Dr. Yousuf. Would you like me to book that for you?"}]},
    {"role": "user", "content": [{"text": "Yes, please."}]}
]

resp = client.converse(
    modelId="qwen.qwen3-coder-30b-a3b-v1:0",
    system=[{"text": system_prompt}],
    messages=messages,
    toolConfig={"tools": tools},
    inferenceConfig={"maxTokens": 100, "temperature": 0.1}
)

msg = resp["output"]["message"]
print("\n=== Gemma 3 Response ===")
print("Stop Reason:", resp.get("stopReason"))
print("Content Blocks:", json.dumps(msg.get("content", []), indent=2))
