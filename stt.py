import numpy as np
from faster_whisper import WhisperModel

print("[INIT STT] Loading Faster-Whisper (small.en | CPU int8 8-threads)...", flush=True)
stt_model = WhisperModel("small.en", device="cpu", compute_type="int8", cpu_threads=8)

def transcribe(audio_np: np.ndarray) -> str:
    segments, _ = stt_model.transcribe(audio_np, beam_size=1, language="en")
    return " ".join([s.text for s in segments]).strip()
