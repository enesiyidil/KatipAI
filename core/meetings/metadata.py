"""Meeting session metadata helpers."""

from __future__ import annotations

import logging

from core.audio.teams_title import (
    datetime_fallback_title,
    is_generic_teams_title,
    read_teams_window_title,
)
from core.db.database import get_session
from core.db.models import MeetingProcessingState, Session, TitleSource

logger = logging.getLogger(__name__)


def set_meeting_recording(session_id: int) -> None:
    with get_session() as db:
        session = db.get(Session, session_id)
        if not session:
            return
        session.processing_state = MeetingProcessingState.RECORDING.value
        snapshot = read_teams_window_title()
        if snapshot and not session.title:
            session.title = snapshot.title
            session.title_source = TitleSource.TEAMS_WINDOW.value
            session.participants_hint = snapshot.participants_hint


def apply_teams_title_on_end(session_id: int, duration_ms: int) -> None:
    """Update duration/state; only replace title if current is empty or generic."""
    with get_session() as db:
        session = db.get(Session, session_id)
        if not session:
            return
        session.duration_ms = duration_ms
        session.processing_state = MeetingProcessingState.PROCESSING.value

        current_is_generic = is_generic_teams_title(session.title)
        can_overwrite = (
            not session.title
            or current_is_generic
            or session.title_source
            in (TitleSource.DATETIME.value, None, "")
        )
        # Never overwrite a manual title
        if session.title_source == TitleSource.MANUAL.value:
            can_overwrite = False

        snapshot = read_teams_window_title()
        if snapshot and can_overwrite:
            session.title = snapshot.title
            session.title_source = TitleSource.TEAMS_WINDOW.value
            if snapshot.participants_hint:
                session.participants_hint = snapshot.participants_hint
            logger.info("Meeting %s title from Teams: %s", session_id, snapshot.title)
        elif not session.title:
            fallback = datetime_fallback_title(session.started_at)
            session.title = fallback.title
            session.title_source = TitleSource.DATETIME.value
            logger.info("Meeting %s title datetime fallback", session_id)
        else:
            logger.info(
                "Meeting %s keeping existing title: %s (source=%s)",
                session_id,
                session.title,
                session.title_source,
            )


def apply_ai_title_if_needed(session_id: int, snippet: str, generate_fn) -> None:
    with get_session() as db:
        session = db.get(Session, session_id)
        if not session:
            return
        if session.title_source == TitleSource.MANUAL.value:
            return
        # Allow AI override for datetime or generic Teams UI titles
        if session.title_source == TitleSource.TEAMS_WINDOW.value and not is_generic_teams_title(
            session.title
        ):
            return
        if (
            session.title
            and session.title_source == TitleSource.AI.value
            and not is_generic_teams_title(session.title)
        ):
            return
    try:
        title = generate_fn(snippet)
        with get_session() as db:
            session = db.get(Session, session_id)
            if session:
                session.title = title
                session.title_source = TitleSource.AI.value
    except Exception as e:
        logger.warning("AI meeting title failed for %s: %s", session_id, e)


def set_meeting_ready(session_id: int) -> None:
    with get_session() as db:
        session = db.get(Session, session_id)
        if session:
            session.processing_state = MeetingProcessingState.READY.value
            session.processing_error = None


def set_meeting_failed(session_id: int, error: str) -> None:
    with get_session() as db:
        session = db.get(Session, session_id)
        if session:
            session.processing_state = MeetingProcessingState.FAILED.value
            session.processing_error = (error or "unknown")[:2000]
