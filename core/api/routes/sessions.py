from datetime import date

from fastapi import APIRouter
from pydantic import BaseModel

from core.db.database import get_session
from core.db.models import Chunk, Session, Transcript

router = APIRouter()


class SessionOut(BaseModel):
    id: int
    started_at: str
    ended_at: str | None
    mode: str
    status: str
    summary: str | None
    vault_file: str | None

    class Config:
        from_attributes = True


@router.get("/sessions")
def list_sessions(limit: int = 50):
    with get_session() as db:
        rows = db.query(Session).order_by(Session.started_at.desc()).limit(limit).all()
        return [
            SessionOut(
                id=s.id,
                started_at=s.started_at.isoformat(),
                ended_at=s.ended_at.isoformat() if s.ended_at else None,
                mode=s.mode,
                status=s.status,
                summary=s.summary,
                vault_file=s.vault_file,
            )
            for s in rows
        ]


@router.get("/sessions/today")
def today_sessions():
    today = date.today()
    with get_session() as db:
        rows = (
            db.query(Session)
            .filter(Session.started_at >= f"{today.isoformat()} 00:00:00")
            .order_by(Session.started_at.desc())
            .all()
        )
        return [{"id": s.id, "started_at": s.started_at.isoformat(), "summary": s.summary} for s in rows]


@router.get("/sessions/{session_id}")
def get_session_detail(session_id: int):
    with get_session() as db:
        session = db.get(Session, session_id)
        if not session:
            return {"error": "not found"}
        chunks = db.query(Chunk).filter(Chunk.session_id == session_id).order_by(Chunk.started_at).all()
        return {
            "session": {
                "id": session.id,
                "started_at": session.started_at.isoformat(),
                "summary": session.summary,
                "vault_file": session.vault_file,
            },
            "chunks": [
                {
                    "id": c.id,
                    "channel": c.channel,
                    "speaker": c.speaker_label,
                    "started_at": c.started_at.isoformat(),
                    "duration_ms": c.duration_ms,
                    "transcript": {
                        "text": c.transcript.text,
                        "confidence": c.transcript.confidence,
                        "needs_review": c.transcript.needs_review,
                    }
                    if c.transcript
                    else None,
                }
                for c in chunks
            ],
        }
