"""Mic ↔ system echo detection via aligned ring buffers and cross-correlation."""

from __future__ import annotations

import numpy as np

from core.config import settings


class EchoDedupEngine:
    """Detect when mic audio is likely a speaker echo of system playback."""

    def __init__(self, sample_rate: int = 16000, window_seconds: float = 2.0):
        self.sample_rate = sample_rate
        self.max_samples = int(sample_rate * window_seconds)
        self._mic_buf = np.zeros(0, dtype=np.float32)
        self._sys_buf = np.zeros(0, dtype=np.float32)

    def push_mic(self, frame: np.ndarray) -> None:
        self._mic_buf = self._append(self._mic_buf, frame)

    def push_system(self, frame: np.ndarray) -> None:
        self._sys_buf = self._append(self._sys_buf, frame)

    def _append(self, buf: np.ndarray, frame: np.ndarray) -> np.ndarray:
        combined = np.concatenate([buf, frame.astype(np.float32)])
        if len(combined) > self.max_samples:
            combined = combined[-self.max_samples :]
        return combined

    def echo_score(self, mic_audio: np.ndarray) -> float:
        """Return normalized correlation 0–1 between mic chunk and recent system buffer."""
        if not settings.echo_suppression_enabled:
            return 0.0
        if len(mic_audio) < self.sample_rate // 10:
            return 0.0
        if len(self._sys_buf) < self.sample_rate // 10:
            return 0.0

        mic = mic_audio.astype(np.float32)
        sys = self._sys_buf
        n = min(len(mic), len(sys))
        mic = mic[-n:]
        sys = sys[-n:]

        mic = mic - np.mean(mic)
        sys = sys - np.mean(sys)
        mic_norm = np.linalg.norm(mic)
        sys_norm = np.linalg.norm(sys)
        if mic_norm < 1e-8 or sys_norm < 1e-8:
            return 0.0

        corr = float(np.dot(mic, sys) / (mic_norm * sys_norm))
        return max(0.0, corr)

    def is_echo(self, mic_audio: np.ndarray) -> tuple[bool, float]:
        score = self.echo_score(mic_audio)
        threshold = settings.echo_correlation_threshold
        return score >= threshold, score

    def clear_system(self) -> None:
        self._sys_buf = np.zeros(0, dtype=np.float32)
