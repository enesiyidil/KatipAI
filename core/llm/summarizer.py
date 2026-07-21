import logging
import re

from mlx_lm import generate, load

from core.config import settings
from core.db.database import get_session
from core.db.models import Correction, Jargon
from core.stt.transcriber import ModelManager

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """Sen KatipAI not asistanısın. Verilen konuşma transcript'inden Türkçe yapılandırılmış not üret.

KURALLAR:
- Sadece aşağıdaki Markdown formatını yaz
- Düşünme süreci, açıklama, analiz YAZMA
- "Thinking Process" veya benzeri metin YAZMA

FORMAT:
## Özet
(2-4 cümle)

## Önemli Anlar
- (karar, action item, deadline)

## Notlar
- (kısa bullet'lar)"""


def _clean_output(text: str) -> str:
    """Strip Qwen thinking/reasoning; keep only the note markdown."""
    text = text.strip()

    # Remove Qwen thinking blocks
    text = re.sub(r"``", "", text, flags=re.DOTALL | re.IGNORECASE)

    # Drop everything before the first ## Özet (or other section headers)
    for marker in ("## Özet", "## Önemli Anlar", "## Notlar"):
        idx = text.find(marker)
        if idx != -1:
            text = text[idx:]
            break
    else:
        # Fallback: strip "Thinking Process:" preamble
        if "Thinking Process:" in text:
            parts = re.split(r"\n(?=## )", text)
            text = next((p for p in parts if p.startswith("## ")), text)

    # Trim trailing junk after last meaningful section
    lines = text.splitlines()
    out: list[str] = []
    in_note = False
    for line in lines:
        if line.startswith("## "):
            in_note = True
        if in_note:
            out.append(line)
    text = "\n".join(out).strip() if out else text.strip()

    return text


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
            jargon_terms = [j.term for j in db.query(Jargon).all()]
            corrections = [
                (c.original, c.corrected)
                for c in db.query(Correction)
                .filter(Correction.approved.is_(True))
                .limit(20)
                .all()
            ]
        jargon_text = ", ".join(jargon_terms) if jargon_terms else ""
        correction_examples = "\n".join(
            f"- Yanlış: {original} → Doğru: {corrected}" for original, corrected in corrections
        )
        parts = []
        if jargon_text:
            parts.append(f"Jargon: {jargon_text}")
        if correction_examples:
            parts.append(f"Düzeltme örnekleri:\n{correction_examples}")
        return "\n".join(parts)

    def _build_prompt(self, context: str, transcript: str) -> str:
        _, tokenizer = self._load()
        user_content = f"/no_think\n\n{context}\n\nTranscript:\n{transcript}" if context else f"/no_think\n\nTranscript:\n{transcript}"

        if tokenizer.chat_template:
            messages = [
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ]
            try:
                return tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=False,
                )
            except TypeError:
                return tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True
                )

        return f"{SYSTEM_PROMPT}\n\n{user_content}\n\nNot:"

    def summarize_session(self, transcript_lines: list[str]) -> str:
        context = self._build_context()
        model, tokenizer = self._load()
        transcript = "\n".join(transcript_lines)
        prompt = self._build_prompt(context, transcript)

        raw = generate(
            model,
            tokenizer,
            prompt=prompt,
            max_tokens=512,
            verbose=False,
        )
        cleaned = _clean_output(raw)

        if not cleaned.startswith("##"):
            logger.warning("LLM output missing markdown headers, using fallback")
            cleaned = self._fallback_summary(transcript_lines)

        return cleaned

    @staticmethod
    def _fallback_summary(transcript_lines: list[str]) -> str:
        bullets = "\n".join(f"- {line}" for line in transcript_lines[:10])
        return f"""## Özet
Konuşma kaydı transcript'ten derlendi.

## Önemli Anlar
{bullets}

## Notlar
- Tam transcript arşivde."""

    def generate_meeting_title(self, snippet: str) -> str:
        """Short meeting title from transcript/summary snippet."""
        model, tokenizer = self._load()
        prompt_text = (
            "/no_think\n\n"
            "Aşağıdaki toplantı metninden 3-8 kelimelik Türkçe bir toplantı başlığı üret. "
            "Sadece başlığı yaz, tırnak veya açıklama ekleme.\n\n"
            f"{snippet[:800]}"
        )
        if tokenizer.chat_template:
            messages = [
                {"role": "user", "content": prompt_text},
            ]
            try:
                prompt = tokenizer.apply_chat_template(
                    messages, tokenize=False, add_generation_prompt=True, enable_thinking=False
                )
            except TypeError:
                prompt = tokenizer.apply_chat_template(messages, tokenize=False, add_generation_prompt=True)
        else:
            prompt = prompt_text

        raw = generate(model, tokenizer, prompt=prompt, max_tokens=32, verbose=False)
        title = raw.strip().split("\n")[0].strip().strip('"').strip("'")
        if len(title) > 120:
            title = title[:117] + "..."
        return title or "Toplantı"
