from datetime import date, datetime

from fastapi import APIRouter
from sqlalchemy import desc

from core import services
from core.audio.app_sources import active_capture_display_label
from core.db.database import get_session
from core.db.models import Chunk, Session, Transcript

router = APIRouter()


@router.get("/timeline/today")
def timeline_today():
    today = date.today()
    with get_session() as db:
        chunks = (
            db.query(Chunk)
            .join(Session)
            .filter(Session.started_at >= datetime.combine(today, datetime.min.time()))
            .order_by(Chunk.started_at.desc())
            .limit(200)
            .all()
        )
        items = []
        for c in chunks:
            t = c.transcript
            src_display = None
            if c.channel == "system":
                src_display = active_capture_display_label() or c.source_app
            items.append({
                "id": c.id,
                "session_id": c.session_id,
                "channel": c.channel,
                "speaker": c.speaker_label,
                "started_at": c.started_at.isoformat(),
                "time": c.started_at.strftime("%H:%M:%S"),
                "duration_ms": c.duration_ms,
                "text": t.text if t else None,
                "confidence": t.confidence if t else None,
                "needs_review": t.needs_review if t else False,
                "processing_error": t.processing_error if t else None,
                "transcript_id": t.id if t else None,
                "skip_reason": c.skip_reason,
                "is_echo": c.is_echo,
                "echo_score": c.echo_score,
                "voice_match_score": c.voice_match_score,
                "source_app": c.source_app,
                "source_app_display": src_display,
            })
    return {"date": today.isoformat(), "items": items}


@router.get("/stats/today")
def stats_today():
    today = date.today()
    with get_session() as db:
        sessions = (
            db.query(Session)
            .filter(Session.started_at >= datetime.combine(today, datetime.min.time()))
            .count()
        )
        chunks = (
            db.query(Chunk)
            .join(Session)
            .filter(Session.started_at >= datetime.combine(today, datetime.min.time()))
            .count()
        )
        transcripts = (
            db.query(Transcript)
            .join(Chunk)
            .join(Session)
            .filter(Session.started_at >= datetime.combine(today, datetime.min.time()))
            .count()
        )
        review = db.query(Transcript).filter(Transcript.needs_review.is_(True)).count()
    svc = services.recording_service
    return {
        "sessions": sessions,
        "chunks": chunks,
        "transcripts": transcripts,
        "review_pending": review,
        "state": svc.app_state.value if svc else "idle",
        "mode": svc.mode.value if svc else "normal",
    }
