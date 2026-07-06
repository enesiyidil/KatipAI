import logging

import numpy as np
from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from core.audio.audio_io import load_audio_bytes
from core.audio.voice_profile import VoiceProfileService, SAMPLE_RATE
from core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter()

ENROLLMENT_TEXT = (
    "Merhaba, ben KatipAI ses profilimi oluşturuyorum. "
    "Bu kayıt sayesinde sistem yalnızca benim sesimi tanıyacak. "
    "Bugün hava güzel, toplantıda önemli konuları konuşacağız. "
    "Teknoloji, yapay zeka ve verimlilik üzerine notlar alıyorum."
)

ENROLLMENT_AUDIO_PATH = settings.data_dir / "voice_enrollment.webm"


@router.get("/voice/status")
def voice_status():
    svc = VoiceProfileService()
    status = svc.status()
    status["enrollment_text"] = ENROLLMENT_TEXT
    return status


@router.get("/voice/enrollment-audio")
def voice_enrollment_audio():
    if not ENROLLMENT_AUDIO_PATH.exists():
        raise HTTPException(404, "Kayıt dosyası yok")
    return FileResponse(ENROLLMENT_AUDIO_PATH, media_type="audio/webm", filename="enrollment.webm")


@router.post("/voice/enroll")
async def voice_enroll(file: UploadFile = File(...)):
    data = await file.read()
    if len(data) < 1000:
        raise HTTPException(400, "Kayıt çok kısa — en az 10 saniye konuşun")
    try:
        audio = load_audio_bytes(data, SAMPLE_RATE)
    except Exception as e:
        raise HTTPException(400, f"Ses dosyası okunamadı: {e}")

    min_samples = SAMPLE_RATE * 10
    if len(audio) < min_samples:
        raise HTTPException(400, "Kayıt en az 10 saniye olmalı")

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

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    ENROLLMENT_AUDIO_PATH.write_bytes(data)
    logger.info("Enrollment audio saved (%d bytes)", len(data))

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
        audio = load_audio_bytes(data, SAMPLE_RATE)
    except Exception as e:
        raise HTTPException(400, f"Ses dosyası okunamadı: {e}")

    score = svc.match(audio)
    threshold = settings.voice_match_threshold
    return {
        "score": score,
        "threshold": threshold,
        "match": score >= threshold,
        "label": "Ben" if score >= threshold else "Bilinmeyen",
        "profile_valid": svc.status().get("profile_valid", True),
    }
