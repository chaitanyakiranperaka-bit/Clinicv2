import json
import asyncio
import numpy as np
import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from silero_vad import load_silero_vad

from config import build_system_prompt, KNOWN_PATIENTS, GOOGLE_CALENDAR_ID, BEDROCK_MODEL_ID
import calendar_service
import stt
import tts
import llm

app = FastAPI()
print("[INIT VAD] Loading Silero VAD (CPU)...", flush=True)
vad_model = load_silero_vad()

@app.get("/")
async def get_index():
    return FileResponse("static/index.html")

@app.get("/status")
async def get_status():
    gcal_active = bool(calendar_service.get_gcal_service())
    return {
        "calendar_badge": f"🟢 Live GCal ({GOOGLE_CALENDAR_ID})" if gcal_active else "🟡 Local Staging Queue",
        "model_id": BEDROCK_MODEL_ID
    }

@app.websocket("/ws/call")
async def call_websocket(websocket: WebSocket):
    await websocket.accept()
    caller_phone = websocket.query_params.get("caller_id", "+353871234567")
    system_prompt = build_system_prompt(caller_phone)
    print(f"\n[WS CONNECTED] Inbound call from: {caller_phone}", flush=True)

    messages = []
    pcm_fifo = np.array([], dtype=np.float32)
    speech_buffer = []
    in_speech = False
    silence_frames = 0
    is_bot_speaking = False
    is_processing_turn = False
    vad_model.reset_states()

    async def send_json(payload: dict):
        try:
            await websocket.send_text(json.dumps(payload))
        except Exception:
            pass

    async def speak_text(text: str):
        nonlocal is_bot_speaking
        if not text:
            return
        print(f"[Deirdre]: {text}", flush=True)
        await send_json({"type": "transcript", "role": "Deirdre", "text": text})
        is_bot_speaking = True
        sentences = [s.strip() for s in text.replace("!", ".").replace("?", ".").split(".") if s.strip()]
        for sentence in sentences:
            b64_wav = await asyncio.to_thread(tts.synthesize_wav_base64, sentence)
            if b64_wav:
                await send_json({"type": "audio", "b64": b64_wav})

    # Greeting
    matched = KNOWN_PATIENTS.get(caller_phone)
    greeting = (
        f"Hello, welcome to Star Dental and GP Clinic in Clonsilla. You are speaking with Deirdre. Am I speaking with {matched['name']}?"
        if matched else
        "Hello, welcome to Star Dental and GP Clinic in Clonsilla. You are speaking with Deirdre. How can I help you today?"
    )
    messages.append({"role": "user", "content": [{"text": "Hello, I am calling the clinic."}]})
    messages.append({"role": "assistant", "content": [{"text": greeting}]})
    asyncio.create_task(speak_text(greeting))

    async def process_user_turn(audio_np: np.ndarray):
        nonlocal is_processing_turn
        is_processing_turn = True
        try:
            user_text = await asyncio.to_thread(stt.transcribe, audio_np)
            if not user_text or len(user_text) < 2:
                return

            print(f"[Patient]: {user_text}", flush=True)
            await send_json({"type": "transcript", "role": "Patient", "text": user_text})
            messages.append({"role": "user", "content": [{"text": user_text}]})

            if tts.FILLER_AUDIO_B64:
                await send_json({"type": "audio", "b64": tts.FILLER_AUDIO_B64})

            reply_text = await llm.execute_turn(
                messages,
                system_prompt,
                caller_phone,
                on_tool_log=lambda msg: send_json({"type": "tool_log", "text": msg}),
                on_booking=lambda b: send_json({"type": "booking_created", "booking": b}),
                on_emergency=lambda cat: send_json({"type": "emergency_alert", "text": cat})
            )

            if reply_text:
                await speak_text(reply_text)

        except Exception as e:
            print(f"[Turn Processing Error]: {e}", flush=True)
        finally:
            is_processing_turn = False
            vad_model.reset_states()

    try:
        while True:
            packet = await websocket.receive()
            if "text" in packet:
                data = json.loads(packet["text"])
                if data.get("action") == "hangup":
                    break
                elif data.get("action") == "playback_finished":
                    is_bot_speaking = False

            elif "bytes" in packet:
                floats = np.frombuffer(packet["bytes"], dtype=np.float32)
                pcm_fifo = np.concatenate([pcm_fifo, floats])

                while len(pcm_fifo) >= 512:
                    window = pcm_fifo[:512]
                    pcm_fifo = pcm_fifo[512:]

                    prob = vad_model(torch.from_numpy(window), 16000).item()
                    if prob > 0.40:
                        if not in_speech and not is_processing_turn:
                            in_speech = True
                            silence_frames = 0
                            speech_buffer = []
                            await send_json({"type": "vad_state", "speaking": True})

                        if is_bot_speaking:
                            is_bot_speaking = False
                            await send_json({"type": "clear_audio"})

                        if in_speech:
                            silence_frames = 0
                            speech_buffer.append(window)
                    else:
                        if in_speech:
                            speech_buffer.append(window)
                            silence_frames += 1
                            if silence_frames >= 16:  # ~512ms silence
                                in_speech = False
                                silence_frames = 0
                                await send_json({"type": "vad_state", "speaking": False})
                                full_turn = np.concatenate(speech_buffer)
                                speech_buffer = []
                                asyncio.create_task(process_user_turn(full_turn))

    except WebSocketDisconnect:
        print("[WS DISCONNECTED] Caller hung up.", flush=True)
