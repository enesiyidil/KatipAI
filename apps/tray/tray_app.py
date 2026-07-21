"""KatipAI macOS menü bar uygulaması."""

import os
import socket
import subprocess
import webbrowser

import rumps

API = "http://127.0.0.1:8742/api"
API_HOST = "127.0.0.1"
API_PORT = 8742
POLL_TIMEOUT = 8
MAX_TRANSIENT_FAILURES = 4

STATE_TR = {
    "idle": "Beklemede",
    "listening": "Dinliyor",
    "recording": "Kayıt",
    "processing": "İşleniyor",
    "paused": "Duraklatıldı",
    "sensitive": "Hassas Mod",
    "error": "Hata",
}

MODE_TR = {
    "normal": "Normal",
    "meeting": "Toplantı",
    "silent": "Sessiz",
    "sensitive": "Hassas",
    "manual": "Manuel",
}

STATE_ICONS = {
    "idle": "⚫",
    "listening": "🟢",
    "recording": "🔴",
    "processing": "🔵",
    "paused": "🟠",
    "sensitive": "🟣",
    "error": "❌",
}


class KatipAITray(rumps.App):
    def __init__(self):
        super().__init__("KatipAI", icon=None, template=True, quit_button=None)
        self._state = "idle"
        self._mode = "normal"
        self._core_process = None
        self._spawned_core = False
        self._managed = os.environ.get("KATIPAI_MANAGED") == "1"
        self._poll_failures = 0
        self._last_good_data: dict | None = None

        self.state_item = rumps.MenuItem("Durum: Başlatılıyor...", callback=None)
        self.primary_item = rumps.MenuItem("Dinlemeyi Başlat", callback=self.start_listening)
        self.stop_item = rumps.MenuItem("Dinlemeyi Durdur", callback=self.stop_listening)

        self.menu = [
            self.state_item,
            None,
            self.primary_item,
            self.stop_item,
            rumps.MenuItem("Manuel Kayıt", callback=self.manual_record),
            None,
            rumps.MenuItem("Normal Mod", callback=lambda _: self.set_mode("normal")),
            rumps.MenuItem("Toplantı Modu", callback=lambda _: self.set_mode("meeting")),
            rumps.MenuItem("Sessiz Mod (STT kapalı)", callback=lambda _: self.set_mode("silent")),
            rumps.MenuItem("Hassas Mod", callback=lambda _: self.set_mode("sensitive")),
            None,
            rumps.MenuItem("Son Chunk Sil", callback=self.delete_last),
            rumps.MenuItem("Hızlı Jargon Ekle", callback=self.add_jargon),
            None,
            rumps.MenuItem("Kontrol Paneli", callback=self.open_dashboard),
            rumps.MenuItem("Ses Kaynakları", callback=self.open_audio_settings),
            rumps.MenuItem("Ayarlar", callback=self.open_settings),
            None,
            rumps.MenuItem("Çıkış", callback=self.quit_app),
        ]

        if not self._managed:
            self._start_core()
        rumps.Timer(self.poll_status, 2).start()

    def _start_core(self):
        if self._api_get("/status"):
            return
        import sys
        from pathlib import Path

        root = Path(__file__).resolve().parents[2]
        venv_python = root / ".venv" / "bin" / "python"
        python = str(venv_python) if venv_python.exists() else sys.executable
        self._core_process = subprocess.Popen(
            [python, "-m", "core.main"],
            cwd=str(root),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self._spawned_core = True

    def _api_post(self, path: str) -> dict | None:
        import json
        import urllib.error
        import urllib.request

        req = urllib.request.Request(f"{API}{path}", method="POST")
        try:
            with urllib.request.urlopen(req, timeout=3) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")
            rumps.notification("KatipAI", "İşlem başarısız", detail[:120] or str(e))
            return None
        except Exception as e:
            rumps.notification("KatipAI", "Sunucuya ulaşılamadı", str(e)[:120])
            return None

    def _api_get(self, path: str, timeout: float = POLL_TIMEOUT) -> dict:
        import json
        import urllib.request

        try:
            with urllib.request.urlopen(f"{API}{path}", timeout=timeout) as resp:
                return json.loads(resp.read())
        except Exception:
            return {}

    def _core_port_open(self) -> bool:
        try:
            with socket.create_connection((API_HOST, API_PORT), timeout=0.5):
                return True
        except OSError:
            return False

    def _effective_state(self, data: dict) -> str:
        state = data.get("state", "idle")
        pipeline = data.get("pipeline") or {}
        if pipeline.get("busy") and state == "listening":
            return "processing"
        return state

    def _render_status(self, data: dict, *, stale: bool = False) -> None:
        self._state = self._effective_state(data)
        self._mode = data.get("mode", "normal")
        icon = STATE_ICONS.get(self._state, "⚫")
        state_label = STATE_TR.get(self._state, self._state)
        mode_label = MODE_TR.get(self._mode, self._mode)
        suffix = " · yenileniyor" if stale else ""
        self.state_item.title = f"{icon} {state_label} · {mode_label}{suffix}"
        self.title = f"K {icon}"
        self._update_controls()

    def _update_controls(self):
        state = self._state
        mode = self._mode
        running = state != "idle"
        paused = state == "paused"
        sensitive = state == "sensitive" or mode == "sensitive"
        busy = state in ("processing", "recording")

        if not running:
            self.primary_item.title = "Dinlemeyi Başlat"
            self.primary_item.set_callback(self.start_listening)
            self.stop_item.set_callback(None)
        elif paused:
            self.primary_item.title = "Devam Et"
            self.primary_item.set_callback(self.resume)
            self.stop_item.set_callback(self.stop_listening)
        elif sensitive:
            self.primary_item.title = "Normal Moda Dön"
            self.primary_item.set_callback(lambda _: self.set_mode("normal"))
            self.stop_item.set_callback(self.stop_listening)
        elif busy:
            self.primary_item.set_callback(None)
            self.stop_item.set_callback(self.stop_listening)
        else:
            self.primary_item.title = "Duraklat"
            self.primary_item.set_callback(self.pause)
            self.stop_item.set_callback(self.stop_listening)

        manual = self.menu["Manuel Kayıt"]
        manual.set_callback(self.manual_record if running and not busy and not sensitive and not paused else None)

    def poll_status(self, _):
        data = self._api_get("/status")
        if not data:
            self._poll_failures += 1
            if self._last_good_data and self._poll_failures <= MAX_TRANSIENT_FAILURES:
                stale_data = dict(self._last_good_data)
                if self._core_port_open():
                    stale_data["state"] = "processing"
                self._render_status(stale_data, stale=True)
                return
            hint = "katipai up" if self._managed else "katipai up veya sunucu başlatın"
            self.state_item.title = f"Durum: Sunucu kapalı ({hint})"
            self.title = "K ⚫"
            self._state = "idle"
            self._update_controls()
            return

        self._poll_failures = 0
        self._last_good_data = data
        self._render_status(data)

    def start_listening(self, _):
        result = self._api_post("/start")
        if result and result.get("ok"):
            rumps.notification("KatipAI", "Dinleme başladı", "Mikrofon ve sistem sesi aktif")

    def stop_listening(self, _):
        result = self._api_post("/stop")
        if result and result.get("ok"):
            rumps.notification("KatipAI", "Dinleme durduruldu", "Kayıt beklemede")

    def pause(self, _):
        result = self._api_post("/pause")
        if result and result.get("ok"):
            rumps.notification("KatipAI", "Duraklatıldı", "Devam etmek için menüden seçin")

    def resume(self, _):
        result = self._api_post("/resume")
        if result and result.get("ok"):
            rumps.notification("KatipAI", "Devam ediliyor", "Dinleme yeniden aktif")

    def manual_record(self, _):
        self._api_post("/manual-record")

    def set_mode(self, mode: str):
        result = self._api_post(f"/mode/{mode}")
        if result and result.get("ok"):
            label = MODE_TR.get(mode, mode)
            rumps.notification("KatipAI", "Mod değişti", label)

    def delete_last(self, _):
        result = self._api_post("/delete-last-chunk")
        if result and result.get("ok"):
            rumps.notification("KatipAI", "Son chunk silindi", "")

    def add_jargon(self, _):
        window = rumps.Window("Terim:", "Jargon Ekle", ok="Ekle", cancel="İptal")
        response = window.run()
        if response.clicked:
            import json
            import urllib.request

            body = json.dumps({"term": response.text}).encode()
            req = urllib.request.Request(
                f"{API}/jargon",
                data=body,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            try:
                urllib.request.urlopen(req, timeout=2)
                rumps.notification("KatipAI", "Jargon eklendi", response.text)
            except Exception as e:
                rumps.alert(f"Hata: {e}")

    def open_dashboard(self, _):
        webbrowser.open("http://localhost:5173")

    def open_audio_settings(self, _):
        webbrowser.open("http://localhost:5173/settings")

    def open_settings(self, _):
        webbrowser.open("http://localhost:5173/settings")

    def quit_app(self, _):
        if self._spawned_core and self._core_process and not self._managed:
            self._core_process.terminate()
        rumps.quit_application()


if __name__ == "__main__":
    KatipAITray().run()
