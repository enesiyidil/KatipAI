import gc
import logging
from dataclasses import dataclass

import mlx_whisper

from core.config import settings
from core.db.database import get_session
from core.db.models import Jargon

logger = logging.getLogger(__name__)

CONFIDENCE_THRESHOLD = -0.8


@dataclass
class TranscriptionResult:
    text: str
    confidence: float
    needs_review: bool
    language: str


class ModelManager:
    """Ensures STT and LLM models are never loaded simultaneously."""

    _stt_loaded = False
    _llm_loaded = False

    @classmethod
    def mark_stt_loaded(cls) -> None:
        if cls._llm_loaded:
            raise RuntimeError("LLM must be unloaded before loading STT")
        cls._stt_loaded = True

    @classmethod
    def mark_stt_unloaded(cls) -> None:
        cls._stt_loaded = False
        gc.collect()

    @classmethod
    def mark_llm_loaded(cls) -> None:
        if cls._stt_loaded:
            raise RuntimeError("STT must be unloaded before loading LLM")
        cls._llm_loaded = True

    @classmethod
    def mark_llm_unloaded(cls) -> None:
        cls._llm_loaded = False
        gc.collect()


def build_jargon_prompt() -> str:
    with get_session() as db:
        terms = db.query(Jargon).all()
    if not terms:
        return "Türkçe teknik terimler, proje adları, kısaltmalar."
    parts = []
    for j in terms:
        if j.aliases:
            parts.append(f"{j.term} ({j.aliases})")
        else:
            parts.append(j.term)
    return "Sözlük: " + ", ".join(parts)


class Transcriber:
    def __init__(self, model: str | None = None):
        self.model = model or settings.stt_model

    def transcribe(self, audio_path: str) -> TranscriptionResult:
        ModelManager.mark_stt_loaded()
        try:
            initial_prompt = build_jargon_prompt()
            result = mlx_whisper.transcribe(
                audio_path,
                path_or_hf_repo=self.model,
                language=settings.stt_language,
                initial_prompt=initial_prompt,
                condition_on_previous_text=True,
                word_timestamps=True,
            )
            segments = result.get("segments", [])
            text = result.get("text", "").strip()
            if not text and segments:
                text = " ".join(s.get("text", "").strip() for s in segments).strip()

            confidences = [s.get("avg_logprob", 0.0) for s in segments if s.get("text")]
            avg_conf = sum(confidences) / len(confidences) if confidences else 0.0
            needs_review = avg_conf < CONFIDENCE_THRESHOLD or len(text) < 2

            return TranscriptionResult(
                text=text,
                confidence=round(avg_conf, 4),
                needs_review=needs_review,
                language=settings.stt_language,
            )
        finally:
            ModelManager.mark_stt_unloaded()
