from fastapi import APIRouter
from pydantic import BaseModel

from core.db.database import get_session
from core.db.models import Jargon

router = APIRouter()


class JargonIn(BaseModel):
    term: str
    aliases: str | None = None
    category: str | None = None


@router.get("/jargon")
def list_jargon():
    with get_session() as db:
        rows = db.query(Jargon).order_by(Jargon.term).all()
        return [{"id": j.id, "term": j.term, "aliases": j.aliases, "category": j.category} for j in rows]


@router.post("/jargon")
def add_jargon(body: JargonIn):
    with get_session() as db:
        entry = Jargon(term=body.term, aliases=body.aliases, category=body.category)
        db.add(entry)
        db.flush()
        return {"id": entry.id, "term": entry.term}


@router.delete("/jargon/{jargon_id}")
def delete_jargon(jargon_id: int):
    with get_session() as db:
        entry = db.get(Jargon, jargon_id)
        if entry:
            db.delete(entry)
    return {"ok": True}
