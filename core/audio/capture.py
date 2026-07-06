import logging
import subprocess
import threading
from collections.abc import Callable

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

    @property
    def is_active(self) -> bool:
        return self._running and self._stream is not None

    def start(self) -> bool:
        if self._running:
            return True
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
        return True

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
        self._stderr_thread: threading.Thread | None = None
        self._running = False
        self.last_error: str | None = None

    @property
    def is_active(self) -> bool:
        return (
            self._running
            and self._process is not None
            and self._process.poll() is None
        )

    def _capture_process_exit(self, code: int | None) -> None:
        self._running = False
        err_text = ""
        if self._process and self._process.stderr:
            try:
                err_text = self._process.stderr.read().decode(errors="replace").strip()
            except Exception:
                pass
        if err_text:
            self.last_error = "helper_error"
            logger.warning("System audio helper exited (%s): %s", code, err_text)
        elif code in (133, 134):
            self.last_error = "permission_denied"
            logger.warning(
                "System audio helper killed (code=%s) — "
                "Ekran ve Sistem Sesi Kaydı → SystemAudioCapture izni gerekli",
                code,
            )
        else:
            self.last_error = "process_exited"
            logger.warning("System audio helper exited (code=%s)", code)

    def _read_loop(self) -> None:
        assert self._process and self._process.stdout
        bytes_per_frame = 4
        chunk_frames = int(SAMPLE_RATE * 0.03)
        chunk_bytes = chunk_frames * bytes_per_frame
        try:
            while self._running and self._process.poll() is None:
                raw = self._process.stdout.read(chunk_bytes)
                if not raw or len(raw) < chunk_bytes:
                    if self._process.poll() is not None:
                        break
                    continue
                samples = np.frombuffer(raw, dtype=np.float32)
                self.on_audio(samples.copy())
        finally:
            if self._process and self._process.poll() is not None:
                self._capture_process_exit(self._process.returncode)

    def _stderr_loop(self) -> None:
        assert self._process and self._process.stderr
        for line in self._process.stderr:
            if not self._running:
                break
            text = line.decode(errors="replace").strip()
            if text:
                logger.warning("System audio helper: %s", text)

    def start(self) -> bool:
        if self._running:
            return True

        self.last_error = None
        cmd = get_capture_args()
        if cmd is None:
            self.last_error = "no_sources"
            logger.warning(
                "System audio not started — no apps selected. "
                "Select apps in Settings or enable capture_all_system_audio."
            )
            return False

        self._process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        self._stderr_thread = threading.Thread(target=self._stderr_loop, daemon=True)
        self._stderr_thread.start()

        if self._process.poll() is not None:
            self.last_error = "process_exited"
            self.stop()
            return False

        logger.info("System audio capture started: %s", " ".join(cmd[-3:]))
        return True

    def stop(self) -> None:
        self._running = False
        if self._process:
            self._process.terminate()
            try:
                self._process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                self._process.kill()
            self._process = None
        if self._thread:
            self._thread.join(timeout=2)
            self._thread = None
        if self._stderr_thread:
            self._stderr_thread.join(timeout=1)
            self._stderr_thread = None
