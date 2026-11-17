import asyncio
import logging
import os
import time
from collections import deque
from typing import Dict, Optional, Callable
import numpy as np
import torch
from silero_vad import load_silero_vad

from config import (
    LIVEKIT_URL,
    LIVEKIT_API_KEY,
    LIVEKIT_API_SECRET,
    build_system_prompt,
    normalize_phone,
    get_known_patient,
)
import stt
import tts
import llm

os.environ.setdefault("LIVEKIT_RTC_LOG_LEVEL", "error")
logging.getLogger("livekit").setLevel(logging.ERROR)

try:
    from livekit import rtc, api
    LIVEKIT_AVAILABLE = True
except ImportError:
    rtc = None
    api = None
    LIVEKIT_AVAILABLE = False

# Active LiveKit room sessions currently handled by Deirdre
_active_rooms: Dict[str, asyncio.Task] = {}
_poller_task: Optional[asyncio.Task] = None


def is_livekit_configured() -> bool:
    return bool(LIVEKIT_AVAILABLE and LIVEKIT_URL and LIVEKIT_API_KEY and LIVEKIT_API_SECRET)


def _extract_caller_phone(room_name: str, participant) -> str:
    """Extracts the caller's phone number from LiveKit SIP participant attributes or identity."""
    if participant is not None:
        attrs = getattr(participant, "attributes", None) or {}
        for key in ("sip.phoneNumber", "sip.fromUser", "phoneNumber", "caller_id"):
            val = attrs.get(key)
            if val:
                return normalize_phone(val)
        identity = getattr(participant, "identity", "") or ""
        if identity and not identity.startswith("deirdre"):
            cleaned_id = identity.replace("sip_", "").replace("sip:", "").lstrip("_")
            if any(ch.isdigit() for ch in cleaned_id):
                return normalize_phone(cleaned_id)

    # Fallback: parse from room name if formatted like "sip-_0872917210_xxxx"
    for prefix in ("sip-_", "sip-", "sip_", "call-", "call_"):
        if room_name.startswith(prefix):
            rest = room_name[len(prefix):].split("_")[0].split("-")[0]
            if any(ch.isdigit() for ch in rest):
                return normalize_phone(rest)

    return "+353871234567"


def _resample_to_16k(samples_f32: np.ndarray, src_rate: int) -> np.ndarray:
    """Fast linear resampler to 16kHz if AudioStream yields native 8kHz/48kHz frames."""
    if src_rate == 16000 or len(samples_f32) == 0:
        return samples_f32
    if src_rate == 48000:
        return samples_f32[::3]
    if src_rate == 8000:
        out = np.empty(len(samples_f32) * 2, dtype=np.float32)
        out[0::2] = samples_f32
        out[1:-1:2] = 0.5 * (samples_f32[:-1] + samples_f32[1:])
        out[-1] = samples_f32[-1]
        return out
    duration = len(samples_f32) / float(src_rate)
    target_len = int(round(duration * 16000))
    if target_len <= 0:
        return np.array([], dtype=np.float32)
    x_old = np.linspace(0.0, 1.0, num=len(samples_f32), endpoint=False)
    x_new = np.linspace(0.0, 1.0, num=target_len, endpoint=False)
    return np.interp(x_new, x_old, samples_f32).astype(np.float32)


async def run_sip_room_session(
    room_name: str,
    stt_thread_pool,
    tts_thread_pool,
    vad_pool: deque,
    global_vad_model,
    split_into_sentences: Callable,
    is_noise_or_empty: Callable,
    is_backchannel: Callable,
):
    """Joins a LiveKit SIP room as Deirdre and runs the Silero VAD -> Whisper -> Bedrock -> Kokoro pipeline."""
    if not is_livekit_configured():
        return

    token = (
        api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET)
        .with_identity(f"deirdre-agent-{int(time.time() * 1000) % 100000}")
        .with_name("Deirdre (AI Receptionist)")
        .with_grants(
            api.VideoGrants(
                room_join=True,
                room=room_name,
                can_publish=True,
                can_subscribe=True,
                can_publish_data=True,
                agent=True,
            )
        )
        .to_jwt()
    )

    room = rtc.Room()
    disconnect_event = asyncio.Event()

    # State variables mirroring server.py's /ws/call pipeline
    messages = []
    pcm_fifo = np.array([], dtype=np.float32)
    pre_speech_buffer = deque(maxlen=4)
    speech_buffer = []
    in_speech = False
    speech_streak = 0
    silence_frames = 0
    is_bot_speaking = False
    is_processing_turn = False
    current_turn_task: Optional[asyncio.Task] = None
    turn_lock = asyncio.Lock()
    audio_out_lock = asyncio.Lock()
    unspoken_sentences = []
    current_speaking_sentence = None
    bot_speech_start_time = 0.0
    filler_sent_this_turn = False
    greeting_started = False
    caller_phone = "+353871234567"
    system_prompt = ""

    # Acquire a dedicated Silero VAD instance from the pre-warmed pool
    vad_from_pool = False
    try:
        if vad_pool:
            vad_model = vad_pool.popleft()
            vad_from_pool = True
        else:
            vad_model = await asyncio.to_thread(load_silero_vad)
            vad_from_pool = True
    except Exception:
        vad_model = global_vad_model
    vad_model.reset_states()

    # 24kHz mono AudioSource for Kokoro TTS output (standard 1000ms queue prevents InvalidState under load)
    audio_source = rtc.AudioSource(24000, 1)

    async def stream_pcm_to_livekit(pcm_int16: np.ndarray):
        """Serializes and streams 24kHz int16 mono PCM into LiveKit AudioSource in 20ms (480-sample) frames."""
        nonlocal is_bot_speaking
        if pcm_int16 is None or len(pcm_int16) == 0:
            return
        frame_samples = 480  # 20ms at 24,000 Hz
        total_samples = len(pcm_int16)
        async with audio_out_lock:
            idx = 0
            while idx < total_samples and is_bot_speaking and not disconnect_event.is_set():
                chunk = pcm_int16[idx:idx + frame_samples]
                if len(chunk) < frame_samples:
                    chunk = np.pad(chunk, (0, frame_samples - len(chunk)), mode="constant")
                frame = rtc.AudioFrame(
                    data=chunk.tobytes(),
                    sample_rate=24000,
                    num_channels=1,
                    samples_per_channel=frame_samples,
                )
                try:
                    await audio_source.capture_frame(frame)
                except Exception:
                    # Occurs if caller hangs up or clear_queue() was invoked during barge-in
                    break
                idx += frame_samples

    async def stop_bot_audio():
        """Immediately halts Deirdre's outgoing audio on caller barge-in."""
        nonlocal is_bot_speaking
        is_bot_speaking = False
        try:
            audio_source.clear_queue()
        except Exception:
            pass

    async def resume_unspoken():
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
        print(f"[SIP Deirdre Resuming ({caller_phone})]: {' '.join(to_speak)}", flush=True)
        unspoken_sentences = list(to_speak)
        loop = asyncio.get_running_loop()
        while unspoken_sentences and is_bot_speaking and not disconnect_event.is_set():
            current_speaking_sentence = unspoken_sentences.pop(0)
            pcm_24k = await loop.run_in_executor(
                tts_thread_pool, tts.synthesize_pcm_24k, current_speaking_sentence
            )
            if len(pcm_24k) > 0 and is_bot_speaking:
                await stream_pcm_to_livekit(pcm_24k)
                current_speaking_sentence = None
        if not unspoken_sentences:
            is_bot_speaking = False

    async def speak_text(text: str):
        nonlocal is_bot_speaking, unspoken_sentences, current_speaking_sentence, bot_speech_start_time
        text = tts.strip_emojis(text)
        if not text:
            return
        print(f"[SIP Deirdre -> {caller_phone}]: {text}", flush=True)
        sentences = split_into_sentences(text)
        unspoken_sentences = list(sentences)
        is_bot_speaking = True
        bot_speech_start_time = time.time()
        loop = asyncio.get_running_loop()
        while unspoken_sentences and is_bot_speaking and not disconnect_event.is_set():
            current_speaking_sentence = unspoken_sentences.pop(0)
            pcm_24k = await loop.run_in_executor(
                tts_thread_pool, tts.synthesize_pcm_24k, current_speaking_sentence
            )
            if len(pcm_24k) > 0 and is_bot_speaking:
                await stream_pcm_to_livekit(pcm_24k)
                current_speaking_sentence = None
        if not unspoken_sentences:
            is_bot_speaking = False

    async def play_filler_b64(filler_b64: str, filler_text: str):
        nonlocal is_bot_speaking, bot_speech_start_time
        if not filler_b64:
            return
        print(f"[SIP Deirdre Filler -> {caller_phone}]: {filler_text}", flush=True)
        pcm_24k = tts.wav_base64_to_pcm_24k(filler_b64)
        if len(pcm_24k) > 0:
            is_bot_speaking = True
            bot_speech_start_time = time.time()
            await stream_pcm_to_livekit(pcm_24k)
            if not unspoken_sentences and current_speaking_sentence is None:
                is_bot_speaking = False

    async def handle_tool_start(tool_name: str, tool_input: dict = None):
        nonlocal filler_sent_this_turn
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
            # Play filler in background serialized via audio_out_lock while Google Calendar API runs
            asyncio.create_task(play_filler_b64(filler_b64, filler_text))

    async def process_user_turn(audio_np: np.ndarray):
        nonlocal is_processing_turn, current_turn_task, unspoken_sentences, current_speaking_sentence, filler_sent_this_turn
        if len(audio_np) < 4000:
            if (unspoken_sentences or current_speaking_sentence) and not is_bot_speaking:
                asyncio.create_task(resume_unspoken())
            return

        loop = asyncio.get_running_loop()
        raw_text = await loop.run_in_executor(stt_thread_pool, stt.transcribe, audio_np)
        user_text = raw_text.strip()

        if is_noise_or_empty(user_text):
            if user_text:
                print(f"[SIP Filtered Noise ({caller_phone})]: '{user_text}'", flush=True)
            if (unspoken_sentences or current_speaking_sentence) and not is_bot_speaking:
                asyncio.create_task(resume_unspoken())
            return

        if (unspoken_sentences or current_speaking_sentence) and is_backchannel(user_text):
            print(f"[SIP Backchannel ({caller_phone})]: '{user_text}' (resuming speech)", flush=True)
            if not is_bot_speaking:
                asyncio.create_task(resume_unspoken())
            return

        print(f"[SIP Patient ({caller_phone})]: {user_text}", flush=True)
        unspoken_sentences = []
        current_speaking_sentence = None

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

            try:
                reply_text = await llm.execute_turn(
                    messages,
                    system_prompt,
                    caller_phone,
                    on_tool_log=lambda msg: print(f"[SIP Tool Log ({caller_phone})]: {msg}", flush=True),
                    on_booking=lambda b: print(f"[SIP Booking Created ({caller_phone})]: {b}", flush=True),
                    on_emergency=lambda cat: print(f"[SIP Emergency Alert ({caller_phone})]: {cat}", flush=True),
                    on_tool_start=handle_tool_start,
                )
                if reply_text and not my_task.cancelled():
                    await speak_text(reply_text)
            except asyncio.CancelledError:
                print(f"[SIP Turn Cancelled ({caller_phone})]: New caller utterance.", flush=True)
            except Exception as e:
                print(f"[SIP Turn Error ({caller_phone})]: {e}", flush=True)
            finally:
                if current_turn_task is my_task:
                    current_turn_task = None
                    is_processing_turn = False
                vad_model.reset_states()

    async def start_greeting_for_participant(participant):
        nonlocal greeting_started, caller_phone, system_prompt
        if greeting_started:
            return
        greeting_started = True
        caller_phone = _extract_caller_phone(room_name, participant)
        system_prompt = build_system_prompt(caller_phone)
        matched = get_known_patient(caller_phone)
        print(
            f"\n[LIVEKIT SIP CALL ACTIVE] Room: {room_name} | Caller ID: {caller_phone} "
            f"| Matched Patient: {matched['name'] if matched else 'New Caller'}",
            flush=True,
        )
        greeting = (
            f"Hello, welcome to Star Dental and GP Clinic in Clonsilla. You are speaking with Deirdre, the clinic's automated AI receptionist. Am I speaking with {matched['name']}?"
            if matched else
            "Hello, welcome to Star Dental and GP Clinic in Clonsilla. You are speaking with Deirdre, the clinic's automated AI receptionist. How can I help you today?"
        )
        messages.append({"role": "user", "content": [{"text": "Hello, I am calling the clinic."}]})
        messages.append({"role": "assistant", "content": [{"text": greeting}]})
        await asyncio.sleep(0.25)  # Brief settle time after SIP RTP bridge opens
        await speak_text(greeting)

    async def consume_audio_track(track: rtc.Track, participant):
        """Reads 16kHz PCM from the SIP caller's LiveKit audio track and feeds Silero VAD."""
        nonlocal pcm_fifo, in_speech, speech_streak, silence_frames, speech_buffer
        await start_greeting_for_participant(participant)

        try:
            audio_stream = rtc.AudioStream(track, sample_rate=16000, num_channels=1)
        except TypeError:
            audio_stream = rtc.AudioStream(track)

        async for event in audio_stream:
            if disconnect_event.is_set():
                break
            frame = event.frame if hasattr(event, "frame") else event
            pcm_int16 = np.frombuffer(frame.data, dtype=np.int16)
            if frame.num_channels > 1:
                pcm_int16 = pcm_int16[::frame.num_channels]
            floats = pcm_int16.astype(np.float32) / 32768.0
            if frame.sample_rate != 16000:
                floats = _resample_to_16k(floats, frame.sample_rate)

            pcm_fifo = np.concatenate([pcm_fifo, floats])

            while len(pcm_fifo) >= 512:
                window = pcm_fifo[:512]
                pcm_fifo = pcm_fifo[512:]

                rms = float(np.sqrt(np.mean(window ** 2)))
                prob = vad_model(torch.from_numpy(window), 16000).item()

                now = time.time()
                in_grace_period = is_bot_speaking and (now - bot_speech_start_time < 0.40)

                if is_bot_speaking:
                    threshold = 0.72
                    required_streak = 7
                    min_rms = 0.018
                else:
                    threshold = 0.52
                    required_streak = 3
                    min_rms = 0.008

                pre_speech_buffer.append(window)

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
                            speech_buffer = list(pre_speech_buffer)

                        if is_bot_speaking:
                            await stop_bot_audio()

                        speech_buffer.append(window)
                    else:
                        if in_speech:
                            speech_buffer.append(window)

                    if in_speech:
                        silence_frames = 0
                else:
                    speech_streak = 0
                    if in_speech:
                        speech_buffer.append(window)
                        silence_frames += 1

                        REQUIRED_SILENCE_FRAMES = 38
                        if silence_frames >= REQUIRED_SILENCE_FRAMES:
                            in_speech = False
                            silence_frames = 0

                            trim_frames = max(0, REQUIRED_SILENCE_FRAMES - 6)
                            full_turn = np.concatenate(speech_buffer)
                            if trim_frames > 0 and len(full_turn) > trim_frames * 512:
                                full_turn = full_turn[:-trim_frames * 512]

                            speech_buffer = []
                            asyncio.create_task(process_user_turn(full_turn))

    @room.on("track_subscribed")
    def on_track_subscribed(track: rtc.Track, publication, participant):
        if track.kind == rtc.TrackKind.KIND_AUDIO and not participant.identity.startswith("deirdre"):
            asyncio.create_task(consume_audio_track(track, participant))

    @room.on("participant_disconnected")
    def on_participant_disconnected(participant):
        if not participant.identity.startswith("deirdre"):
            print(f"[LIVEKIT SIP DISCONNECTED] Caller {caller_phone} hung up (room: {room_name}).", flush=True)
            disconnect_event.set()

    @room.on("disconnected")
    def on_disconnected(*_):
        disconnect_event.set()

    try:
        await room.connect(LIVEKIT_URL, token)
        track = rtc.LocalAudioTrack.create_audio_track("deirdre-voice", audio_source)
        options = rtc.TrackPublishOptions(source=rtc.TrackSource.SOURCE_MICROPHONE)
        await room.local_participant.publish_track(track, options)

        for participant in room.remote_participants.values():
            if not participant.identity.startswith("deirdre"):
                for pub in participant.track_publications.values():
                    if pub.track and pub.track.kind == rtc.TrackKind.KIND_AUDIO:
                        asyncio.create_task(consume_audio_track(pub.track, participant))
                if not greeting_started:
                    asyncio.create_task(start_greeting_for_participant(participant))

        await disconnect_event.wait()
    except Exception as e:
        print(f"[LIVEKIT ROOM ERROR ({room_name})]: {e}", flush=True)
    finally:
        is_bot_speaking = False
        if current_turn_task and not current_turn_task.done():
            current_turn_task.cancel()
        try:
            await room.disconnect()
        except Exception:
            pass
        if vad_from_pool and len(vad_pool) < 120:
            try:
                vad_model.reset_states()
                vad_pool.append(vad_model)
            except Exception:
                pass
        _active_rooms.pop(room_name, None)


def ensure_room_session(
    room_name: str,
    stt_thread_pool,
    tts_thread_pool,
    vad_pool: deque,
    global_vad_model,
    split_into_sentences: Callable,
    is_noise_or_empty: Callable,
    is_backchannel: Callable,
) -> bool:
    """Spawns a Deirdre session for `room_name` if not already active."""
    if not room_name or not is_livekit_configured():
        return False
    existing = _active_rooms.get(room_name)
    if existing and not existing.done():
        return False

    task = asyncio.create_task(
        run_sip_room_session(
            room_name=room_name,
            stt_thread_pool=stt_thread_pool,
            tts_thread_pool=tts_thread_pool,
            vad_pool=vad_pool,
            global_vad_model=global_vad_model,
            split_into_sentences=split_into_sentences,
            is_noise_or_empty=is_noise_or_empty,
            is_backchannel=is_backchannel,
        )
    )
    _active_rooms[room_name] = task
    return True


async def poll_livekit_sip_rooms(
    stt_thread_pool,
    tts_thread_pool,
    vad_pool: deque,
    global_vad_model,
    split_into_sentences: Callable,
    is_noise_or_empty: Callable,
    is_backchannel: Callable,
):
    """Polls local LiveKit server every 500ms to auto-join any new SIP call room (`sip-*` or `call-*`)."""
    if not is_livekit_configured():
        print("[LIVEKIT] LIVEKIT_API_KEY / SECRET not set in .env; SIP bridge standing by.", flush=True)
        return

    print(f"[LIVEKIT SIP BRIDGE] Watching LiveKit Server at {LIVEKIT_URL} for inbound VoIPLine.ie calls...", flush=True)
    lk_http_url = LIVEKIT_URL.replace("wss://", "https://").replace("ws://", "http://")
    lkapi = api.LiveKitAPI(url=lk_http_url, api_key=LIVEKIT_API_KEY, api_secret=LIVEKIT_API_SECRET)

    try:
        while True:
            try:
                resp = await lkapi.room.list_rooms(api.ListRoomsRequest())
                for rm in resp.rooms:
                    if rm.name.startswith(("sip-", "sip_", "call-", "clinic-")) and rm.num_participants > 0:
                        ensure_room_session(
                            room_name=rm.name,
                            stt_thread_pool=stt_thread_pool,
                            tts_thread_pool=tts_thread_pool,
                            vad_pool=vad_pool,
                            global_vad_model=global_vad_model,
                            split_into_sentences=split_into_sentences,
                            is_noise_or_empty=is_noise_or_empty,
                            is_backchannel=is_backchannel,
                        )
            except Exception:
                pass
            await asyncio.sleep(0.5)
    finally:
        try:
            await lkapi.aclose()
        except Exception:
            pass
