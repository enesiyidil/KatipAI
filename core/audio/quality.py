import re
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile

from core.config import settings

# Whisper'ın sessiz/gürültülü seslerde sık ürettiği Türkçe halüsinasyonlar
HALLUCINATION_PATTERNS = [
    re.compile(p, re.IGNORECASE)
    for p in (
        r"^altyazı\s+m\.?\s*k\.?\s*$",
        r"^abone\s+ol(\s+abone\s+ol)+",
        r"^izlediğiniz\s+için\s+teşekkür",
        r"^www\.",
        r"^subtitle",
        r"^thanks\s+for\s+watching",
        r"^(presp)+$",
        r"^[\W\d]+$",
    )
]

# Tekrarlayan kısa kelime dizileri (ör. "abone ol abone ol...")
REPETITIVE_PATTERN = re.compile(r"^(.{2,20})(\s+\1){2,}$", re.IGNORECASE)


def audio_rms(path: str | Path) -> float:
    sr, data = wavfile.read(str(path))
    audio = data.astype(np.float32)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    if data.dtype == np.int16:
        audio /= 32768.0
    elif np.max(np.abs(audio)) > 1.0:
        audio /= np.max(np.abs(audio))
    return float(np.sqrt(np.mean(audio**2)))


def is_loud_enough(rms: float) -> bool:
    return rms >= settings.min_audio_rms


def is_hallucination(text: str) -> bool:
    text = text.strip()
    if not text:
        return True
    if len(text) < 3:
        return True
    normalized = re.sub(r"\s+", " ", text)
    if any(p.search(normalized) for p in HALLUCINATION_PATTERNS):
        return True
    if REPETITIVE_PATTERN.match(normalized):
        return True
    # Çok düşük benzersiz kelime oranı (tekrar spam)
    words = normalized.lower().split()
    if len(words) >= 4 and len(set(words)) <= 2:
        return True
    return False
