"""Load uploaded audio bytes (WebM, WAV, etc.) into mono float32 @ target sample rate."""

from __future__ import annotations

import io
import logging
import shutil
import subprocess

import numpy as np
import scipy.io.wavfile as wavfile

logger = logging.getLogger(__name__)


def _load_wav_bytes(data: bytes) -> tuple[np.ndarray, int]:
    buf = io.BytesIO(data)
    sr, audio = wavfile.read(buf)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)
    if audio.max() > 1.0:
        audio = audio / 32767.0
    return audio, int(sr)


def _load_ffmpeg_bytes(data: bytes, target_sr: int) -> np.ndarray:
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg bulunamadı — brew install ffmpeg")

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-i",
        "pipe:0",
        "-f",
        "f32le",
        "-acodec",
        "pcm_f32le",
        "-ac",
        "1",
        "-ar",
        str(target_sr),
        "pipe:1",
    ]
    proc = subprocess.run(cmd, input=data, capture_output=True, check=False)
    if proc.returncode != 0:
        err = proc.stderr.decode(errors="replace").strip() or "ffmpeg decode failed"
        raise ValueError(err)

    audio = np.frombuffer(proc.stdout, dtype=np.float32)
    if audio.size == 0:
        raise ValueError("Boş ses verisi")
    return audio


def load_audio_bytes(data: bytes, target_sr: int = 16000) -> np.ndarray:
    """Decode arbitrary audio bytes to mono float32 at target_sr."""
    if len(data) < 100:
        raise ValueError("Ses dosyası çok kısa")

    # Fast path for WAV uploads
    if data[:4] == b"RIFF":
        try:
            audio, sr = _load_wav_bytes(data)
            if sr != target_sr:
                from scipy import signal

                num_samples = int(len(audio) * target_sr / sr)
                audio = signal.resample(audio, num_samples).astype(np.float32)
            return audio
        except Exception:
            pass

    try:
        return _load_ffmpeg_bytes(data, target_sr)
    except Exception as ffmpeg_err:
        try:
            audio, sr = _load_wav_bytes(data)
            if sr != target_sr:
                from scipy import signal

                num_samples = int(len(audio) * target_sr / sr)
                audio = signal.resample(audio, num_samples).astype(np.float32)
            return audio
        except Exception:
            raise ValueError(str(ffmpeg_err)) from ffmpeg_err
