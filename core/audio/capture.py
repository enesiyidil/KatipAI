import logging
import os
import socket
import subprocess
import threading
import time
from collections.abc import Callable
from pathlib import Path

import numpy as np
import sounddevice as sd

from core.audio.app_sources import (
    capture_config_snapshot,
    get_capture_launch_spec,
    helper_app_bundle,
    helper_binary_path,
)
from core.config import settings

logger = logging.getLogger(__name__)

SAMPLE_RATE = settings.sample_rate
CHANNELS = 1
DTYPE = "float32"
HELPER_LABEL = "KatipAIAudioHelper"
MAX_START_RETRIES = 3


class MicrophoneCapture:
    """16kHz mono microphone stream."""

    def __init__(self, on_audio: Callable[[np.ndarray], None]):
        self.on_audio = on_audio
        self._stream: sd.InputStream | None = None
        self._running = False
        self._current_level = 0.0

    @property
    def current_level(self) -> float:
        return self._current_level

    def _callback(self, indata, frames, time_info, status):
        if status:
            logger.warning("Mic status: %s", status)
        frame = indata[:, 0].copy()
        self._current_level = float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))
        self.on_audio(frame)

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
    """System audio via KatipAIAudioHelper (ScreenCaptureKit + unix socket)."""

    def __init__(
        self,
        on_audio: Callable[[np.ndarray], None],
        on_failed: Callable[[], None] | None = None,
    ):
        self.on_audio = on_audio
        self.on_failed = on_failed
        self._client: socket.socket | None = None
        self._server: socket.socket | None = None
        self._thread: threading.Thread | None = None
        self._monitor_thread: threading.Thread | None = None
        self._socket_path: Path | None = None
        self._proc: subprocess.Popen | None = None
        self._log_handle = None
        self._running = False
        self.last_error: str | None = None

    @property
    def is_active(self) -> bool:
        return self._running and self._client is not None

    def _helper_log_path(self) -> Path:
        return settings.data_dir / "run" / "logs" / "audio-helper.log"

    def _capture_failed(self, code: str, message: str) -> None:
        self.last_error = code
        self._running = False
        logger.warning(message)
        if self.on_failed:
            try:
                self.on_failed()
            except Exception:
                logger.exception("System capture on_failed callback error")

    def _read_loop(self) -> None:
        assert self._client is not None
        bytes_per_frame = 4
        chunk_frames = int(SAMPLE_RATE * 0.03)
        chunk_bytes = chunk_frames * bytes_per_frame
        try:
            while self._running:
                raw = self._client.recv(chunk_bytes)
                if not raw:
                    break
                if len(raw) < chunk_bytes:
                    continue
                samples = np.frombuffer(raw, dtype=np.float32)
                self.on_audio(samples.copy())
        except OSError:
            pass
        finally:
            if self._running:
                code = self._proc.poll() if self._proc else None
                self._capture_failed(
                    "process_exited",
                    f"System audio helper bağlantısı kapandı (code={code})",
                )

    def _monitor_process(self) -> None:
        proc = self._proc
        if proc is None:
            return
        code = proc.wait()
        if self._running and code not in (0, None):
            logger.warning("System audio helper exited (code=%s)", code)
            tail = self._read_helper_log_tail()
            if tail:
                logger.warning("Helper log tail:\n%s", tail)
            self._capture_failed("helper_error", f"Sistem sesi helper hatası (code={code})")

    def _read_helper_log_tail(self, lines: int = 8) -> str:
        path = self._helper_log_path()
        if not path.exists():
            return ""
        try:
            content = path.read_text(encoding="utf-8", errors="replace").splitlines()
            return "\n".join(content[-lines:])
        except OSError:
            return ""

    def _launch_helper(self, launch_args: list[str]) -> subprocess.Popen | None:
        helper_bin = helper_binary_path()
        if not helper_bin.exists():
            return None

        log_path = self._helper_log_path()
        log_path.parent.mkdir(parents=True, exist_ok=True)
        if self._log_handle:
            try:
                self._log_handle.close()
            except OSError:
                pass
        self._log_handle = open(log_path, "a", encoding="utf-8")
        self._log_handle.write(f"\n--- launch pid={os.getpid()} args={' '.join(launch_args)} ---\n")
        self._log_handle.flush()

        try:
            return subprocess.Popen(
                [str(helper_bin), *launch_args],
                stdout=subprocess.DEVNULL,
                stderr=self._log_handle,
            )
        except Exception as e:
            self._log_handle.write(f"launch failed: {e}\n")
            self._log_handle.flush()
            logger.warning("System audio launch failed: %s", e)
            return None

    def _try_start_once(self, spec: dict, attempt: int) -> bool:
        self._cleanup_sockets()
        self.last_error = None

        self._socket_path = Path(settings.data_dir) / f"audio-helper-{os.getpid()}.sock"
        self._socket_path.parent.mkdir(parents=True, exist_ok=True)
        if self._socket_path.exists():
            self._socket_path.unlink()

        self._server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self._server.bind(str(self._socket_path))
        self._server.listen(1)
        self._server.settimeout(12.0)

        launch_args = [*spec["args"], "--socket", str(self._socket_path)]
        self._proc = self._launch_helper(launch_args)
        if self._proc is None:
            self._cleanup_sockets()
            self.last_error = "spawn_failed"
            return False

        self._monitor_thread = threading.Thread(target=self._monitor_process, daemon=True)
        self._monitor_thread.start()

        try:
            self._client, _ = self._server.accept()
        except socket.timeout:
            self._cleanup_sockets()
            self.last_error = "permission_denied"
            logger.warning(
                "KatipAI Audio başlamadı (deneme %s/%s) — Ekran ve Sistem Sesi Kaydı iznini kontrol edin",
                attempt,
                MAX_START_RETRIES,
            )
            tail = self._read_helper_log_tail()
            if tail:
                logger.warning("Helper log tail:\n%s", tail)
            return False
        finally:
            if self._server:
                self._server.close()
                self._server = None

        self._client.settimeout(5.0)
        self._running = True
        self._thread = threading.Thread(target=self._read_loop, daemon=True)
        self._thread.start()
        logger.info(
            "System audio capture started (attempt %s): %s",
            attempt,
            " ".join(launch_args[-4:]),
        )
        return True

    def start(self) -> bool:
        if self._running:
            return True

        spec = get_capture_launch_spec()
        if spec is None:
            self.last_error = "no_sources"
            snap = capture_config_snapshot()
            missing = snap.get("missing_bundle_ids") or []
            if missing:
                logger.warning(
                    "System audio not started — selected apps not running: %s",
                    ", ".join(missing),
                )
            else:
                logger.warning(
                    "System audio not started — no apps selected. "
                    "Select apps in Settings or enable capture_all_system_audio."
                )
            return False

        if not helper_app_bundle().exists() and not helper_binary_path().exists():
            self.last_error = "missing_helper"
            logger.warning("KatipAIAudioHelper.app bulunamadı — build_helper.sh çalıştırın")
            return False

        for attempt in range(1, MAX_START_RETRIES + 1):
            if self._try_start_once(spec, attempt):
                return True
            self.stop()
            if attempt < MAX_START_RETRIES:
                time.sleep(0.8 * attempt)

        if self.last_error is None:
            self.last_error = "helper_error"
        return False

    def _cleanup_sockets(self) -> None:
        if self._client:
            try:
                self._client.close()
            except OSError:
                pass
            self._client = None
        if self._server:
            try:
                self._server.close()
            except OSError:
                pass
            self._server = None
        if self._socket_path and self._socket_path.exists():
            self._socket_path.unlink(missing_ok=True)
        self._socket_path = None
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
        self._proc = None

    def stop(self) -> None:
        self._running = False
        subprocess.run(["pkill", "-x", HELPER_LABEL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self._cleanup_sockets()
        if self._thread and self._thread is not threading.current_thread():
            self._thread.join(timeout=2)
            self._thread = None
        if self._monitor_thread and self._monitor_thread is not threading.current_thread():
            self._monitor_thread.join(timeout=1)
            self._monitor_thread = None
        if self._log_handle:
            try:
                self._log_handle.close()
            except OSError:
                pass
            self._log_handle = None


def probe_system_capture(timeout: float = 8.0) -> dict:
    """Test KatipAIAudioHelper launch + socket audio (macOS TCC)."""
    spec = get_capture_launch_spec()
    if spec is None:
        return {
            "ok": False,
            "code": "no_sources",
            "message": "Uygulama seçilmedi veya helper yok",
        }
    if not helper_app_bundle().exists() and not helper_binary_path().exists():
        return {"ok": False, "code": "missing_helper", "message": "KatipAIAudioHelper.app bulunamadı"}

    sock_path = Path(settings.data_dir) / f"audio-probe-{os.getpid()}.sock"
    sock_path.parent.mkdir(parents=True, exist_ok=True)
    if sock_path.exists():
        sock_path.unlink()

    server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
    helper_bin = helper_binary_path()
    try:
        server.bind(str(sock_path))
        server.listen(1)
        server.settimeout(timeout)
        launch_args = [*spec["args"], "--socket", str(sock_path)]
        log_path = settings.data_dir / "run" / "logs" / "audio-helper.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with open(log_path, "a", encoding="utf-8") as log_f:
            proc = subprocess.Popen(
                [str(helper_bin), *launch_args],
                stdout=subprocess.DEVNULL,
                stderr=log_f,
            )
        client, _ = server.accept()
        client.settimeout(3.0)
        try:
            data = client.recv(4096)
        finally:
            client.close()
        if proc.poll() is None:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
        subprocess.run(["pkill", "-x", HELPER_LABEL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if data:
            return {"ok": True, "code": "running", "message": "Sistem sesi yakalama çalışıyor"}
        return {
            "ok": True,
            "code": "connected",
            "message": "Sistem sesi izni tamam — seçili uygulama ses çalınca kayıt başlar",
        }
    except socket.timeout:
        subprocess.run(["pkill", "-x", HELPER_LABEL], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return {
            "ok": False,
            "code": "permission_denied",
            "message": "KatipAI Audio başlamadı — Ekran ve Sistem Sesi Kaydı iznini kontrol edin",
        }
    except Exception as e:
        return {"ok": False, "code": "probe_failed", "message": str(e)}
    finally:
        server.close()
        sock_path.unlink(missing_ok=True)
