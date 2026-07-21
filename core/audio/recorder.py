import asyncio
import logging
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

import numpy as np

from core.audio.app_sources import capture_config_snapshot, source_app_label
from core.audio.capture import MicrophoneCapture, SystemAudioCapture, SAMPLE_RATE
from core.audio.chunker import AudioChunker, Channel, ChunkResult
from core.audio.dedup import EchoDedupEngine
from core.audio.meeting_recorder import MeetingRecorder
from core.audio.voice_matcher import VoiceMatcher
from core.config import settings
from core.db.database import get_session
from core.db.models import AppState, Chunk, RecordingMode, Session, SessionStatus
from core.meetings.metadata import apply_teams_title_on_end, set_meeting_recording

logger = logging.getLogger(__name__)


def _capture_error_message(code: str | None) -> str:
    if code == "no_sources":
        return "Uygulama seçilmedi — Teams/Chrome seçin"
    if code == "permission_denied":
        return (
            "Ekran/Sistem Sesi Kaydı izni yok — Ayarlar → İzinler → "
            "«Sistem sesi izni iste»"
        )
    if code == "helper_error":
        return "Sistem sesi helper hatası — logları kontrol edin"
    if code == "process_exited":
        return "Sistem sesi başlatılamadı — izin ve uygulama seçimini kontrol edin"
    return "Sistem sesi başlatılamadı"


class RecordingService:
    """Normal mod: yalnızca mikrofon, canlı chunk STT. Toplantı modu: sürekli kayıt, bitince toplu STT."""

    def __init__(
        self,
        on_state_change: Callable | None = None,
        on_mode_change: Callable | None = None,
        on_chunk_saved: Callable | None = None,
        on_session_end: Callable | None = None,
        on_meeting_end: Callable | None = None,
    ):
        self.on_state_change = on_state_change
        self.on_mode_change = on_mode_change
        self.on_chunk_saved = on_chunk_saved
        self.on_session_end = on_session_end
        self.on_meeting_end = on_meeting_end
        self._mode = RecordingMode.NORMAL
        self._app_state = AppState.IDLE
        self._session_id: int | None = None
        self._chunker: AudioChunker | None = None
        self._meeting: MeetingRecorder | None = None
        self._mic: MicrophoneCapture | None = None
        self._system: SystemAudioCapture | None = None
        self._echo_dedup = EchoDedupEngine(sample_rate=SAMPLE_RATE)
        self._voice_matcher = VoiceMatcher()
        self._running = False
        self._paused = False
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None
        self._system_retry_at = 0.0
        self._system_retry_count = 0

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

    def _uses_system_audio(self) -> bool:
        return self._mode == RecordingMode.MEETING and settings.system_enabled

    def _uses_mic(self) -> bool:
        if self._mode == RecordingMode.SENSITIVE:
            return False
        return settings.mic_enabled

    def get_mic_activity_hint(self) -> dict:
        if not self._running or not self._mic:
            return {"active": False, "level": 0.0, "speaking": False}
        level = float(self._mic.current_level)
        return {
            "active": True,
            "level": round(level, 4),
            "speaking": level >= settings.min_audio_rms,
        }

    def get_capture_warning(self) -> str | None:
        if not self._running or not self._uses_system_audio():
            return None
        if self._system and self._system.is_active:
            return None
        err = self._system.last_error if self._system else "not_started"
        msg = _capture_error_message(err)
        snap = capture_config_snapshot()
        missing = snap.get("missing_bundle_ids") or []
        if missing:
            msg = f"{msg} (kapalı: {', '.join(missing)})"
        return f"Toplantı modu — sistem sesi gerekli: {msg}. Mikrofon kaydı devam ediyor."

    def _on_system_capture_failed(self) -> None:
        if not self._running or not self._uses_system_audio():
            return
        now = time.time()
        if now - self._system_retry_at < 8:
            return
        if self._system and self._system.is_active:
            return
        self._system_retry_at = now
        if self._system_retry_count >= 3:
            logger.error("System capture failed repeatedly — Ayarlar → Kayıt yenile")
            return
        self._system_retry_count += 1
        logger.info("System capture auto-retry %s/3", self._system_retry_count)
        self.restart_system_capture()

    def _ensure_session(self) -> int:
        if self._session_id is not None:
            return self._session_id
        with get_session() as db:
            session = Session(mode=self._mode.value, status=SessionStatus.ACTIVE.value)
            db.add(session)
            db.flush()
            self._session_id = session.id
        if self._mode == RecordingMode.MEETING:
            set_meeting_recording(self._session_id)
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
            "Chunk saved: %s %s (%dms) skip=%s",
            result.channel.value,
            chunk_id,
            result.duration_ms,
            result.skip_reason,
        )
        self._set_state(AppState.PROCESSING)
        if self.on_chunk_saved and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_chunk_saved(chunk_id), self._loop)

    def _on_session_idle(self) -> None:
        if self._mode == RecordingMode.MEETING:
            return
        logger.info("Session idle, ending")
        self._end_session()

    def _handle_frame(self, channel: Channel, frame: np.ndarray) -> None:
        if self._paused or self._mode == RecordingMode.SENSITIVE:
            return

        if self._mode == RecordingMode.MEETING:
            session_id = self._ensure_session()
            with self._lock:
                if self._meeting is None:
                    self._meeting = MeetingRecorder(session_id=session_id)
                if channel == Channel.MIC:
                    self._meeting.push_mic(frame)
                else:
                    self._meeting.push_system(frame)
            self._set_state(AppState.RECORDING)
            return

        # Normal mod: yalnızca mikrofon
        if channel == Channel.SYSTEM:
            return
        if channel == Channel.MIC:
            if not self._uses_mic():
                return
            self._echo_dedup.push_mic(frame)

        with self._lock:
            if self._chunker is None:
                session_id = self._ensure_session()
                self._chunker = AudioChunker(
                    session_id=session_id,
                    on_chunk=self._on_chunk,
                    on_session_idle=self._on_session_idle,
                    echo_dedup=self._echo_dedup,
                    voice_matcher=self._voice_matcher,
                    source_app=None,
                )
            self._chunker.process_frame(channel, frame)
            if self._app_state not in (AppState.RECORDING, AppState.PROCESSING):
                self._set_state(AppState.LISTENING)

    @property
    def is_running(self) -> bool:
        return self._running

    def _start_mic(self) -> None:
        if not self._uses_mic():
            return
        self._mic = MicrophoneCapture(lambda f: self._handle_frame(Channel.MIC, f))
        self._mic.start()

    def _start_system(self) -> None:
        if not self._uses_system_audio():
            return
        self._system = SystemAudioCapture(
            lambda f: self._handle_frame(Channel.SYSTEM, f),
            on_failed=self._on_system_capture_failed,
        )
        if self._system.start():
            self._system_retry_count = 0
        else:
            logger.warning(
                "System audio not active: %s",
                _capture_error_message(self._system.last_error),
            )

    def start(self) -> bool:
        if self._running:
            return False
        self._running = True
        self._paused = False
        settings.audio_dir.mkdir(parents=True, exist_ok=True)
        self._start_mic()
        self._start_system()

        if self._mode == RecordingMode.SENSITIVE:
            self._set_state(AppState.SENSITIVE)
        else:
            self._set_state(AppState.LISTENING)
        logger.info("Recording service started (mode=%s)", self._mode.value)
        return True

    def stop(self) -> bool:
        if not self._running:
            return False
        self._running = False
        self._paused = False
        if self._mode == RecordingMode.MEETING:
            self._finalize_meeting()
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

    def _finalize_meeting(self) -> None:
        meeting = self._meeting
        self._meeting = None
        if not meeting:
            return
        result = meeting.finalize()
        if not result:
            return
        session_id = result.session_id
        apply_teams_title_on_end(session_id, result.duration_ms)
        with get_session() as db:
            chunk = Chunk(
                session_id=session_id,
                channel="meeting",
                speaker_label="Toplantı",
                audio_path=str(result.stereo_path),
                started_at=result.started_at,
                duration_ms=result.duration_ms,
            )
            db.add(chunk)
        self._set_state(AppState.PROCESSING)
        logger.info("Meeting %s queued for batch STT (%dms)", session_id, result.duration_ms)
        if self.on_meeting_end and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_meeting_end(session_id), self._loop)

    def restart_system_capture(self) -> dict:
        status = self.get_system_capture_status()

        if not self._running:
            status["restarted"] = False
            status["message"] = "Dinleme kapalı — ayar kaydedildi"
            return status

        if not self._uses_system_audio():
            if self._system:
                self._system.stop()
                self._system = None
            status["restarted"] = False
            status["message"] = "Normal mod — sistem sesi kapalı"
            status.update(self.get_system_capture_status())
            return status

        self._echo_dedup.clear_system()
        if self._system:
            self._system.stop()
        self._system = SystemAudioCapture(
            lambda f: self._handle_frame(Channel.SYSTEM, f),
            on_failed=self._on_system_capture_failed,
        )
        started = self._system.start()
        status["restarted"] = True
        status.update(self.get_system_capture_status())
        if started:
            self._system_retry_count = 0
            status["message"] = "Sistem sesi yeniden başlatıldı"
            logger.info("System capture restarted")
        else:
            err = self._system.last_error if self._system else "unknown"
            status["message"] = _capture_error_message(err)
            logger.warning("System capture restart failed: %s", err)
        return status

    def get_system_capture_status(self) -> dict:
        snap = capture_config_snapshot()
        active = bool(self._system and self._system.is_active)
        last_error = self._system.last_error if self._system else None
        return {
            **snap,
            "listening": self._running,
            "system_enabled": settings.system_enabled,
            "system_capture_active": active,
            "last_error": last_error,
            "capture_warning": self.get_capture_warning(),
            "mic_activity": self.get_mic_activity_hint(),
            "recording_mode": self._mode.value,
        }

    def restart_mic_capture(self) -> None:
        if not self._running or not self._uses_mic():
            if self._mic:
                self._mic.stop()
                self._mic = None
            return
        if self._mic:
            self._mic.stop()
        self._start_mic()
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
        elif self._mode == RecordingMode.MEETING:
            self._set_state(AppState.RECORDING)
        else:
            self._set_state(AppState.LISTENING)
        return True

    def set_mode(self, mode: RecordingMode) -> None:
        if mode == self._mode:
            return

        previous = self._mode
        if previous == RecordingMode.MEETING and self._running:
            self._finalize_meeting()
            self._end_session()

        self._mode = mode
        self._notify_mode()

        if not self._running:
            return

        if previous != RecordingMode.MEETING and mode == RecordingMode.MEETING:
            if self._chunker:
                self._chunker.stop()
                self._chunker = None
            self._end_session()
            self._meeting = None

        if self._uses_mic() and (not self._mic or not self._mic.is_active):
            self.restart_mic_capture()
        elif not self._uses_mic() and self._mic:
            self._mic.stop()
            self._mic = None

        if self._uses_system_audio():
            self.restart_system_capture()
        elif self._system:
            self._system.stop()
            self._system = None

        if mode == RecordingMode.SENSITIVE:
            self._set_state(AppState.SENSITIVE)
        elif self._paused:
            self._set_state(AppState.PAUSED)
        elif mode == RecordingMode.MEETING:
            self._set_state(AppState.RECORDING)
        else:
            self._set_state(AppState.LISTENING)

        logger.info("Mode changed: %s → %s", previous.value, mode.value)

    def on_processing_complete(self) -> None:
        if not self._running or self._paused:
            return
        if self._mode == RecordingMode.SENSITIVE:
            return
        if self._app_state == AppState.PROCESSING:
            if self._mode == RecordingMode.MEETING:
                self._set_state(AppState.RECORDING)
            else:
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
        self._meeting = None
        if self.on_session_end and self._loop:
            asyncio.run_coroutine_threadsafe(self.on_session_end(ended_id), self._loop)
        if self._running and not self._paused:
            if self._mode == RecordingMode.MEETING:
                self._set_state(AppState.RECORDING)
            else:
                self._set_state(AppState.LISTENING)
