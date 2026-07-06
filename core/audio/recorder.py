import asyncio
import logging
import threading
from datetime import datetime, timezone
from typing import Callable

import numpy as np

from core.audio.app_sources import source_app_label
from core.audio.capture import MicrophoneCapture, SystemAudioCapture, SAMPLE_RATE
from core.audio.chunker import AudioChunker, Channel, ChunkResult
from core.audio.dedup import EchoDedupEngine
from core.audio.voice_matcher import VoiceMatcher
from core.config import settings
from core.db.database import get_session
from core.db.models import AppState, Chunk, RecordingMode, Session, SessionStatus

logger = logging.getLogger(__name__)


def _capture_error_message(code: str | None) -> str:
    if code == "no_sources":
        return "Uygulama seçilmedi — sistem sesi dinlenmiyor"
    if code == "permission_denied":
        return (
            "Ekran/Sistem Sesi Kaydı izni yok — Ayarlar → İzinler → "
            "«Sistem sesi izni iste» veya KatipAI Audio.app'ı «Yalnızca Sistem Sesi Kaydı» listesine ekleyin"
        )
    if code == "helper_error":
        return "Sistem sesi helper hatası — logları kontrol edin"
    if code == "process_exited":
        return "Sistem sesi başlatılamadı — izin ve uygulama seçimini kontrol edin"
    return "Sistem sesi başlatılamadı"


class RecordingService:
    """Orchestrates dual-channel capture, VAD, and chunk persistence."""

    def __init__(
        self,
        on_state_change: Callable | None = None,
        on_mode_change: Callable | None = None,
        on_chunk_saved: Callable | None = None,
        on_session_end: Callable | None = None,
    ):
        self.on_state_change = on_state_change
        self.on_mode_change = on_mode_change
        self.on_chunk_saved = on_chunk_saved
        self.on_session_end = on_session_end
        self._mode = RecordingMode.NORMAL
        self._app_state = AppState.IDLE
        self._session_id: int | None = None
        self._chunker: AudioChunker | None = None
        self._mic: MicrophoneCapture | None = None
        self._system: SystemAudioCapture | None = None
        self._echo_dedup = EchoDedupEngine(sample_rate=SAMPLE_RATE)
        self._voice_matcher = VoiceMatcher()
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
        if self._app_state == state:
            return
        self._app_state = state
        if self.on_state_change and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_state_change(state), self._loop)

    def _notify_mode(self) -> None:
        if self.on_mode_change and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_mode_change(self._mode), self._loop)

    def _should_allow_mic(self) -> bool:
        if self._mode != RecordingMode.MEETING:
            return True
        if settings.voice_filter_mode == "off":
            return False
        return self._voice_matcher.is_enrolled()

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
                source_app=result.source_app,
                is_echo=result.is_echo,
                echo_score=result.echo_score,
                voice_match_score=result.voice_match_score,
                skip_reason=result.skip_reason,
            )
            db.add(chunk)
            db.flush()
            chunk_id = chunk.id
        logger.info(
            "Chunk saved: %s %s (%dms) skip=%s echo=%.2f voice=%s",
            result.channel.value,
            chunk_id,
            result.duration_ms,
            result.skip_reason,
            result.echo_score or 0,
            result.voice_match_score,
        )
        self._set_state(AppState.PROCESSING)
        if self.on_chunk_saved and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_chunk_saved(chunk_id), self._loop)

    def _on_session_idle(self) -> None:
        logger.info("Session idle, ending")
        self._end_session()

    def _handle_frame(self, channel: Channel, frame: np.ndarray) -> None:
        if self._paused or self._mode == RecordingMode.SENSITIVE:
            return
        if channel == Channel.MIC:
            if not self._should_allow_mic():
                return
            self._echo_dedup.push_mic(frame)
        if channel == Channel.SYSTEM:
            self._echo_dedup.push_system(frame)
        if self._mode == RecordingMode.SILENT and channel == Channel.SYSTEM:
            return

        with self._lock:
            if self._chunker is None:
                session_id = self._ensure_session()
                self._chunker = AudioChunker(
                    session_id=session_id,
                    on_chunk=self._on_chunk,
                    on_session_idle=self._on_session_idle,
                    echo_dedup=self._echo_dedup,
                    voice_matcher=self._voice_matcher,
                    source_app=source_app_label(),
                )
            self._chunker.process_frame(channel, frame)
            if self._app_state not in (AppState.RECORDING, AppState.PROCESSING):
                self._set_state(AppState.LISTENING)

    @property
    def is_running(self) -> bool:
        return self._running

    def start(self) -> bool:
        if self._running:
            return False
        self._running = True
        self._paused = False
        settings.audio_dir.mkdir(parents=True, exist_ok=True)

        if settings.mic_enabled:
            self._mic = MicrophoneCapture(lambda f: self._handle_frame(Channel.MIC, f))
            self._mic.start()
        if settings.system_enabled:
            self._system = SystemAudioCapture(lambda f: self._handle_frame(Channel.SYSTEM, f))
            if not self._system.start():
                logger.warning(
                    "System audio capture not active at start: %s",
                    _capture_error_message(self._system.last_error),
                )

        if self._mode == RecordingMode.SENSITIVE:
            self._set_state(AppState.SENSITIVE)
        else:
            self._set_state(AppState.LISTENING)
        logger.info("Recording service started")
        return True

    def stop(self) -> bool:
        if not self._running:
            return False
        self._running = False
        self._paused = False
        if self._chunker:
            self._chunker.stop()
            self._chunker = None
        if self._mic:
            self._mic.stop()
            self._mic = None
        if self._system:
            self._system.stop()
            self._system = None
        self._end_session()
        self._set_state(AppState.IDLE)
        logger.info("Recording service stopped")
        return True

    def restart_system_capture(self) -> dict:
        """Hot-restart ScreenCaptureKit helper after source selection changes."""
        status = self.get_system_capture_status()

        if not self._running:
            status["restarted"] = False
            status["message"] = "Dinleme kapalı — ayar kaydedildi, başlatınca uygulanır"
            return status

        if not settings.system_enabled:
            if self._system:
                self._system.stop()
                self._system = None
            status["restarted"] = False
            status["message"] = "Sistem sesi devre dışı (Ayarlar → Kayıt)"
            status.update(self.get_system_capture_status())
            return status

        self._echo_dedup.clear_system()
        if self._system:
            self._system.stop()
        self._system = SystemAudioCapture(lambda f: self._handle_frame(Channel.SYSTEM, f))
        started = self._system.start()
        if self._chunker is not None:
            self._chunker._source_app = source_app_label()

        status["restarted"] = True
        status.update(self.get_system_capture_status())
        if started:
            status["message"] = "Sistem sesi yeniden başlatıldı"
            logger.info("System capture restarted (%s)", status.get("capture_mode"))
        else:
            err = self._system.last_error if self._system else "unknown"
            status["message"] = _capture_error_message(err)
            logger.warning("System capture restart failed: %s", err)
        return status

    def get_system_capture_status(self) -> dict:
        from core.audio.app_sources import capture_config_snapshot

        snap = capture_config_snapshot()
        active = bool(self._system and self._system.is_active)
        last_error = self._system.last_error if self._system else None
        return {
            **snap,
            "listening": self._running,
            "system_enabled": settings.system_enabled,
            "system_capture_active": active,
            "last_error": last_error,
        }

    def restart_mic_capture(self) -> None:
        if not self._running or not settings.mic_enabled:
            return
        if self._mic:
            self._mic.stop()
        self._mic = MicrophoneCapture(lambda f: self._handle_frame(Channel.MIC, f))
        self._mic.start()
        logger.info("Microphone capture restarted")

    def restart_all_capture(self) -> None:
        if not self._running:
            self.start()
            return
        self.restart_mic_capture()
        self.restart_system_capture()

    def pause(self) -> bool:
        if not self._running or self._paused:
            return False
        if self._mode == RecordingMode.SENSITIVE:
            return False
        self._paused = True
        self._set_state(AppState.PAUSED)
        return True

    def resume(self) -> bool:
        if not self._running or not self._paused:
            return False
        self._paused = False
        if self._mode == RecordingMode.SENSITIVE:
            self._set_state(AppState.SENSITIVE)
        else:
            self._set_state(AppState.LISTENING)
        return True

    def set_mode(self, mode: RecordingMode) -> None:
        self._mode = mode
        self._notify_mode()
        if mode == RecordingMode.SENSITIVE:
            if self._running:
                self._set_state(AppState.SENSITIVE)
        elif self._running:
            if self._paused:
                self._set_state(AppState.PAUSED)
            else:
                self._set_state(AppState.LISTENING)

    def on_processing_complete(self) -> None:
        if not self._running or self._paused:
            return
        if self._mode == RecordingMode.SENSITIVE:
            return
        if self._app_state == AppState.PROCESSING:
            self._set_state(AppState.LISTENING)

    def manual_record_start(self) -> None:
        self._mode = RecordingMode.MANUAL
        self._notify_mode()
        self._ensure_session()
        self._set_state(AppState.RECORDING)

    def delete_last_chunk(self) -> int | None:
        with get_session() as db:
            chunk = db.query(Chunk).order_by(Chunk.id.desc()).first()
            if not chunk:
                return None
            from pathlib import Path

            chunk_id = chunk.id
            Path(chunk.audio_path).unlink(missing_ok=True)
            db.delete(chunk)
        return chunk_id

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
