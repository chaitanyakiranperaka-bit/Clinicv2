import io
import re
import base64
import numpy as np
import soundfile as sf
from kokoro import KPipeline

print("[INIT TTS] Loading Kokoro-82M (bf_isabella)...", flush=True)
tts_pipeline = KPipeline(lang_code="b")

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

def synthesize_wav_base64(text: str) -> str:
    clean = re.sub(r"^(Deirdre|Receptionist|Assistant|Doctor):\s*", "", text, flags=re.IGNORECASE).strip()
    clean = re.sub(r"`[^`]*`", "", clean).strip()
    # Strip any XML/HTML tags like <function=...>, <parameter=...>, <tool_call>, etc.
    clean = re.sub(r"<[^>]+>", " ", clean)
    clean = strip_emojis(clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    if not clean:
        return ""
    try:
        generator = tts_pipeline(clean, voice="bf_isabella", speed=1.0)
        chunks = [audio for _, _, audio in generator]
        if not chunks:
            return ""
        combined = np.concatenate(chunks)
        buf = io.BytesIO()
        sf.write(buf, combined, 24000, format="WAV")
        return base64.b64encode(buf.getvalue()).decode("utf-8")
    except Exception as e:
        print(f"[TTS Error]: {e}", flush=True)
        return ""

FILLER_AUDIO_B64 = synthesize_wav_base64("One moment please while I access the clinic schedule.")
