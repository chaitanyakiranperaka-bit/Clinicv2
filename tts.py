import io
import re
import base64
import numpy as np
import soundfile as sf
from kokoro import KPipeline

print("[INIT TTS] Loading Kokoro-82M (bf_isabella)...", flush=True)
tts_pipeline = KPipeline(lang_code="b")

def synthesize_wav_base64(text: str) -> str:
    clean = re.sub(r"^(Deirdre|Receptionist|Assistant|Doctor):\s*", "", text, flags=re.IGNORECASE).strip()
    clean = re.sub(r"`[^`]*`", "", clean).strip()
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
