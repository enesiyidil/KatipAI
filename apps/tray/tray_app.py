"""KatipAI macOS menü bar uygulaması."""

import subprocess
import webbrowser

import rumps

API = "http://127.0.0.1:8742/api"


class KatipAITray(rumps.App):
    def __init__(self):
        super().__init__("KatipAI", icon=None, template=True, quit_button=None)
        self.state_item = rumps.MenuItem("Durum: Başlatılıyor...", callback=None)
        self.menu = [
            self.state_item,
            None,
            rumps.MenuItem("Duraklat", callback=self.pause),
            rumps.MenuItem("Devam Et", callback=self.resume),
            rumps.MenuItem("Manuel Kayıt", callback=self.manual_record),
            None,
            rumps.MenuItem("Toplantı Modu (sadece sistem)", callback=lambda _: self.set_mode("meeting")),
            rumps.MenuItem("Sessiz Mod (sadece mikrofon)", callback=lambda _: self.set_mode("silent")),
            rumps.MenuItem("Hassas Mod (1 saat)", callback=lambda _: self.set_mode("sensitive")),
            None,
            rumps.MenuItem("Son Chunk Sil", callback=self.delete_last),
            rumps.MenuItem("Hızlı Jargon Ekle", callback=self.add_jargon),
            None,
            rumps.MenuItem("Bugünün Notları", callback=self.open_dashboard),
            rumps.MenuItem("Ayarlar", callback=self.open_settings),
            None,
            rumps.MenuItem("Çıkış", callback=self.quit_app),
        ]
        self._core_process = None
        self._start_core()
        rumps.Timer(self.poll_status, 3).start()

    def _start_core(self):
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

    def _api_post(self, path: str):
        import urllib.request

        req = urllib.request.Request(f"{API}{path}", method="POST")
        try:
            urllib.request.urlopen(req, timeout=2)
        except Exception:
            pass

    def _api_get(self, path: str) -> dict:
        import json
        import urllib.request

        try:
            with urllib.request.urlopen(f"{API}{path}", timeout=2) as resp:
                return json.loads(resp.read())
        except Exception:
            return {}

    def poll_status(self, _):
        data = self._api_get("/status")
        state = data.get("state", "unknown")
        mode = data.get("mode", "normal")
        icons = {
            "idle": "⚫",
            "listening": "🟢",
            "recording": "🔴",
            "processing": "🔵",
            "paused": "🟠",
            "sensitive": "🟣",
            "error": "❌",
        }
        icon = icons.get(state, "⚫")
        self.state_item.title = f"{icon} {state} | mod: {mode}"
        self.title = f"K {icon}"

    def pause(self, _):
        self._api_post("/pause")

    def resume(self, _):
        self._api_post("/resume")

    def manual_record(self, _):
        self._api_post("/manual-record")

    def set_mode(self, mode: str):
        self._api_post(f"/mode/{mode}")

    def delete_last(self, _):
        self._api_post("/delete-last-chunk")

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

    def open_settings(self, _):
        webbrowser.open("http://localhost:5173/settings")

    def quit_app(self, _):
        if self._core_process:
            self._core_process.terminate()
        rumps.quit_application()


if __name__ == "__main__":
    KatipAITray().run()
