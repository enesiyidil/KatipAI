import re
import unicodedata
from collections import Counter
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile

from core.config import settings

# Whisper gürültüde sık ürettiği CJK / Arap / Kiril karakterler
_NON_LATIN_SCRIPT = re.compile(
    r"[\u0400-\u04ff\u0600-\u06ff\u0900-\u097f\u3040-\u30ff\u3400-\u9fff\uf900-\ufaff]"
)

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
# Karakter / hece yığınları: mmmm, ıııı, hahaha, e-e-e
CHAR_RUN_PATTERN = re.compile(r"(.)\1{4,}", re.IGNORECASE)
SYLLABLE_STUTTER = re.compile(r"^(\w{1,3})([-\s]\1){3,}", re.IGNORECASE)


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


def _latin_letter_ratio(text: str) -> float:
    letters = [ch for ch in text if ch.isalpha()]
    if not letters:
        return 0.0
    latin = sum(
        1
        for ch in letters
        if "LATIN" in unicodedata.name(ch, "")
        or ch in "çğıöşüÇĞİÖŞÜ"
    )
    return latin / len(letters)


def is_hallucination(text: str) -> bool:
    text = text.strip()
    if not text:
        return True
    if len(text) < 3:
        return True
    normalized = re.sub(r"\s+", " ", text)
    if _NON_LATIN_SCRIPT.search(normalized):
        return True
    # İzlandaca / bozuk Latin (Við, alðist vb.)
    if re.search(r"[ðþÐÞ]", normalized):
        return True
    if _latin_letter_ratio(normalized) < 0.85:
        return True
    if any(p.search(normalized) for p in HALLUCINATION_PATTERNS):
        return True
    if REPETITIVE_PATTERN.match(normalized):
        return True
    if CHAR_RUN_PATTERN.search(normalized):
        return True
    if SYLLABLE_STUTTER.search(normalized):
        return True

    # Compact form without spaces for runs like "hahahaha"
    compact = re.sub(r"[\s\-_.]+", "", normalized.lower())
    if len(compact) >= 6 and CHAR_RUN_PATTERN.search(compact):
        return True

    words = normalized.lower().split()
    if len(words) >= 4 and len(set(words)) <= 2:
        return True
    # Düşük unique-token oranı
    if len(words) >= 6:
        unique_ratio = len(set(words)) / len(words)
        if unique_ratio <= 0.35:
            return True
    # Tek kelimenin metnin çoğunu tekrar etmesi (buses buses buses...)
    if len(words) >= 3:
        top_word, top_count = Counter(words).most_common(1)[0]
        if top_count >= 3 and top_count / len(words) >= 0.45:
            return True
    # Whisper jargon sızıntısı: "abela", "Bonnie" vb. tekrarlar
    if re.search(r"(abela){3,}", normalized, re.IGNORECASE):
        return True
    if re.search(r"(bonnie\s*){3,}", normalized, re.IGNORECASE):
        return True
    return False
