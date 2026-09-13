from collections.abc import Generator
from contextlib import contextmanager

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from core.config import settings
from core.db.models import Base

_engine = None
_SessionLocal = None


def reset_engine() -> None:
    """Drop the process-wide engine so tests can point at a temp data_dir."""
    global _engine, _SessionLocal
    if _engine is not None:
        _engine.dispose()
    _engine = None
    _SessionLocal = None


def _ensure_engine():
    global _engine, _SessionLocal
    if _engine is None:
        settings.data_dir.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{settings.db_path}", connect_args={"check_same_thread": False})
        _SessionLocal = sessionmaker(bind=_engine, autoflush=False, autocommit=False)
    return _engine, _SessionLocal


def init_db() -> None:
    from core.db.migrate import run_migrations
    from core.db.models import Speaker

    engine, _ = _ensure_engine()
    Base.metadata.create_all(bind=engine)
    run_migrations()
    _, session_factory = _ensure_engine()
    session = session_factory()
    try:
        defaults = [
            ("ben", "Ben", "mic"),
            ("diger", "Diğer", "system"),
            ("bilinmeyen", "Bilinmeyen", "mic"),
        ]
        for label, display_name, hint in defaults:
            if not session.query(Speaker).filter_by(label=label).first():
                session.add(Speaker(label=label, display_name=display_name, channel_hint=hint))
        session.commit()
    finally:
        session.close()


@contextmanager
def get_session() -> Generator[Session, None, None]:
    _, session_factory = _ensure_engine()
    session = session_factory()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
