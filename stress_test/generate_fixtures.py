#!/usr/bin/env python3
"""Audio Fixture Pre-generator for Stress & Load Testing.

Synthesizes realistic human speech audio files (16kHz mono WAV) for all
stress test conversational turns. Uses:
  1. Kokoro-82M TTS (if available in current Python environment, e.g. EC2 voice-env)
  2. macOS 'say' + 'afconvert' (on macOS workstations)
  3. Linux 'espeak' / 'ffmpeg' (fallback)
"""

import os
import sys
import wave
import shutil
import argparse
import subprocess
from pathlib import Path

# Adjust path so stress_config can be imported
CURRENT_DIR = Path(__file__).resolve().parent
if str(CURRENT_DIR) not in sys.path:
    sys.path.insert(0, str(CURRENT_DIR))

from stress_config import TEST_SCRIPTS

FIXTURES_DIR = CURRENT_DIR / "audio_fixtures"
TARGET_SAMPLE_RATE = 16000

def synthesize_with_kokoro(text: str, dest_wav: Path, voice: str = "bm_george") -> bool:
    """Synthesizes speech using Kokoro-82M and resamples to 16kHz mono WAV."""
    try:
        from kokoro import KPipeline
        import numpy as np

        pipeline = KPipeline(lang_code="b")
        generator = pipeline(text, voice=voice, speed=1.0, split_pattern=r"\n+")
        audio_chunks = []
        for _, _, audio in generator:
            audio_chunks.append(audio)

        if not audio_chunks:
            return False

        full_audio = np.concatenate(audio_chunks)
        # Resample from 24000Hz (Kokoro native) to 16000Hz
        src_len = len(full_audio)
        dst_len = int(src_len * TARGET_SAMPLE_RATE / 24000)
        
        try:
            from scipy import signal
            resampled = signal.resample(full_audio, dst_len).astype(np.float32)
        except ImportError:
            # Linear interpolation fallback
            x_old = np.linspace(0, 1, src_len)
            x_new = np.linspace(0, 1, dst_len)
            resampled = np.interp(x_new, x_old, full_audio).astype(np.float32)

        # Convert float32 [-1, 1] to signed int16
        int16_samples = (np.clip(resampled, -1.0, 1.0) * 32767.0).astype(np.int16)

        with wave.open(str(dest_wav), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(TARGET_SAMPLE_RATE)
            wf.writeframes(int16_samples.tobytes())

        return True
    except Exception as e:
        print(f"Kokoro synthesis failed: {e}", file=sys.stderr)
        return False

def synthesize_with_macos_say(text: str, dest_wav: Path, voice: str = "Samantha") -> bool:
    """Synthesizes speech using macOS 'say' and converts to 16kHz WAV with 'afconvert'."""
    say_bin = shutil.which("say")
    afconvert_bin = shutil.which("afconvert")
    if not (say_bin and afconvert_bin):
        return False

    tmp_aiff = FIXTURES_DIR / f"_tmp_{os.getpid()}.aiff"
    try:
        subprocess.run([say_bin, "-v", voice, "-o", str(tmp_aiff), text], check=True, capture_output=True)
        subprocess.run(
            [afconvert_bin, "-f", "WAVE", "-d", "LEI16@16000", "-c", "1", str(tmp_aiff), str(dest_wav)],
            check=True,
            capture_output=True
        )
        return True
    except Exception as e:
        print(f"macOS say synthesis failed: {e}", file=sys.stderr)
        return False
    finally:
        if tmp_aiff.exists():
            tmp_aiff.unlink()

def synthesize_with_espeak(text: str, dest_wav: Path) -> bool:
    """Synthesizes speech using espeak / espeak-ng."""
    espeak_bin = shutil.which("espeak-ng") or shutil.which("espeak")
    if not espeak_bin:
        return False

    try:
        subprocess.run([espeak_bin, "-s", "140", "-w", str(dest_wav), text], check=True, capture_output=True)
        return True
    except Exception as e:
        print(f"espeak synthesis failed: {e}", file=sys.stderr)
        return False

def generate_all_fixtures(force: bool = False):
    """Generates WAV audio fixtures for all test script turns."""
    FIXTURES_DIR.mkdir(parents=True, exist_ok=True)
    print("=" * 78)
    print("  AUDIO FIXTURE GENERATION FOR STRESS TEST")
    print(f"  Destination directory: {FIXTURES_DIR}")
    print("=" * 78)

    generated = 0
    skipped = 0

    for script in TEST_SCRIPTS:
        script_id = script["id"]
        for turn in script.get("turns", []):
            turn_idx = turn["turn_index"]
            turn_key = f"{script_id}_t{turn_idx}"
            text = turn["text"]
            dest_wav = FIXTURES_DIR / f"{turn_key}.wav"

            if dest_wav.exists() and not force:
                print(f"  [EXISTS] {dest_wav.name:32} (Use --force to regenerate)")
                skipped += 1
                continue

            print(f"  [GENERATING] {dest_wav.name:28} -> \"{text[:45]}...\"")
            
            success = False
            # 1. Try Kokoro
            try:
                import kokoro
                success = synthesize_with_kokoro(text, dest_wav)
                if success:
                    print(f"    ✓ Generated via Kokoro-82M")
            except ImportError:
                pass

            # 2. Try macOS say
            if not success:
                success = synthesize_with_macos_say(text, dest_wav)
                if success:
                    print(f"    ✓ Generated via macOS say/afconvert")

            # 3. Try Linux espeak
            if not success:
                success = synthesize_with_espeak(text, dest_wav)
                if success:
                    print(f"    ✓ Generated via espeak")

            if success:
                generated += 1
            else:
                print(f"    ✗ Failed to synthesize {dest_wav.name}. No supported TTS engine found.")

    print("-" * 78)
    print(f"Summary: {generated} generated, {skipped} already present.")

    # Print table of fixtures
    print("\nVerified Fixtures on Disk:")
    for wav_file in sorted(FIXTURES_DIR.glob("*.wav")):
        try:
            with wave.open(str(wav_file), "rb") as w:
                p = w.getparams()
                dur = p.nframes / p.framerate
                print(f"  • {wav_file.name:32} | {dur:4.2f}s | {p.framerate}Hz | {p.nchannels}ch | {p.sampwidth*8}bit PCM")
        except Exception as e:
            print(f"  • {wav_file.name:32} | Corrupt: {e}")

    print("=" * 78 + "\n")

def main():
    parser = argparse.ArgumentParser(description="Pre-generate spoken audio fixtures for stress testing.")
    parser.add_argument("--force", action="store_true", help="Force regenerate fixtures even if they already exist.")
    args = parser.parse_args()

    generate_all_fixtures(force=args.force)

if __name__ == "__main__":
    main()

