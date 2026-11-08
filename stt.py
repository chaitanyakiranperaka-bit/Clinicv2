import numpy as np
import torch
from faster_whisper import WhisperModel

# Automatically take advantage of NVIDIA A10G GPU on g5.2xlarge
device = "cuda" if torch.cuda.is_available() else "cpu"
compute_type = "float16" if device == "cuda" else "int8"
threads = 4 if device == "cpu" else 1

print(f"[INIT STT] Loading Faster-Whisper (small.en | device={device} compute_type={compute_type})...", flush=True)
stt_model = WhisperModel("small.en", device=device, compute_type=compute_type, cpu_threads=threads)

def transcribe(audio_np: np.ndarray) -> str:
    segments, _ = stt_model.transcribe(audio_np, beam_size=1, language="en")
    return " ".join([s.text for s in segments]).strip()
