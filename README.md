# KatipAI

Arka planda ses dinleyip lokal AI ile not alan macOS uygulaması — uzaktan çalışan yazılımcılar için.

## Özellikler

- **Silero VAD** — insan sesi algılandığında kayıt; 2 sn sessizlikte chunk bölme; 60 sn sessizlikte oturum durma
- **Çift kanal** — mikrofon (Ben) + sistem sesi (Diğer) ayrı track
- **STT** — `mlx-community/whisper-large-v3-turbo` (Türkçe)
- **LLM** — `mlx-community/Qwen3.5-4B-OptiQ-4bit` (akıllı hibrit özet)
- **Obsidian** — vault'a günlük index + oturum Markdown dosyaları
- **Web UI** — dashboard, jargon, düzeltme kuyruğu, ayarlar
- **Menü bar** — duraklat, modlar, hızlı jargon, durum göstergesi

## Gereksinimler

- macOS 13+ (M1 Pro önerilir)
- Python 3.11+
- ~8 GB boş RAM (modeller sıralı yüklenir)
- Mikrofon + Ekran Kaydı izni (sistem sesi için)

## Kurulum

```bash
chmod +x scripts/install_mac.sh
./scripts/install_mac.sh
```

## Çalıştırma

Terminal 1 — core servis:
```bash
source .venv/bin/activate
katipai server
```

Terminal 2 — menü bar:
```bash
source .venv/bin/activate
pip install rumps   # menü bar için
python apps/tray/tray_app.py
```

Terminal 3 — web arayüzü:
```bash
cd apps/web && npm install && npm run dev
```

Tarayıcı: http://localhost:5173

## Obsidian

Ayarlar'dan vault yolunu girin. Notlar şu yapıda yazılır:

```
{vault}/KatipAI/
  daily/2025-06-12.md
  sessions/2025-06-12_14-32-07.md
  archive/transcripts/2025-06-12_14-32-07_full.md
```

## API

- `GET /api/status` — durum
- `POST /api/pause`, `/api/resume`, `/api/mode/{mode}`
- `GET /api/sessions/today`
- `GET /api/chunks/review-queue`
- `GET/POST /api/jargon`
- `PATCH /api/settings`

WebSocket: `ws://127.0.0.1:8742/ws`

## Modeller

| Rol | Model | Fallback |
|-----|-------|----------|
| STT | whisper-large-v3-turbo | whisper-medium-mlx |
| LLM | Qwen3.5-4B-OptiQ-4bit | Qwen2.5-3B-Instruct-4bit |

Modeller ilk kullanımda HuggingFace'den indirilir (~4.5 GB toplam).
