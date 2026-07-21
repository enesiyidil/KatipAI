from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.config import settings
from core.db.database import get_session
from core.db.models import Chunk, RecordingMode, Session, TitleSource

router = APIRouter()

SUMMARY_SNIPPET_LEN = 200


class MeetingPatch(BaseModel):
    title: str


def _format_duration(duration_ms: int | None) -> str | None:
    if not duration_ms:
        return None
    total_sec = duration_ms // 1000
    minutes, seconds = divmod(total_sec, 60)
    if minutes >= 60:
        hours, minutes = divmod(minutes, 60)
        return f"{hours}s {minutes}dk"
    return f"{minutes}dk {seconds}sn"


def _summary_snippet(summary: str | None) -> str | None:
    if not summary:
        return None
    text = summary.strip()
    if len(text) <= SUMMARY_SNIPPET_LEN:
        return text
    return text[:SUMMARY_SNIPPET_LEN].rstrip() + "…"


def _meeting_list_item(session: Session) -> dict:
    return {
        "id": session.id,
        "title": session.title or f"Toplantı #{session.id}",
        "title_source": session.title_source,
        "started_at": session.started_at.isoformat(),
        "ended_at": session.ended_at.isoformat() if session.ended_at else None,
        "duration_ms": session.duration_ms,
        "duration_label": _format_duration(session.duration_ms),
        "participants_hint": session.participants_hint,
        "processing_state": session.processing_state or "processing",
        "summary_snippet": _summary_snippet(session.summary),
        "has_summary": bool(session.summary),
    }


@router.get("/meetings")
def list_meetings(limit: int = 100):
    with get_session() as db:
        rows = (
            db.query(Session)
            .filter(Session.mode == RecordingMode.MEETING.value)
            .order_by(Session.started_at.desc())
            .limit(limit)
            .all()
        )
        return [_meeting_list_item(s) for s in rows]


@router.get("/meetings/{meeting_id}")
def get_meeting(meeting_id: int):
    with get_session() as db:
        session = db.get(Session, meeting_id)
        if not session or session.mode != RecordingMode.MEETING.value:
            raise HTTPException(status_code=404, detail="Toplantı bulunamadı")

        chunks = (
            db.query(Chunk)
            .filter(Chunk.session_id == meeting_id, Chunk.channel != "meeting")
            .order_by(Chunk.started_at)
            .all()
        )

        stereo_path = None
        master = (
            db.query(Chunk)
            .filter(Chunk.session_id == meeting_id, Chunk.channel == "meeting")
            .order_by(Chunk.id.desc())
            .first()
        )
        if master:
            stereo_path = master.audio_path

        transcript = []
        for chunk in chunks:
            text = None
            confidence = None
            needs_review = False
            if chunk.transcript:
                text = chunk.transcript.text
                confidence = chunk.transcript.confidence
                needs_review = chunk.transcript.needs_review
            transcript.append(
                {
                    "chunk_id": chunk.id,
                    "channel": chunk.channel,
                    "speaker": chunk.speaker_label,
                    "started_at": chunk.started_at.isoformat(),
                    "time": chunk.started_at.strftime("%H:%M"),
                    "duration_ms": chunk.duration_ms,
                    "text": text,
                    "confidence": confidence,
                    "needs_review": needs_review,
                }
            )

        return {
            "id": session.id,
            "title": session.title or f"Toplantı #{session.id}",
            "title_source": session.title_source,
            "started_at": session.started_at.isoformat(),
            "ended_at": session.ended_at.isoformat() if session.ended_at else None,
            "duration_ms": session.duration_ms,
            "duration_label": _format_duration(session.duration_ms),
            "participants_hint": session.participants_hint,
            "processing_state": session.processing_state or "processing",
            "processing_error": session.processing_error,
            "summary": session.summary,
            "stereo_path": stereo_path,
            "transcript": transcript,
        }


@router.patch("/meetings/{meeting_id}")
def patch_meeting(meeting_id: int, body: MeetingPatch):
    title = body.title.strip()
    if not title:
        raise HTTPException(status_code=400, detail="Başlık boş olamaz")
    with get_session() as db:
        session = db.get(Session, meeting_id)
        if not session or session.mode != RecordingMode.MEETING.value:
            raise HTTPException(status_code=404, detail="Toplantı bulunamadı")
        session.title = title[:512]
        session.title_source = TitleSource.MANUAL.value
        return _meeting_list_item(session)


@router.get("/meetings/{meeting_id}/audio")
def get_meeting_audio(meeting_id: int):
    from pathlib import Path

    from fastapi.responses import FileResponse

    with get_session() as db:
        session = db.get(Session, meeting_id)
        if not session or session.mode != RecordingMode.MEETING.value:
            raise HTTPException(status_code=404, detail="Toplantı bulunamadı")
        master = (
            db.query(Chunk)
            .filter(Chunk.session_id == meeting_id, Chunk.channel == "meeting")
            .order_by(Chunk.id.desc())
            .first()
        )
        if not master or not master.audio_path:
            raise HTTPException(status_code=404, detail="Stereo kayıt yok")
        path = Path(master.audio_path).resolve()
        audio_root = settings.audio_dir.resolve()
        try:
            path.relative_to(audio_root)
        except ValueError:
            raise HTTPException(status_code=403, detail="Invalid audio path")
        if not path.exists():
            raise HTTPException(status_code=404, detail="Audio file missing")
        return FileResponse(path, media_type="audio/wav", filename=path.name)


@router.post("/meetings/{meeting_id}/reprocess")
def reprocess_meeting(meeting_id: int):
    from core.api.app import schedule_meeting_reprocess
    from core.db.models import MeetingProcessingState

    with get_session() as db:
        session = db.get(Session, meeting_id)
        if not session or session.mode != RecordingMode.MEETING.value:
            raise HTTPException(status_code=404, detail="Toplantı bulunamadı")
        session.processing_state = MeetingProcessingState.PROCESSING.value
        session.processing_error = None
        session.summary = None
        chunks = (
            db.query(Chunk)
            .filter(Chunk.session_id == meeting_id, Chunk.channel != "meeting")
            .all()
        )
        for chunk in chunks:
            db.delete(chunk)

    scheduled = schedule_meeting_reprocess(meeting_id)
    if not scheduled:
        raise HTTPException(status_code=503, detail="Pipeline kullanılamıyor")
    return {"ok": True, "message": "Toplantı yeniden işleniyor", "session_id": meeting_id}
