"""Continuous dual-channel recording for meeting mode — processed once at end."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import scipy.io.wavfile as wavfile

from core.config import settings

logger = logging.getLogger(__name__)

SAMPLE_RATE = settings.sample_rate


@dataclass
class MeetingRecordingResult:
    session_id: int
    started_at: datetime
    ended_at: datetime
    stereo_path: Path
    mic_path: Path
    system_path: Path | None
    duration_ms: int


@dataclass
class MeetingRecorder:
    session_id: int
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    _mic_frames: list[np.ndarray] = field(default_factory=list)
    _system_frames: list[np.ndarray] = field(default_factory=list)

    @property
    def output_dir(self) -> Path:
        path = settings.audio_dir / str(self.session_id)
        path.mkdir(parents=True, exist_ok=True)
        return path

    def push_mic(self, frame: np.ndarray) -> None:
        self._mic_frames.append(frame.astype(np.float32))

    def push_system(self, frame: np.ndarray) -> None:
        self._system_frames.append(frame.astype(np.float32))

    @property
    def duration_ms(self) -> int:
        mic_samples = sum(len(f) for f in self._mic_frames)
        sys_samples = sum(len(f) for f in self._system_frames)
        samples = max(mic_samples, sys_samples)
        return int(samples / SAMPLE_RATE * 1000)

    def finalize(self) -> MeetingRecordingResult | None:
        ended_at = datetime.now(timezone.utc)
        mic = np.concatenate(self._mic_frames) if self._mic_frames else np.array([], dtype=np.float32)
        system = (
            np.concatenate(self._system_frames) if self._system_frames else np.array([], dtype=np.float32)
        )

        if mic.size == 0 and system.size == 0:
            logger.warning("Meeting %s: no audio captured", self.session_id)
            return None

        if mic.size == 0:
            mic = np.zeros_like(system)
        elif system.size == 0:
            system = np.zeros_like(mic)
        elif len(mic) != len(system):
            target = max(len(mic), len(system))
            if len(mic) < target:
                mic = np.pad(mic, (0, target - len(mic)))
            if len(system) < target:
                system = np.pad(system, (0, target - len(system)))

        duration_ms = int(len(mic) / SAMPLE_RATE * 1000)
        if duration_ms < 500:
            logger.info("Meeting %s: too short (%dms), skipping save", self.session_id, duration_ms)
            return None

        out = self.output_dir
        mic_path = out / "meeting_mic.wav"
        system_path = out / "meeting_system.wav"
        stereo_path = out / "meeting_stereo.wav"

        _write_wav(mic_path, mic)
        has_system = bool(self._system_frames)
        if has_system:
            _write_wav(system_path, system)
        stereo = np.stack([mic, system if has_system else np.zeros_like(mic)], axis=1)
        _write_wav_stereo(stereo_path, stereo)

        logger.info(
            "Meeting %s saved: %dms mic=%d system=%d samples",
            self.session_id,
            duration_ms,
            len(mic),
            len(system),
        )
        return MeetingRecordingResult(
            session_id=self.session_id,
            started_at=self.started_at,
            ended_at=ended_at,
            stereo_path=stereo_path,
            mic_path=mic_path,
            system_path=system_path if has_system else None,
            duration_ms=duration_ms,
        )


def _write_wav(path: Path, audio: np.ndarray) -> None:
    clipped = np.clip(audio, -1.0, 1.0)
    wavfile.write(path, SAMPLE_RATE, (clipped * 32767).astype(np.int16))


def _write_wav_stereo(path: Path, audio: np.ndarray) -> None:
    clipped = np.clip(audio, -1.0, 1.0)
    wavfile.write(path, SAMPLE_RATE, (clipped * 32767).astype(np.int16))
