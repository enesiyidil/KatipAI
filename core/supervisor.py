"""KatipAI process supervisor — doctor, up, down, restart, status."""

from __future__ import annotations

import json
import logging
import os
import shutil
import signal
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from enum import Enum
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = settings.data_dir / "run"
LOG_DIR = RUN_DIR / "logs"
VENV_PYTHON = PROJECT_ROOT / ".venv" / "bin" / "python"
SWIFT_HELPER = (
    PROJECT_ROOT / "tools" / "system_audio" / ".build" / "release" / "SystemAudioCapture"
)
WEB_DIR = PROJECT_ROOT / "apps" / "web"
API_URL = f"http://{settings.host}:{settings.port}/api/status"
WEB_PORT = 5173


class CheckStatus(str, Enum):
    OK = "ok"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    name: str
    status: CheckStatus
    message: str
    hint: str | None = None


def _python() -> str:
    return str(VENV_PYTHON if VENV_PYTHON.exists() else sys.executable)


def _ensure_run_dir() -> None:
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _pid_path(service: str) -> Path:
    return RUN_DIR / f"{service}.pid"


def _log_path(service: str) -> Path:
    return LOG_DIR / f"{service}.log"


def _read_pid(service: str) -> int | None:
    path = _pid_path(service)
    if not path.exists():
        return None
    try:
        pid = int(path.read_text().strip())
        os.kill(pid, 0)
        return pid
    except (OSError, ValueError):
        path.unlink(missing_ok=True)
        return None


def _write_pid(service: str, pid: int) -> None:
    _ensure_run_dir()
    _pid_path(service).write_text(str(pid))


def _port_open(port: int, host: str = "127.0.0.1") -> bool:
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _api_healthy() -> bool:
    try:
        with urllib.request.urlopen(API_URL, timeout=2) as resp:
            return resp.status == 200
    except (urllib.error.URLError, TimeoutError):
        return False


def _which(cmd: str) -> str | None:
    return shutil.which(cmd)


def run_doctor() -> list[CheckResult]:
    results: list[CheckResult] = []

    py_ver = sys.version_info
    if py_ver >= (3, 11):
        results.append(CheckResult("Python", CheckStatus.OK, f"{py_ver.major}.{py_ver.minor}.{py_ver.micro}"))
    else:
        results.append(CheckResult("Python", CheckStatus.FAIL, f"{py_ver.major}.{py_ver.minor} — 3.11+ gerekli", "brew install python@3.12"))

    if VENV_PYTHON.exists():
        results.append(CheckResult("Virtualenv", CheckStatus.OK, str(VENV_PYTHON.parent.parent)))
    else:
        results.append(CheckResult("Virtualenv", CheckStatus.FAIL, ".venv bulunamadı", "python3 -m venv .venv && pip install -e ."))

    try:
        import fastapi  # noqa: F401

        results.append(CheckResult("Python paketleri", CheckStatus.OK, "katipai kurulu"))
    except ImportError:
        results.append(CheckResult("Python paketleri", CheckStatus.FAIL, "fastapi import edilemedi", "pip install -e ."))

    if _which("ffmpeg"):
        results.append(CheckResult("ffmpeg", CheckStatus.OK, _which("ffmpeg") or ""))
    else:
        results.append(CheckResult("ffmpeg", CheckStatus.FAIL, "bulunamadı", "brew install ffmpeg"))

    if sys.platform == "darwin":
        if _which("swift"):
            results.append(CheckResult("Swift", CheckStatus.OK, _which("swift") or ""))
        else:
            results.append(CheckResult("Swift", CheckStatus.WARN, "bulunamadı", "Xcode CLT — sistem sesi devre dışı"))

        if SWIFT_HELPER.exists():
            results.append(CheckResult("SystemAudioCapture", CheckStatus.OK, str(SWIFT_HELPER)))
        else:
            results.append(CheckResult("SystemAudioCapture", CheckStatus.WARN, "derlenmemiş", "cd tools/system_audio && swift build -c release"))
    else:
        results.append(CheckResult("macOS", CheckStatus.WARN, "KatipAI tam özellik için macOS 13+ önerilir"))

    if _which("node"):
        results.append(CheckResult("Node.js", CheckStatus.OK, _which("node") or ""))
    else:
        results.append(CheckResult("Node.js", CheckStatus.WARN, "bulunamadı", "brew install node — web UI için"))

    if (WEB_DIR / "node_modules").exists():
        results.append(CheckResult("Web bağımlılıkları", CheckStatus.OK, "node_modules mevcut"))
    elif _which("npm"):
        results.append(CheckResult("Web bağımlılıkları", CheckStatus.WARN, "node_modules yok", "cd apps/web && npm install"))
    else:
        results.append(CheckResult("Web bağımlılıkları", CheckStatus.WARN, "npm yok"))

    settings.data_dir.mkdir(parents=True, exist_ok=True)
    results.append(CheckResult("Veri dizini", CheckStatus.OK, str(settings.data_dir)))

    voice_model = settings.data_dir / "models" / "speaker_embedding.onnx"
    if voice_model.exists():
        results.append(CheckResult("Ses profili modeli", CheckStatus.OK, str(voice_model)))
    else:
        results.append(CheckResult("Ses profili modeli", CheckStatus.WARN, "ONNX yok (fallback kullanılır)", "python scripts/download_voice_model.py"))

    if _port_open(settings.port):
        if _api_healthy():
            results.append(CheckResult(f"API :{settings.port}", CheckStatus.OK, "çalışıyor ve yanıt veriyor"))
        else:
            results.append(CheckResult(f"API :{settings.port}", CheckStatus.WARN, "port dolu ama API yanıt vermiyor"))
    else:
        results.append(CheckResult(f"API :{settings.port}", CheckStatus.OK, "boş (başlatılabilir)"))

    if _port_open(WEB_PORT):
        results.append(CheckResult(f"Web :{WEB_PORT}", CheckStatus.WARN, "port dolu"))
    else:
        results.append(CheckResult(f"Web :{WEB_PORT}", CheckStatus.OK, "boş (başlatılabilir)"))

    if sys.platform == "darwin":
        results.append(CheckResult(
            "macOS izinleri",
            CheckStatus.WARN,
            "Mikrofon + Ekran Kaydı — Sistem Ayarları'ndan kontrol edin",
            "Sistem Ayarları → Gizlilik ve Güvenlik",
        ))

    return results


def print_doctor(results: list[CheckResult]) -> int:
    icons = {CheckStatus.OK: "✓", CheckStatus.WARN: "!", CheckStatus.FAIL: "✗"}
    exit_code = 0
    for r in results:
        icon = icons[r.status]
        line = f"  [{icon}] {r.name}: {r.message}"
        print(line)
        if r.hint:
            print(f"      → {r.hint}")
        if r.status == CheckStatus.FAIL:
            exit_code = 1
    fails = sum(1 for r in results if r.status == CheckStatus.FAIL)
    warns = sum(1 for r in results if r.status == CheckStatus.WARN)
    print()
    if fails:
        print(f"{fails} hata, {warns} uyarı — düzeltmeden 'katipai up' riskli olabilir.")
    elif warns:
        print(f"Tüm kritik kontroller geçti ({warns} uyarı).")
    else:
        print("Tüm kontroller geçti.")
    return exit_code


def _start_process(service: str, cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> int:
    existing = _read_pid(service)
    if existing:
        logger.info("%s zaten çalışıyor (pid %s)", service, existing)
        return existing

    _ensure_run_dir()
    log_file = open(_log_path(service), "a", encoding="utf-8")
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)

    proc = subprocess.Popen(
        cmd,
        cwd=str(cwd or PROJECT_ROOT),
        stdout=log_file,
        stderr=subprocess.STDOUT,
        start_new_session=True,
        env=proc_env,
    )
    _write_pid(service, proc.pid)
    log_file.close()
    return proc.pid


def _wait_for_api(timeout: float = 30) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _api_healthy():
            return True
        time.sleep(0.5)
    return False


def _wait_for_web(timeout: float = 20) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _port_open(WEB_PORT):
            return True
        time.sleep(0.5)
    return False


def run_up(*, web: bool = False, tray: bool = False) -> None:
    results = run_doctor()
    fails = [r for r in results if r.status == CheckStatus.FAIL]
    if fails:
        print("Kritik hatalar var — önce 'katipai doctor' çıktısını düzeltin.")
        print_doctor(results)
        sys.exit(1)

    print("KatipAI başlatılıyor...")
    python = _python()

    core_pid = _start_process(
        "core",
        [python, "-m", "core.main"],
    )
    print(f"  core  pid={core_pid}  log={_log_path('core')}")

    if not _wait_for_api():
        print("  ✗ API 30 sn içinde hazır olmadı — logları kontrol edin:")
        print(f"    tail -f {_log_path('core')}")
        sys.exit(1)
    print(f"  ✓ API http://{settings.host}:{settings.port}")

    if web:
        npm = _which("npm")
        if not npm:
            print("  ✗ npm bulunamadı — web atlandı")
        elif not (WEB_DIR / "node_modules").exists():
            print("  ! node_modules yok — 'cd apps/web && npm install' çalıştırın")
        else:
            web_pid = _start_process("web", [npm, "run", "dev"], cwd=WEB_DIR)
            print(f"  web   pid={web_pid}  log={_log_path('web')}")
            if _wait_for_web():
                print(f"  ✓ Web http://localhost:{WEB_PORT}")
            else:
                print(f"  ! Web henüz hazır değil — log: {_log_path('web')}")

    if tray:
        if sys.platform != "darwin":
            print("  ✗ Tray yalnızca macOS'ta")
        else:
            tray_pid = _start_process(
                "tray",
                [python, str(PROJECT_ROOT / "apps" / "tray" / "tray_app.py")],
                env={"KATIPAI_MANAGED": "1"},
            )
            print(f"  tray  pid={tray_pid}")

    print()
    print("Hazır. Durdurmak için: katipai down")


def _stop_service(service: str, sig: int = signal.SIGTERM) -> bool:
    pid = _read_pid(service)
    if pid is None:
        return False
    try:
        os.killpg(os.getpgid(pid), sig)
    except ProcessLookupError:
        pass
    except PermissionError:
        try:
            os.kill(pid, sig)
        except ProcessLookupError:
            pass

    for _ in range(20):
        try:
            os.kill(pid, 0)
            time.sleep(0.25)
        except OSError:
            break

    _pid_path(service).unlink(missing_ok=True)
    return True


def run_down() -> None:
    stopped = []
    for service in ("tray", "web", "core"):
        if _stop_service(service):
            stopped.append(service)
    if stopped:
        print(f"Durduruldu: {', '.join(stopped)}")
    else:
        print("Çalışan servis bulunamadı.")


def run_restart(*, web: bool = False, tray: bool = False) -> None:
    run_down()
    time.sleep(1)
    run_up(web=web, tray=tray)


def run_status() -> None:
    services = {}
    for name in ("core", "web", "tray"):
        pid = _read_pid(name)
        services[name] = pid

    print("KatipAI durumu")
    print("-" * 40)
    for name, pid in services.items():
        if pid:
            log = _log_path(name)
            print(f"  {name:6} pid={pid}  log={log}")
        else:
            print(f"  {name:6} kapalı")

    print()
    if _api_healthy():
        try:
            with urllib.request.urlopen(API_URL, timeout=2) as resp:
                data = json.loads(resp.read())
            print(f"  API   http://{settings.host}:{settings.port}  state={data.get('state')} mode={data.get('mode')}")
        except Exception:
            print(f"  API   http://{settings.host}:{settings.port}  (yanıt okunamadı)")
    else:
        print(f"  API   kapalı veya yanıt vermiyor")

    if _port_open(WEB_PORT):
        print(f"  Web   http://localhost:{WEB_PORT}")
    else:
        print("  Web   kapalı")
