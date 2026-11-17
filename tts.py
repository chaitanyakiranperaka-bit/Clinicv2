import io
import re
import base64
import threading
from collections import OrderedDict
import numpy as np
import soundfile as sf
from kokoro import KPipeline

print("[INIT TTS] Loading Kokoro-82M (bf_isabella) with in-memory LRU audio cache...", flush=True)
tts_pipeline = KPipeline(lang_code="b")
tts_lock = threading.Lock()

_TTS_CACHE_MAX = 512
_tts_cache = OrderedDict()
_tts_cache_lock = threading.Lock()

EMOJI_PATTERN = re.compile(
    "["
    "\U0001F600-\U0001F64F"  # emoticons
    "\U0001F300-\U0001F5FF"  # symbols & pictographs
    "\U0001F680-\U0001F6FF"  # transport & map symbols
    "\U0001F1E0-\U0001F1FF"  # flags
    "\U0001F900-\U0001F9FF"  # supplemental symbols and pictographs
    "\U0001FA70-\U0001FAFF"  # symbols and pictographs extended-a
    "\U00002702-\U000027B0"  # dingbats
    "\U000024C2-\U0001F251"
    "\U00002600-\U000026FF"  # misc symbols
    "\U00002300-\U000023FF"  # misc technical
    "\u200d"                 # zero width joiner
    "\ufe0f"                 # variation selector
    "]+",
    flags=re.UNICODE
)

def strip_emojis(text: str) -> str:
    """Removes all emojis and symbols that Kokoro reads aloud as text descriptions."""
    if not text:
        return ""
    cleaned = EMOJI_PATTERN.sub("", text)
    cleaned = re.sub(r"\s+([.,!?:;])", r"\1", cleaned)
    return re.sub(r"\s+", " ", cleaned).strip()

def verbalize_spoken_times(text: str) -> str:
    """Replaces raw 24h clock times like '09:00', '13:15' with natural spoken times '9 am', '1:15 pm'."""
    def _repl(match):
        h = int(match.group(1))
        mins = int(match.group(2))
        period = "am" if h < 12 else "pm"
        h12 = h if 1 <= h <= 12 else (h - 12 if h > 12 else 12)
        if mins == 0:
            return f"{h12} {period}"
        return f"{h12}:{mins:02d} {period}"

    pattern = r"\b([01]?\d|2[0-3]):([0-5]\d)(?!\s*(?:am|pm))\b"
    return re.sub(pattern, _repl, text, flags=re.IGNORECASE)

def synthesize_wav_base64(text: str) -> str:
    clean = re.sub(r"^(Deirdre|Receptionist|Assistant|Doctor):\s*", "", text, flags=re.IGNORECASE).strip()
    clean = re.sub(r"`[^`]*`", "", clean).strip()
    # Strip any XML/HTML tags like <function=...>, <parameter=...>, <tool_call>, etc.
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = strip_emojis(clean)
    clean = verbalize_spoken_times(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return ""

    # 1. Fast in-memory cache lookup (0ms for greetings, closings, and repeated prompts)
    with _tts_cache_lock:
        cached = _tts_cache.get(clean)
        if cached is not None:
            _tts_cache.move_to_end(clean)
            return cached

    # 2. Single-stream GPU synthesis to avoid Python GIL / CUDA stream contention with event loop
    try:
        with tts_lock:
            generator = tts_pipeline(clean, voice="bf_isabella", speed=1.0)
            chunks = [audio for _, _, audio in generator]
        if not chunks:
            return ""
        combined = np.concatenate(chunks)
        buf = io.BytesIO()
        sf.write(buf, combined, 24000, format="WAV")
        b64_out = base64.b64encode(buf.getvalue()).decode("utf-8")
        with _tts_cache_lock:
            _tts_cache[clean] = b64_out
            if len(_tts_cache) > _TTS_CACHE_MAX:
                _tts_cache.popitem(last=False)
        return b64_out
    except Exception as e:
        print(f"[TTS Error]: {e}", flush=True)
        return ""

def wav_base64_to_pcm_24k(b64_wav: str) -> np.ndarray:
    """Converts a base64-encoded 24kHz WAV string into a 1D int16 NumPy array for LiveKit AudioSource."""
    if not b64_wav:
        return np.array([], dtype=np.int16)
    try:
        raw_bytes = base64.b64decode(b64_wav)
        pcm_int16, _ = sf.read(io.BytesIO(raw_bytes), dtype="int16")
        if pcm_int16.ndim > 1:
            pcm_int16 = pcm_int16[:, 0]
        return np.ascontiguousarray(pcm_int16, dtype=np.int16)
    except Exception as e:
        print(f"[TTS PCM Decode Error]: {e}", flush=True)
        return np.array([], dtype=np.int16)

def synthesize_pcm_24k(text: str) -> np.ndarray:
    """Synthesizes (or fetches from _tts_cache) 24kHz mono int16 PCM directly for LiveKit SIP."""
    b64_wav = synthesize_wav_base64(text)
    return wav_base64_to_pcm_24k(b64_wav)

# Polite conversational filler and common greeting/closing sentences pre-synthesized at startup for zero-latency playback
CHECK_FILLERS = []
BOOK_FILLERS = []
_filler_idx = 0

try:
    CHECK_FILLERS = [
        (synthesize_wav_base64("Let me check that for you now, just one moment please."), "Let me check that for you now, just one moment please."),
        (synthesize_wav_base64("Just one moment please, let me check the schedule for you."), "Just one moment please, let me check the schedule for you.")
    ]
    BOOK_FILLERS = [
        (synthesize_wav_base64("Just one moment please while I confirm that booking for you."), "Just one moment please while I confirm that booking for you.")
    ]
    # Pre-warm static greeting and closing sentences into _tts_cache
    for _warm_sentence in (
        "Hello, welcome to Star Dental and GP Clinic in Clonsilla.",
        "You are speaking with Deirdre, the clinic's automated AI receptionist.",
        "How can I help you today?",
        "Is there anything else I can help you with today?",
        "This sounds like an emergency. Please hang up immediately and dial 999 or 112 for an ambulance.",
    ):
        synthesize_wav_base64(_warm_sentence)
except Exception as e:
    print(f"[WARN] Failed to pre-synthesize filler audio: {e}", flush=True)

def get_check_filler():
    global _filler_idx
    valid = [item for item in CHECK_FILLERS if item[0]]
    if not valid:
        return "", ""
    item = valid[_filler_idx % len(valid)]
    _filler_idx += 1
    return item

def get_book_filler():
    global _filler_idx
    valid = [item for item in BOOK_FILLERS if item[0]]
    if not valid:
        return "", ""
    item = valid[_filler_idx % len(valid)]
    _filler_idx += 1
    return item

FILLER_AUDIO_B64 = CHECK_FILLERS[0][0] if (CHECK_FILLERS and CHECK_FILLERS[0][0]) else ""
