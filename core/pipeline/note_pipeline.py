import logging
from datetime import datetime, timezone

from core.db.database import get_session
from core.db.models import Chunk, Session, Transcript
from core.llm.summarizer import Summarizer
from core.stt.transcriber import Transcriber
from core.vault.writer import VaultWriter

logger = logging.getLogger(__name__)


class NotePipeline:
    def __init__(self):
        self.transcriber = Transcriber()
        self.summarizer = Summarizer()
        self.vault = VaultWriter()

    async def process_chunk(self, chunk_id: int) -> None:
        with get_session() as db:
            chunk = db.get(Chunk, chunk_id)
            if not chunk:
                return
            audio_path = chunk.audio_path
            speaker = chunk.speaker_label
            session_id = chunk.session_id

        result = self.transcriber.transcribe(audio_path)
        with get_session() as db:
            chunk = db.get(Chunk, chunk_id)
            if not chunk:
                return
            transcript = Transcript(
                chunk_id=chunk_id,
                text=result.text,
                confidence=result.confidence,
                language=result.language,
                needs_review=result.needs_review,
            )
            db.add(transcript)

        logger.info("Transcribed chunk %s: %s...", chunk_id, result.text[:60])

    async def finalize_session(self, session_id: int) -> None:
        with get_session() as db:
            session = db.get(Session, session_id)
            if not session:
                return
            started = session.started_at
            ended = session.ended_at or datetime.now(timezone.utc)
            chunks = (
                db.query(Chunk)
                .filter(Chunk.session_id == session_id)
                .order_by(Chunk.started_at)
                .all()
            )
            lines = []
            speakers = set()
            for chunk in chunks:
                speakers.add(chunk.speaker_label)
                if chunk.transcript:
                    ts = chunk.started_at.strftime("%H:%M")
                    lines.append(f"[{ts}] **{chunk.speaker_label}**: {chunk.transcript.text}")

        if not lines:
            return

        summary = self.summarizer.summarize_session(lines)
        self.summarizer.unload()

        duration_min = max(1, int((ended - started).total_seconds() / 60))

        vault_path = None
        if self.vault.enabled:
            vault_path = self.vault.write_session(
                session_id=session_id,
                started_at=started,
                duration_min=duration_min,
                speakers=sorted(speakers),
                summary_md=summary,
                transcript_lines=lines,
            )

        with get_session() as db:
            session = db.get(Session, session_id)
            if session:
                session.summary = summary
                if vault_path:
                    session.vault_file = str(vault_path)

        logger.info("Session %s finalized", session_id)
