import logging
from datetime import datetime, timezone

from core.db.database import get_session
from core.db.models import Chunk, Session, SessionStatus, Transcript
from core.llm.summarizer import Summarizer
from core.stt.transcriber import Transcriber
from core.vault.general_notes import extract_general_note, is_general_note_command
from core.vault.writer import VaultWriter

logger = logging.getLogger(__name__)


class NotePipeline:
    def __init__(self):
        self.transcriber = Transcriber()
        self.summarizer = Summarizer()
        self.vault = VaultWriter()

    async def process_chunk(self, chunk_id: int) -> None:
        session_id: int | None = None
        skipped = False

        with get_session() as db:
            chunk = db.get(Chunk, chunk_id)
            if not chunk:
                return
            session_id = chunk.session_id
            if chunk.skip_reason in ("echo", "voice_mismatch"):
                logger.info("Chunk %s atlandı (STT): %s", chunk_id, chunk.skip_reason)
                db.add(
                    Transcript(
                        chunk_id=chunk_id,
                        text="",
                        confidence=0.0,
                        needs_review=False,
                    )
                )
                skipped = True

        if skipped:
            if session_id is not None:
                await self.try_finalize_session(session_id)
            return

        with get_session() as db:
            chunk = db.get(Chunk, chunk_id)
            if not chunk:
                return
            audio_path = chunk.audio_path
            session_id = chunk.session_id
            started_at = chunk.started_at
            speaker = chunk.speaker_label

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

        if result.rejected:
            logger.info("Chunk %s reddedildi: %s", chunk_id, result.reject_reason)
        else:
            logger.info("Transcribed chunk %s: %s...", chunk_id, result.text[:60])

        if self.vault.enabled and result.text.strip() and not result.rejected:
            time_str = started_at.strftime("%H:%M")
            self.vault.append_transcript_line(
                dt=started_at,
                time_str=time_str,
                speaker=speaker,
                text=result.text,
            )

            if is_general_note_command(result.text):
                note = extract_general_note(result.text)
                path = self.vault.append_general_note(
                    dt=started_at,
                    time_str=time_str,
                    note_text=note,
                    source_transcript=result.text,
                )
                logger.info("Genel not eklendi: %s", path)

        await self.try_finalize_session(session_id)

    async def try_finalize_session(self, session_id: int) -> None:
        """Oturum kapandıysa ve tüm chunk'lar transcript edildiyse özet üret."""
        with get_session() as db:
            session = db.get(Session, session_id)
            if not session or session.summary:
                return
            if session.status not in (SessionStatus.IDLE.value,):
                return
            chunks = db.query(Chunk).filter(Chunk.session_id == session_id).all()
            if not chunks:
                return
            if any(c.transcript is None for c in chunks):
                return

        await self.finalize_session(session_id)

    async def finalize_session(self, session_id: int) -> None:
        with get_session() as db:
            session = db.get(Session, session_id)
            if not session:
                return
            if session.summary:
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
                if chunk.transcript and chunk.transcript.text.strip():
                    ts = chunk.started_at.strftime("%H:%M")
                    lines.append(f"[{ts}] **{chunk.speaker_label}**: {chunk.transcript.text}")

        if not lines:
            return

        summary = self.summarizer.summarize_session(lines)
        self.summarizer.unload()

        vault_path = None
        if self.vault.enabled:
            vault_path = self.vault.write_session(
                session_id=session_id,
                started_at=started,
                duration_min=max(1, int((ended - started).total_seconds() / 60)),
                speakers=sorted(speakers),
                summary_md=summary,
                transcript_lines=lines,
            )

        with get_session() as db:
            session = db.get(Session, session_id)
            if session and not session.summary:
                session.summary = summary
                if vault_path:
                    session.vault_file = str(vault_path)

        logger.info("Session %s finalized", session_id)
