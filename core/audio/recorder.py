import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Callable

import numpy as np

from core.audio.capture import MicrophoneCapture, SystemAudioCapture, SAMPLE_RATE
from core.audio.chunker import AudioChunker, Channel, ChunkResult
from core.audio.vad_processor import SileroVAD
from core.config import settings
from core.db.database import get_session
from core.db.models import AppState, Chunk, RecordingMode, Session, SessionStatus

logger = logging.getLogger(__name__)


class RecordingService:
    """Orchestrates dual-channel capture, VAD, and chunk persistence."""

    def __init__(
        self,
        on_state_change: Callable | None = None,
        on_chunk_saved: Callable | None = None,
        on_session_end: Callable | None = None,
    ):
        self.on_state_change = on_state_change
        self.on_chunk_saved = on_chunk_saved
        self.on_session_end = on_session_end
        self._mode = RecordingMode.NORMAL
        self._app_state = AppState.IDLE
        self._session_id: int | None = None
        self._chunker: AudioChunker | None = None
        self._vad = SileroVAD()
        self._mic: MicrophoneCapture | None = None
        self._system: SystemAudioCapture | None = None
        self._running = False
        self._paused = False
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    @property
    def app_state(self) -> AppState:
        return self._app_state

    @property
    def mode(self) -> RecordingMode:
        return self._mode

    @property
    def session_id(self) -> int | None:
        return self._session_id

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def _set_state(self, state: AppState) -> None:
        self._app_state = state
        if self.on_state_change and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_state_change(state), self._loop)

    def _ensure_session(self) -> int:
        if self._session_id is not None:
            return self._session_id
        with get_session() as db:
            session = Session(mode=self._mode.value, status=SessionStatus.ACTIVE.value)
            db.add(session)
            db.flush()
            self._session_id = session.id
        return self._session_id

    def _on_chunk(self, result: ChunkResult) -> None:
        session_id = self._ensure_session()
        with get_session() as db:
            chunk = Chunk(
                session_id=session_id,
                channel=result.channel.value,
                speaker_label=result.speaker_label,
                audio_path=str(result.audio_path),
                started_at=result.started_at,
                duration_ms=result.duration_ms,
            )
            db.add(chunk)
            db.flush()
            chunk_id = chunk.id
        logger.info("Chunk saved: %s %s (%dms)", result.channel.value, chunk_id, result.duration_ms)
        self._set_state(AppState.PROCESSING)
        if self.on_chunk_saved and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_chunk_saved(chunk_id), self._loop)

    def _on_session_idle(self) -> None:
        logger.info("Session idle, ending")
        self._end_session()

    def _handle_frame(self, channel: Channel, frame: np.ndarray) -> None:
        if self._paused or self._mode == RecordingMode.SENSITIVE:
            return
        if self._mode == RecordingMode.MEETING and channel == Channel.MIC:
            return
        if self._mode == RecordingMode.SILENT and channel == Channel.SYSTEM:
            return

        with self._lock:
            if self._chunker is None:
                session_id = self._ensure_session()
                self._chunker = AudioChunker(
                    session_id=session_id,
                    on_chunk=self._on_chunk,
                    on_session_idle=self._on_session_idle,
                    vad=self._vad,
                )
            self._chunker.process_frame(channel, frame)
            if self._app_state not in (AppState.RECORDING, AppState.PROCESSING):
                self._set_state(AppState.LISTENING)

    def start(self) -> None:
        if self._running:
            return
        self._running = True
        self._paused = False
        settings.audio_dir.mkdir(parents=True, exist_ok=True)

        if settings.mic_enabled:
            self._mic = MicrophoneCapture(lambda f: self._handle_frame(Channel.MIC, f))
            self._mic.start()
        if settings.system_enabled:
            self._system = SystemAudioCapture(lambda f: self._handle_frame(Channel.SYSTEM, f))
            self._system.start()

        self._set_state(AppState.LISTENING)
        logger.info("Recording service started")

    def stop(self) -> None:
        self._running = False
        if self._chunker:
            self._chunker.stop()
        if self._mic:
            self._mic.stop()
        if self._system:
            self._system.stop()
        self._end_session()
        self._set_state(AppState.IDLE)

    def pause(self) -> None:
        self._paused = True
        self._set_state(AppState.PAUSED)

    def resume(self) -> None:
        self._paused = False
        self._set_state(AppState.LISTENING)

    def set_mode(self, mode: RecordingMode) -> None:
        self._mode = mode
        if mode == RecordingMode.SENSITIVE:
            self._set_state(AppState.SENSITIVE)

    def manual_record_start(self) -> None:
        self._mode = RecordingMode.MANUAL
        self._ensure_session()
        self._set_state(AppState.RECORDING)

    def delete_last_chunk(self) -> bool:
        with get_session() as db:
            chunk = db.query(Chunk).order_by(Chunk.id.desc()).first()
            if not chunk:
                return False
            from pathlib import Path

            Path(chunk.audio_path).unlink(missing_ok=True)
            db.delete(chunk)
        return True

    def _end_session(self) -> None:
        if self._session_id is None:
            return
        ended_id = self._session_id
        with get_session() as db:
            session = db.get(Session, ended_id)
            if session:
                session.status = SessionStatus.IDLE.value
                session.ended_at = datetime.now(timezone.utc)
        self._session_id = None
        self._chunker = None
        if self.on_session_end and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_session_end(ended_id), self._loop)
        if self._running and not self._paused:
            self._set_state(AppState.LISTENING)
