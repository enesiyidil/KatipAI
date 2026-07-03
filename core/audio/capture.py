import logging
import subprocess
import threading
from collections.abc import Callable
from pathlib import Path

import numpy as np
import sounddevice as sd

from core.audio.app_sources import get_capture_args
from core.config import settings

logger = logging.getLogger(__name__)

SAMPLE_RATE = settings.sample_rate
CHANNELS = 1
DTYPE = "float32"


class MicrophoneCapture:
    """16kHz mono microphone stream."""

    def __init__(self, on_audio: Callable[[np.ndarray], None]):
        self.on_audio = on_audio
        self._stream: sd.InputStream | None = None
        self._running = False

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.warning("Mic status: %s", status)
        self.on_audio(indata[:, 0].copy())

    def start(self) -> None:
        if self._running:
            return
        self._stream = sd.InputStream(
            samplerate=SAMPLE_RATE,
            channels=CHANNELS,
            dtype=DTYPE,
            blocksize=int(SAMPLE_RATE * 0.03),
            callback=self._callback,
        )
        self._stream.start()
        self._running = True
        logger.info("Microphone capture started")

    def stop(self) -> None:
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        self._running = False


class SystemAudioCapture:
    """System audio via Swift ScreenCaptureKit helper."""

    def __init__(self, on_audio: Callable[[np.ndarray], None]):
        self.on_audio = on_audio
        self._process: subprocess.Popen | None = None
        self._thread: threading.Thread | None = None
        self._running = False

    def _read_loop(self) -> None:
        assert self._process and self._process.stdout
        bytes_per_frame = 4
        chunk_frames = int(SAMPLE_RATE * 0.03)
        chunk_bytes = chunk_frames * bytes_per_frame
        while self._running and self._process.poll() is None:
            raw = self._process.stdout.read(chunk_bytes)
            if not raw or len(raw) < chunk_bytes:
                continue
            samples = np.frombuffer(raw, dtype=np.float32)
            self.on_audio(samples.copy())

    def start(self) -> None:
        if self._running:
            return
        cmd = get_capture_args()
        if cmd is None:
            logger.warning(
                "System audio not started — no apps selected. "
                "Select apps in Settings or enable capture_all_system_audio."
            )
            return
        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info("System audio capture started: %s", " ".join(cmd[-3:]))

    def stop(self) -> None:
        self._running = False
        if self._process:
            self._process.terminate()
            self._process = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
