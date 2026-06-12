import logging

from mlx_lm import generate, load

from core.config import settings
from core.db.database import get_session
from core.db.models import Correction, Jargon
from core.stt.transcriber import ModelManager

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sen KatipAI not asistanısın. Verilen toplantı/konuşma transcript'inden Türkçe yapılandırılmış not üret.
Çıktı formatı (Markdown):
## Özet
2-4 cümle

## Önemli Anlar
- karar, action item, deadline

## Notlar
- kısa bullet'lar

Sadece Markdown döndür, ek açıklama yapma."""


class Summarizer:
    def __init__(self, model: str | None = None):
        self.model_name = model or settings.llm_model
        self._model = None
        self._tokenizer = None

    def _load(self):
        if self._model is None:
            ModelManager.mark_llm_loaded()
            self._model, self._tokenizer = load(self.model_name)
        return self._model, self._tokenizer

    def unload(self):
        self._model = None
        self._tokenizer = None
        ModelManager.mark_llm_unloaded()

    def _build_context(self) -> str:
        with get_session() as db:
            jargon = db.query(Jargon).all()
            corrections = db.query(Correction).filter(Correction.approved.is_(True)).limit(20).all()
        jargon_text = ", ".join(j.term for j in jargon) if jargon else ""
        correction_examples = "\n".join(
            f"- Yanlış: {c.original} → Doğru: {c.corrected}" for c in corrections
        )
        parts = []
        if jargon_text:
            parts.append(f"Jargon: {jargon_text}")
        if correction_examples:
            parts.append(f"Düzeltme örnekleri:\n{correction_examples}")
        return "\n".join(parts)

    def summarize_session(self, transcript_lines: list[str]) -> str:
        model, tokenizer = self._load()
        context = self._build_context()
        transcript = "\n".join(transcript_lines)
        prompt = f"""{SYSTEM_PROMPT}

{context}

Transcript:
{transcript}

Not:"""

        if tokenizer.chat_template:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"{context}\n\nTranscript:\n{transcript}"},
            ]
            prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)

        response = generate(model, tokenizer, prompt=prompt, max_tokens=1024, verbose=False)
        return response.strip()
