import json
import re
import time
import asyncio
from collections import deque
import numpy as np
import torch
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketDisconnect as StarletteWebSocketDisconnect
try:
    from starlette.websockets import WebSocketDisconnected
except ImportError:
    WebSocketDisconnected = StarletteWebSocketDisconnect
from fastapi.responses import FileResponse
from silero_vad import load_silero_vad

from config import (
    build_system_prompt,
    KNOWN_PATIENTS,
    GOOGLE_CALENDAR_ID,
    BEDROCK_MODEL_ID,
    normalize_phone,
    get_known_patient
)
import calendar_service
import stt
import tts
import llm
from concurrent.futures import ThreadPoolExecutor

app = FastAPI()

# High-concurrency thread pools:
# - thread_pool (128 workers): handles network I/O (AWS Bedrock & Google Calendar API)
# - stt_thread_pool (16 workers): dedicated exclusively to Whisper STT so TTS or network I/O never blocks transcription
# - tts_thread_pool (16 workers): dedicated exclusively to Kokoro TTS synthesis
thread_pool = ThreadPoolExecutor(max_workers=128, thread_name_prefix="io_worker")
stt_thread_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="stt_worker")
tts_thread_pool = ThreadPoolExecutor(max_workers=16, thread_name_prefix="tts_worker")

@app.on_event("startup")
async def startup_event():
    try:
        loop = asyncio.get_running_loop()
        loop.set_default_executor(thread_pool)
        print("[INIT EXECUTOR] Set default I/O pool (128), dedicated STT pool (16), and dedicated TTS pool (16).", flush=True)
    except Exception as e:
        print(f"[WARN] Failed to set ThreadPoolExecutor: {e}", flush=True)

print("[INIT VAD] Loading Silero VAD pool (CPU)...", flush=True)
global_vad_model = load_silero_vad()
_vad_pool = deque()
for _ in range(100):
    try:
        _vad_pool.append(load_silero_vad())
    except Exception:
        break

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
    raw_phone = websocket.query_params.get("caller_id", "+353871234567")
    caller_phone = normalize_phone(raw_phone)
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
    turn_lock = asyncio.Lock()
    unspoken_sentences = []
    current_speaking_sentence = None
    bot_speech_start_time = 0.0

    # Dedicated VAD model instance per connection from pre-warmed pool (avoids blocking event loop on disk JIT load)
    vad_from_pool = False
    try:
        if _vad_pool:
            vad_model = _vad_pool.popleft()
            vad_from_pool = True
        else:
            vad_model = await asyncio.to_thread(load_silero_vad)
            vad_from_pool = True
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
        loop = asyncio.get_running_loop()
        while unspoken_sentences and is_bot_speaking:
            current_speaking_sentence = unspoken_sentences.pop(0)
            b64_wav = await loop.run_in_executor(tts_thread_pool, tts.synthesize_wav_base64, current_speaking_sentence)
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
        loop = asyncio.get_running_loop()
        while unspoken_sentences and is_bot_speaking:
            current_speaking_sentence = unspoken_sentences.pop(0)
            b64_wav = await loop.run_in_executor(tts_thread_pool, tts.synthesize_wav_base64, current_speaking_sentence)
            if b64_wav and is_bot_speaking:
                await send_json({"type": "audio", "b64": b64_wav})

    # Greeting (with EU AI Act Art. 50 transparency disclosure)
    matched = get_known_patient(caller_phone)
    greeting = (
        f"Hello, welcome to Star Dental and GP Clinic in Clonsilla. You are speaking with Deirdre, the clinic's automated AI receptionist. Am I speaking with {matched['name']}?"
        if matched else
        "Hello, welcome to Star Dental and GP Clinic in Clonsilla. You are speaking with Deirdre, the clinic's automated AI receptionist. How can I help you today?"
    )
    messages.append({"role": "user", "content": [{"text": "Hello, I am calling the clinic."}]})
    messages.append({"role": "assistant", "content": [{"text": greeting}]})
    asyncio.create_task(speak_text(greeting))

    filler_sent_this_turn = False

    async def handle_tool_start(tool_name: str, tool_input: dict = None):
        nonlocal filler_sent_this_turn
        await send_json({"type": "tool_start", "tool": tool_name, "input": tool_input or {}})
        # If filler audio was already played at the start of this turn, do not repeat
        if filler_sent_this_turn:
            return

        filler_b64 = None
        filler_text = ""
        if tool_name == "check_calendar_slots":
            filler_b64, filler_text = tts.get_check_filler()
        elif tool_name == "book_calendar_slot":
            filler_b64, filler_text = tts.get_book_filler()

        if filler_b64:
            filler_sent_this_turn = True
            if filler_text:
                await send_json({"type": "transcript", "role": "Deirdre", "text": filler_text})
            await send_json({"type": "audio", "b64": filler_b64})

    async def handle_tool_result(tool_name: str, tool_input: dict, tool_result: dict):
        await send_json({
            "type": "tool_result",
            "tool": tool_name,
            "input": tool_input or {},
            "result": tool_result or {}
        })

    async def process_user_turn(audio_np: np.ndarray):
        nonlocal is_processing_turn, current_turn_task, unspoken_sentences, current_speaking_sentence, filler_sent_this_turn
        # Minimum audio frame check: ~250ms (4000 samples at 16kHz) to filter mic pops
        if len(audio_np) < 4000:
            if (unspoken_sentences or current_speaking_sentence) and not is_bot_speaking:
                asyncio.create_task(resume_unspoken())
            return

        loop = asyncio.get_running_loop()
        raw_text = await loop.run_in_executor(stt_thread_pool, stt.transcribe, audio_np)
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

        # Cancel any previous in-flight turn task and await its cleanup before mutating shared state
        my_task = asyncio.current_task()
        if current_turn_task and current_turn_task is not my_task and not current_turn_task.done():
            current_turn_task.cancel()
            try:
                await current_turn_task
            except (asyncio.CancelledError, Exception):
                pass
        current_turn_task = my_task

        async with turn_lock:
            messages.append({"role": "user", "content": [{"text": user_text}]})
            is_processing_turn = True
            filler_sent_this_turn = False

            # Fast Conversational Filler:
            # Immediately acknowledge scheduling queries within ~200ms so TTFA stays sub-second and eliminates dead air
            lower_user = user_text.lower()
            scheduling_keywords = (
                "book", "appointment", "slot", "available", "see ", "dr.", "doctor",
                "nurse", "dentist", "check", "monday", "tuesday", "wednesday",
                "thursday", "friday", "morning", "afternoon", "tomorrow", "today", "confirm"
            )
            if any(w in lower_user for w in scheduling_keywords):
                filler_b64, filler_text = tts.get_check_filler()
                if filler_b64:
                    filler_sent_this_turn = True
                    await send_json({"type": "transcript", "role": "Deirdre", "text": filler_text})
                    await send_json({"type": "audio", "b64": filler_b64})

            try:
                reply_text = await llm.execute_turn(
                    messages,
                    system_prompt,
                    caller_phone,
                    on_tool_log=lambda msg: send_json({"type": "tool_log", "text": msg}),
                    on_booking=lambda b: send_json({"type": "booking_created", "booking": b}),
                    on_emergency=lambda cat: send_json({"type": "emergency_alert", "text": cat}),
                    on_tool_start=handle_tool_start,
                    on_tool_result=handle_tool_result
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
            if packet.get("type") == "websocket.disconnect":
                break
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

                    # Determine speech frames with Hysteresis:
                    # 1. Initiation: To START speech, require high confidence (prob > threshold, rms > min_rms)
                    # 2. Continuation (Hysteresis): Once speech has begun, maintain speech even during softer
                    #    trailing vowels, hesitations, or thinking sounds (prob > 0.35, rms > 0.005).
                    if not in_speech:
                        is_speech_frame = (prob > threshold) and (rms > min_rms) and (not in_grace_period)
                    else:
                        is_speech_frame = (prob > 0.35) and (rms > 0.005)

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

                        # While continuing to speak or vocalize, keep silence counter reset
                        if in_speech:
                            silence_frames = 0
                    else:
                        speech_streak = 0
                        if in_speech:
                            speech_buffer.append(window)
                            silence_frames += 1

                            # Generous conversational pause threshold:
                            # 38 frames = ~1.22 seconds of confirmed silence before concluding the turn.
                            # Gives callers plenty of time to pause, hesitate, and speak freely without interruption.
                            REQUIRED_SILENCE_FRAMES = 38

                            if silence_frames >= REQUIRED_SILENCE_FRAMES:
                                in_speech = False
                                silence_frames = 0
                                await send_json({"type": "vad_state", "speaking": False})

                                # Trim excess trailing silence (keep ~200ms natural tail padding)
                                trim_frames = max(0, REQUIRED_SILENCE_FRAMES - 6)
                                full_turn = np.concatenate(speech_buffer)
                                if trim_frames > 0 and len(full_turn) > trim_frames * 512:
                                    full_turn = full_turn[:-trim_frames * 512]

                                speech_buffer = []
                                asyncio.create_task(process_user_turn(full_turn))

    except (WebSocketDisconnect, WebSocketDisconnected):
        print("[WS DISCONNECTED] Caller hung up.", flush=True)
    finally:
        is_bot_speaking = False
        if current_turn_task and not current_turn_task.done():
            current_turn_task.cancel()
        if vad_from_pool and len(_vad_pool) < 120:
            try:
                vad_model.reset_states()
                _vad_pool.append(vad_model)
            except Exception:
                pass
