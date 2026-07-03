import io
import logging

import numpy as np
import scipy.io.wavfile as wavfile
from fastapi import APIRouter, File, HTTPException, UploadFile

from core.audio.voice_profile import VoiceProfileService, SAMPLE_RATE

logger = logging.getLogger(__name__)
router = APIRouter()

ENROLLMENT_TEXT = (
    "Merhaba, ben KatipAI ses profilimi oluşturuyorum. "
    "Bu kayıt sayesinde sistem yalnızca benim sesimi tanıyacak. "
    "Bugün hava güzel, toplantıda önemli konuları konuşacağız. "
    "Teknoloji, yapay zeka ve verimlilik üzerine notlar alıyorum."
)


def _load_wav_bytes(data: bytes) -> np.ndarray:
    buf = io.BytesIO(data)
    sr, audio = wavfile.read(buf)
    if audio.ndim > 1:
        audio = audio.mean(axis=1)
    audio = audio.astype(np.float32)
    if audio.max() > 1.0:
        audio = audio / 32767.0
    if sr != SAMPLE_RATE:
        from scipy import signal

        num_samples = int(len(audio) * SAMPLE_RATE / sr)
        audio = signal.resample(audio, num_samples).astype(np.float32)
    return audio


@router.get("/voice/status")
def voice_status():
    svc = VoiceProfileService()
    status = svc.status()
    status["enrollment_text"] = ENROLLMENT_TEXT
    return status


@router.post("/voice/enroll")
async def voice_enroll(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) < 1000:
        raise HTTPException(400, "Kayıt çok kısa — en az 10 saniye konuşun")
    try:
        audio = _load_wav_bytes(data)
    except Exception as e:
        raise HTTPException(400, f"Geçersiz ses dosyası: {e}")

    min_samples = SAMPLE_RATE * 10
    if len(audio) < min_samples:
        raise HTTPException(400, "Kayıt en az 10 saniye olmalı")

    # Split into ~5s segments for robust centroid
    seg_len = SAMPLE_RATE * 5
    segments = []
    for i in range(0, len(audio) - seg_len + 1, seg_len):
        segments.append(audio[i : i + seg_len])
    if not segments:
        segments = [audio]

    svc = VoiceProfileService()
    try:
        avg_self_sim = svc.enroll(segments)
    except ValueError as e:
        raise HTTPException(400, str(e))

    return {"ok": True, "sample_count": len(segments), "self_similarity": avg_self_sim, **svc.status()}


@router.delete("/voice/profile")
def voice_delete():
    VoiceProfileService().delete_profile()
    return {"ok": True, **VoiceProfileService().status()}


@router.post("/voice/test")
async def voice_test(file: UploadFile = File(...)):
    svc = VoiceProfileService()
    if not svc.is_enrolled():
        raise HTTPException(409, "Önce ses profilinizi oluşturun")

    data = await file.read()
    try:
        audio = _load_wav_bytes(data)
    except Exception as e:
        raise HTTPException(400, f"Geçersiz ses dosyası: {e}")

    score = svc.match(audio)
    from core.config import settings

    threshold = settings.voice_match_threshold
    return {
        "score": score,
        "threshold": threshold,
        "match": score >= threshold,
        "label": "Ben" if score >= threshold else "Bilinmeyen",
    }
