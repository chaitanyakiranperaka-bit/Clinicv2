import os
import io
import math
import random
import struct
import array
from pathlib import Path
from typing import Dict, Optional, Union

try:
    import numpy as np
    HAS_NUMPY = True
except ImportError:
    np = None
    HAS_NUMPY = False

FIXTURES_DIR = Path(__file__).resolve().parent / "audio_fixtures"
SAMPLE_RATE = 16000

def ensure_fixtures_dir():
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)

def generate_synthetic_speech(duration_sec: float = 3.0, base_freq: float = 140.0) -> bytes:
    """Generates synthetic voiced formant speech signal as raw float32 PCM bytes
    with natural vocal harmonics and syllable envelope modulation.
    Reliably triggers Silero VAD (prob > 0.85, RMS > 0.05).
    """
    num_samples = int(duration_sec * SAMPLE_RATE)
    
    if HAS_NUMPY:
        t = np.linspace(0, duration_sec, num_samples, endpoint=False, dtype=np.float32)
        f0 = base_freq + 18.0 * np.sin(2 * np.pi * 1.5 * t)
        phase = 2 * np.pi * np.cumsum(f0) / SAMPLE_RATE

        h1 = 0.50 * np.sin(phase)
        h2 = 0.35 * np.sin(2 * phase)
        h3 = 0.25 * np.sin(3 * phase)
        f1 = 0.30 * np.sin(2 * np.pi * 520 * t)
        f2 = 0.20 * np.sin(2 * np.pi * 1550 * t)
        f3 = 0.10 * np.sin(2 * np.pi * 2450 * t)
        raw_voice = h1 + h2 + h3 + f1 + f2 + f3

        syllables = np.maximum(0.0, np.sin(2 * np.pi * 4.2 * t)) ** 2
        noise = 0.03 * np.random.normal(0, 1, num_samples).astype(np.float32)
        voice_modulated = (raw_voice * syllables) + noise

        current_rms = float(np.sqrt(np.mean(voice_modulated ** 2)))
        if current_rms > 1e-4:
            voice_modulated = (voice_modulated / current_rms) * 0.12
        return voice_modulated.astype(np.float32).tobytes()

    # Pure standard library fallback using array.array('f')
    samples = array.array('f')
    phase = 0.0
    for i in range(num_samples):
        t = i / SAMPLE_RATE
        f0 = base_freq + 18.0 * math.sin(2 * math.pi * 1.5 * t)
        phase += 2 * math.pi * f0 / SAMPLE_RATE
        val = (
            0.50 * math.sin(phase) +
            0.35 * math.sin(2 * phase) +
            0.25 * math.sin(3 * phase) +
            0.30 * math.sin(2 * math.pi * 520 * t) +
            0.20 * math.sin(2 * math.pi * 1550 * t)
        )
        syllable = max(0.0, math.sin(2 * math.pi * 4.2 * t)) ** 2
        noise = random.gauss(0, 0.03)
        sample = (val * syllable + noise) * 0.12
        samples.append(sample)
    return samples.tobytes()

def generate_silence(duration_sec: float = 1.35) -> bytes:
    """Generates quiet acoustic room silence with gentle background noise (RMS ~0.0008)
    to cleanly trigger Silero VAD pause hysteresis (38 silence frames = ~1.22s).
    """
    num_samples = int(duration_sec * SAMPLE_RATE)
    if HAS_NUMPY:
        noise = np.random.normal(0, 0.0008, num_samples).astype(np.float32)
        return noise.tobytes()

    samples = array.array('f')
    for _ in range(num_samples):
        samples.append(random.gauss(0, 0.0008))
    return samples.tobytes()

def get_turn_audio_bytes(text: str, turn_key: str) -> bytes:
    """Returns 16kHz float32 PCM bytes for the full turn (speech + trailing silence)."""
    words = text.split()
    duration = max(1.8, len(words) * 0.32)
    speech = generate_synthetic_speech(duration_sec=duration)
    silence = generate_silence(duration_sec=1.35)
    return speech + silence
