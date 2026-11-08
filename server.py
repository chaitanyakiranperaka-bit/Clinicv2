import json
import re
import time
import asyncio
from collections import deque
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
global_vad_model = load_silero_vad()

BACKCHANNELS = {
    "uh-huh", "uh huh", "mhm", "mm-hmm", "mm", "right", "ah", "got it"
}

NOISE_WORDS = {
    "", ".", "um", "uh", "cough", "throat", "clears throat", "blank_audio"
}

def clean_whisper_text(text: str) -> str:
    """Removes whisper artifacts like [music], (cough) and punctuation."""
    cleaned = re.sub(r'\[.*?\]|\(.*?\)', '', text).strip()
    cleaned = re.sub(r'[^\w\s-]', '', cleaned).strip().lower()
    return cleaned

def is_backchannel(text: str) -> bool:
    """Detects passive conversational affirmations (uh-huh, mhm) that should not disrupt bot flow."""
    c = clean_whisper_text(text)
    return c in BACKCHANNELS

def is_noise_or_empty(text: str) -> bool:
    """Detects background audio artifacts, coughs, and unvoiced breaths."""
    c = clean_whisper_text(text)
    return len(c) < 2 or c in NOISE_WORDS

def split_into_sentences(text: str) -> list:
    """Splits text into sentences while protecting titles (Dr., Mr., etc.) and preserving ?, ! punctuation."""
    if not text:
        return []
    abbrevs = {
        "Dr.": "Dr<DOT>",
        "dr.": "dr<DOT>",
        "Mr.": "Mr<DOT>",
        "Mrs.": "Mrs<DOT>",
        "Ms.": "Ms<DOT>",
        "Prof.": "Prof<DOT>",
        "St.": "St<DOT>",
        "e.g.": "eg<DOT>",
        "i.e.": "ie<DOT>"
    }
    cleaned = text.strip()
    for abbr, repl in abbrevs.items():
        cleaned = cleaned.replace(abbr, repl)

    raw_sentences = re.split(r'([.!?]+(?:\s+|$))', cleaned)
    tokens = []
    current = ""
    for token in raw_sentences:
        current += token
        if re.search(r'[.!?]+(?:\s+|$)', token):
            sent = current.strip()
            for abbr, repl in abbrevs.items():
                sent = sent.replace(repl, abbr)
            if sent:
                tokens.append(sent)
            current = ""
    if current.strip():
        sent = current.strip()
        for abbr, repl in abbrevs.items():
            sent = sent.replace(repl, abbr)
        tokens.append(sent)

    # Merge very short introductory fragments (e.g. "Yes, Sean.", "Of course.") into the next sentence
    merged = []
    i = 0
    while i < len(tokens):
        s = tokens[i].strip()
        if len(s.split()) <= 3 and i + 1 < len(tokens):
            merged.append(f"{s} {tokens[i+1].strip()}")
            i += 2
        else:
            merged.append(s)
            i += 1

    return merged if merged else [text.strip()]

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
    pre_speech_buffer = deque(maxlen=4)
    speech_buffer = []
    in_speech = False
    speech_streak = 0
    silence_frames = 0
    is_bot_speaking = False
    is_processing_turn = False
    current_turn_task = None
    unspoken_sentences = []
    current_speaking_sentence = None
    bot_speech_start_time = 0.0

    # Dedicated VAD model instance per connection for state isolation
    try:
        vad_model = load_silero_vad()
    except Exception:
        vad_model = global_vad_model
    vad_model.reset_states()

    async def send_json(payload: dict):
        try:
            await websocket.send_text(json.dumps(payload))
        except Exception:
            pass

    async def resume_unspoken():
        """Resumes speaking the interrupted sentence or queued sentences if interruption was just noise or backchannel."""
        nonlocal is_bot_speaking, unspoken_sentences, current_speaking_sentence, bot_speech_start_time
        to_speak = []
        if current_speaking_sentence:
            to_speak.append(current_speaking_sentence)
            current_speaking_sentence = None
        to_speak.extend(unspoken_sentences)
        unspoken_sentences = []

        if not to_speak or is_bot_speaking:
            return

        is_bot_speaking = True
        bot_speech_start_time = time.time()
        print(f"[Deirdre Resuming]: {' '.join(to_speak)}", flush=True)
        unspoken_sentences = list(to_speak)
        while unspoken_sentences and is_bot_speaking:
            current_speaking_sentence = unspoken_sentences.pop(0)
            b64_wav = await asyncio.to_thread(tts.synthesize_wav_base64, current_speaking_sentence)
            if b64_wav and is_bot_speaking:
                await send_json({"type": "audio", "b64": b64_wav})

    async def speak_text(text: str):
        nonlocal is_bot_speaking, unspoken_sentences, current_speaking_sentence, bot_speech_start_time
        text = tts.strip_emojis(text)
        if not text:
            return
        print(f"[Deirdre]: {text}", flush=True)
        await send_json({"type": "transcript", "role": "Deirdre", "text": text})
        sentences = split_into_sentences(text)
        unspoken_sentences = list(sentences)
        is_bot_speaking = True
        bot_speech_start_time = time.time()
        while unspoken_sentences and is_bot_speaking:
            current_speaking_sentence = unspoken_sentences.pop(0)
            b64_wav = await asyncio.to_thread(tts.synthesize_wav_base64, current_speaking_sentence)
            if b64_wav and is_bot_speaking:
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

    async def handle_tool_start(tool_name: str):
        # Only play filler audio during tool calls (not on every simple conversational turn)
        if tool_name in ("check_calendar_slots", "book_calendar_slot") and tts.FILLER_AUDIO_B64:
            await send_json({"type": "audio", "b64": tts.FILLER_AUDIO_B64})

    async def process_user_turn(audio_np: np.ndarray):
        nonlocal is_processing_turn, current_turn_task, unspoken_sentences, current_speaking_sentence
        # Minimum audio frame check: ~250ms (4000 samples at 16kHz) to filter mic pops
        if len(audio_np) < 4000:
            if (unspoken_sentences or current_speaking_sentence) and not is_bot_speaking:
                asyncio.create_task(resume_unspoken())
            return

        raw_text = await asyncio.to_thread(stt.transcribe, audio_np)
        user_text = raw_text.strip()

        # 1. Check if unvoiced noise, cough, breath, or acoustic artifact
        if is_noise_or_empty(user_text):
            if user_text:
                print(f"[Filtered Noise/Artifact]: '{user_text}'", flush=True)
            if (unspoken_sentences or current_speaking_sentence) and not is_bot_speaking:
                asyncio.create_task(resume_unspoken())
            return

        # 2. Check if passive conversational backchannel ("uh-huh", "mhm")
        # ONLY treat as backchannel if the bot was mid-speech and still has unspoken sentences to finish!
        if (unspoken_sentences or current_speaking_sentence) and is_backchannel(user_text):
            print(f"[Patient Backchannel]: '{user_text}' (resuming bot speech)", flush=True)
            if not is_bot_speaking:
                asyncio.create_task(resume_unspoken())
            return

        # 3. Genuine caller speech — user is giving an instruction or answering
        print(f"[Patient]: {user_text}", flush=True)
        await send_json({"type": "transcript", "role": "Patient", "text": user_text})

        # Discard previous bot sentences since caller has responded or changed topic
        unspoken_sentences = []
        current_speaking_sentence = None

        # Cancel any previous task ONLY if it is a DIFFERENT task than this one
        my_task = asyncio.current_task()
        if current_turn_task and current_turn_task is not my_task and not current_turn_task.done():
            current_turn_task.cancel()
        current_turn_task = my_task

        messages.append({"role": "user", "content": [{"text": user_text}]})
        is_processing_turn = True

        try:
            reply_text = await llm.execute_turn(
                messages,
                system_prompt,
                caller_phone,
                on_tool_log=lambda msg: send_json({"type": "tool_log", "text": msg}),
                on_booking=lambda b: send_json({"type": "booking_created", "booking": b}),
                on_emergency=lambda cat: send_json({"type": "emergency_alert", "text": cat}),
                on_tool_start=handle_tool_start
            )

            if reply_text and not my_task.cancelled():
                await speak_text(reply_text)

        except asyncio.CancelledError:
            print("[Turn Cancelled]: New caller utterance initiated.", flush=True)
        except Exception as e:
            print(f"[Turn Processing Error]: {e}", flush=True)
        finally:
            if current_turn_task is my_task:
                current_turn_task = None
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
                    current_speaking_sentence = None
                    if not unspoken_sentences:
                        is_bot_speaking = False

            elif "bytes" in packet:
                floats = np.frombuffer(packet["bytes"], dtype=np.float32)
                pcm_fifo = np.concatenate([pcm_fifo, floats])

                while len(pcm_fifo) >= 512:
                    window = pcm_fifo[:512]
                    pcm_fifo = pcm_fifo[512:]

                    # Calculate Root-Mean-Square (RMS) audio energy
                    rms = float(np.sqrt(np.mean(window ** 2)))
                    prob = vad_model(torch.from_numpy(window), 16000).item()

                    # Dual-Threshold VAD Guard:
                    # When bot is speaking: protect against acoustic echo bleed, breathing, and minor rustle.
                    now = time.time()
                    in_grace_period = is_bot_speaking and (now - bot_speech_start_time < 0.40)

                    if is_bot_speaking:
                        threshold = 0.72       # Stricter probability for barge-in
                        required_streak = 7    # ~224ms of sustained speech required to interrupt
                        min_rms = 0.018        # Must have actual vocal volume
                    else:
                        threshold = 0.52       # Standard speech threshold when caller is expected to speak
                        required_streak = 3    # ~96ms
                        min_rms = 0.008        # Filters low-level mic hum

                    pre_speech_buffer.append(window)
                    is_speech_frame = (prob > threshold) and (rms > min_rms) and (not in_grace_period)

                    if is_speech_frame:
                        speech_streak += 1
                        if speech_streak >= required_streak:
                            if not in_speech:
                                in_speech = True
                                silence_frames = 0
                                # Include pre-speech head padding (~128ms) so first consonants are never clipped
                                speech_buffer = list(pre_speech_buffer)
                                await send_json({"type": "vad_state", "speaking": True})

                            # Confirmed genuine caller barge-in: stop audio playback
                            if is_bot_speaking:
                                is_bot_speaking = False
                                await send_json({"type": "clear_audio"})

                            speech_buffer.append(window)
                        else:
                            if in_speech:
                                speech_buffer.append(window)
                    else:
                        speech_streak = 0
                        if in_speech:
                            speech_buffer.append(window)
                            silence_frames += 1

                            # Conversational pause threshold:
                            # If caller spoke only a short phrase (< 1.5s total audio), allow ~1.05s pause (33 frames)
                            # to think/hesitate without getting cut off.
                            # For longer turns, allow ~864ms (27 frames).
                            total_spoken_frames = len(speech_buffer)
                            required_silence = 33 if total_spoken_frames < 45 else 27

                            if silence_frames >= required_silence:
                                in_speech = False
                                silence_frames = 0
                                await send_json({"type": "vad_state", "speaking": False})

                                # Trim excess trailing silence (keep ~190ms natural tail padding)
                                trim_frames = max(0, required_silence - 6)
                                full_turn = np.concatenate(speech_buffer)
                                if trim_frames > 0 and len(full_turn) > trim_frames * 512:
                                    full_turn = full_turn[:-trim_frames * 512]

                                speech_buffer = []
                                current_turn_task = asyncio.create_task(process_user_turn(full_turn))

    except WebSocketDisconnect:
        print("[WS DISCONNECTED] Caller hung up.", flush=True)
    finally:
        if current_turn_task and not current_turn_task.done():
            current_turn_task.cancel()
