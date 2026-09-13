import logging
import math
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile
from sqlalchemy import or_

from core.audio.meeting_segments import assign_meeting_speakers, split_channel_segments
from core.audio.voice_matcher import VoiceMatcher
from core.config import settings
from core.db.database import get_session
from core.db.models import Chunk, RecordingMode, Session, SessionStatus, Transcript
from core.llm.summarizer import Summarizer
from core.meetings.metadata import (
    set_meeting_failed,
    set_meeting_ready,
)
from core.pipeline.worker import run_ml
from core.stt.transcriber import Transcriber
from core.vault.general_notes import extract_general_note, is_general_note_command
from core.vault.writer import VaultWriter

logger = logging.getLogger(__name__)


def _safe_confidence(value: float | None) -> float:
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return 0.0
    return float(value)


def find_pending_chunk_ids(limit: int = 20) -> list[int]:
    """Recent chunks without transcript — capped to avoid blocking live capture."""
    with get_session() as db:
        rows = (
            db.query(Chunk.id)
            .outerjoin(Transcript, Transcript.chunk_id == Chunk.id)
            .filter(
                Transcript.id.is_(None),
                or_(Chunk.skip_reason.is_(None), Chunk.skip_reason == ""),
            )
            .order_by(Chunk.id.desc())
            .limit(limit)
            .all()
        )
        return [row[0] for row in reversed(rows)]


class NotePipeline:
    def __init__(self):
        self.transcriber = Transcriber()
        self.summarizer = Summarizer()
        self.vault = VaultWriter()
        self._voice_matcher = VoiceMatcher()

    @staticmethod
    def mark_chunk_failed(chunk_id: int, error: str) -> bool:
        """Persist a failed transcript so UI does not spin forever."""
        with get_session() as db:
            chunk = db.get(Chunk, chunk_id)
            if not chunk or chunk.transcript is not None:
                return False
            db.add(
                Transcript(
                    chunk_id=chunk_id,
                    text="",
                    confidence=0.0,
                    needs_review=True,
                    processing_error=(error or "unknown")[:2000],
                )
            )
        logger.warning("Chunk %s marked failed: %s", chunk_id, error[:200])
        return True

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
            channel = chunk.channel

        use_jargon = channel != "system"
        result = await run_ml(self.transcriber.transcribe, audio_path, use_jargon=use_jargon)

        with get_session() as db:
            chunk = db.get(Chunk, chunk_id)
            if not chunk:
                return
            transcript = Transcript(
                chunk_id=chunk_id,
                text=result.text or "",
                confidence=_safe_confidence(result.confidence),
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

    async def process_meeting_session(self, session_id: int) -> None:
        """Toplantı bittiğinde stereo kaydı kanallara ayırıp tek seferde STT."""
        try:
            await self._process_meeting_session_inner(session_id)
            set_meeting_ready(session_id)
        except Exception as e:
            logger.exception("Meeting %s processing failed", session_id)
            set_meeting_failed(session_id, str(e))
            raise

    async def _process_meeting_session_inner(self, session_id: int) -> None:
        with get_session() as db:
            session = db.get(Session, session_id)
            if not session:
                return
            if session.mode != RecordingMode.MEETING.value:
                return
            started = session.started_at
            master = (
                db.query(Chunk)
                .filter(Chunk.session_id == session_id, Chunk.channel == "meeting")
                .order_by(Chunk.id.desc())
                .first()
            )
            if not master:
                logger.warning("Meeting %s: master chunk missing", session_id)
                return
            stereo_path = Path(master.audio_path)

        if not stereo_path.exists():
            raise FileNotFoundError(f"Audio missing: {stereo_path}")

        sr, data = wavfile.read(str(stereo_path))
        if data.ndim == 1:
            mic = data.astype(np.float32)
            if mic.max() > 1.0:
                mic /= 32768.0
            system = np.zeros_like(mic)
        else:
            mic = data[:, 0].astype(np.float32)
            system = data[:, 1].astype(np.float32)
            if mic.max() > 1.0:
                mic /= 32768.0
                system /= 32768.0

        mic_segs = split_channel_segments(mic, channel="mic", speaker_label="Ben", session_start=started)
        sys_segs = split_channel_segments(
            system, channel="system", speaker_label="Diğer", session_start=started
        )
        mic_segs, sys_segs, speaker_warning = assign_meeting_speakers(
            mic_segs, sys_segs, mic, system, voice_matcher=self._voice_matcher
        )
        if speaker_warning:
            logger.warning("Meeting %s: %s", session_id, speaker_warning)
            with get_session() as db:
                session = db.get(Session, session_id)
                if session and not session.processing_error:
                    # Soft hint stored separately from hard failures
                    pass

        all_segs = sorted(mic_segs + sys_segs, key=lambda s: s.started_at)
        logger.info(
            "Meeting %s: transcribing %d segments (%d mic, %d system)%s",
            session_id,
            len(all_segs),
            len(mic_segs),
            len(sys_segs),
            f" — {speaker_warning}" if speaker_warning else "",
        )

        out_dir = settings.audio_dir / str(session_id)
        out_dir.mkdir(parents=True, exist_ok=True)

        # Replace prior segment chunks; keep stereo master for reprocess
        with get_session() as db:
            chunks = (
                db.query(Chunk)
                .filter(Chunk.session_id == session_id, Chunk.channel != "meeting")
                .all()
            )
            for chunk in chunks:
                db.delete(chunk)

        transcript_lines: list[str] = []
        for idx, seg in enumerate(all_segs):
            seg_path = out_dir / f"meeting_seg_{idx:04d}_{seg.channel}.wav"
            clipped = np.clip(seg.audio, -1.0, 1.0)
            wavfile.write(seg_path, settings.sample_rate, (clipped * 32767).astype(np.int16))

            use_jargon = seg.speaker_label == "Ben"
            result = await run_ml(self.transcriber.transcribe, str(seg_path), use_jargon=use_jargon)

            with get_session() as db:
                chunk = Chunk(
                    session_id=session_id,
                    channel=seg.channel,
                    speaker_label=seg.speaker_label,
                    audio_path=str(seg_path),
                    started_at=seg.started_at,
                    duration_ms=seg.duration_ms,
                )
                db.add(chunk)
                db.flush()
                db.add(
                    Transcript(
                        chunk_id=chunk.id,
                        text=result.text or "",
                        confidence=_safe_confidence(result.confidence),
                        language=result.language,
                        needs_review=result.needs_review,
                    )
                )

            if result.text.strip() and not result.rejected:
                ts = seg.started_at.strftime("%H:%M")
                transcript_lines.append(f"[{ts}] **{seg.speaker_label}**: {result.text}")

            if self.vault.enabled and result.text.strip() and not result.rejected:
                self.vault.append_transcript_line(
                    dt=seg.started_at,
                    time_str=seg.started_at.strftime("%H:%M"),
                    speaker=seg.speaker_label,
                    text=result.text,
                )

        snippet = "\n".join(transcript_lines[:15])
        if snippet:
            await self._maybe_ai_meeting_title(session_id, snippet)

        await self.finalize_session(session_id)

    async def _maybe_ai_meeting_title(self, session_id: int, snippet: str) -> None:
        from core.audio.teams_title import is_generic_teams_title
        from core.db.models import TitleSource

        with get_session() as db:
            session = db.get(Session, session_id)
            if not session:
                return
            if session.title_source == TitleSource.MANUAL.value:
                return
            if (
                session.title_source == TitleSource.TEAMS_WINDOW.value
                and not is_generic_teams_title(session.title)
            ):
                return
            if (
                session.title
                and session.title_source == TitleSource.AI.value
                and not is_generic_teams_title(session.title)
            ):
                return
        try:
            title = await run_ml(self.summarizer.generate_meeting_title, snippet)
            with get_session() as db:
                session = db.get(Session, session_id)
                if session:
                    session.title = title
                    session.title_source = TitleSource.AI.value
        except Exception as e:
            logger.warning("AI meeting title failed for %s: %s", session_id, e)

    async def try_finalize_session(self, session_id: int) -> None:
        """Oturum kapandıysa ve tüm chunk'lar transcript edildiyse özet üret."""
        with get_session() as db:
            session = db.get(Session, session_id)
            if not session or session.summary:
                return
            if session.status not in (SessionStatus.IDLE.value,):
                return
            chunks = (
                db.query(Chunk)
                .filter(Chunk.session_id == session_id, Chunk.channel != "meeting")
                .all()
            )
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
                .filter(Chunk.session_id == session_id, Chunk.channel != "meeting")
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

        try:
            summary = await run_ml(self.summarizer.summarize_session, lines)
        finally:
            await run_ml(self.summarizer.unload)

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
