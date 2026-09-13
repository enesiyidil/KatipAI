# KatipAI

[![CI](https://github.com/enesiyidil/KatipAI/actions/workflows/ci.yml/badge.svg)](https://github.com/enesiyidil/KatipAI/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A macOS background assistant that listens to your audio and takes notes with **fully local AI** — built for remote developers. Nothing leaves your machine: speech-to-text and summarization run on-device with Apple MLX.

> Türkçe açıklama için [aşağıya bakın](#türkçe).

## Features

- **Silero VAD** — records only when human speech is detected; splits a chunk after 2 s of silence; stops the session after 60 s of silence.
- **Dual channel** — microphone (*Ben* / "Me") and system audio (*Diğer* / "Other") on separate tracks.
- **STT** — `mlx-community/whisper-large-v3-turbo` (Turkish).
- **LLM** — `mlx-community/Qwen3.5-4B-OptiQ-4bit` for smart hybrid summaries.
- **Obsidian** — daily index + per-session Markdown files written to your vault.
- **Web UI** — dashboard, jargon, review queue, settings.
- **Menu bar** — pause, modes, quick jargon, status indicator.

## Privacy

KatipAI is **local-first**. Audio, transcripts, summaries and your voice profile stay in `~/.katipai/` (and, optionally, your Obsidian vault). There is no cloud API and no telemetry. The HTTP/WebSocket API binds to `127.0.0.1` only. Please read [SECURITY.md](SECURITY.md) for the local trust model before exposing the port.

## Requirements

- macOS 13+ (Apple Silicon; M1 Pro or better recommended)
- Python 3.11+
- ~8 GB free RAM (models are loaded sequentially)
- Microphone + Screen Recording permission (Screen Recording is required for system audio)

## Installation

```bash
chmod +x scripts/install_mac.sh
./scripts/install_mac.sh
```

Then copy the example environment file and adjust as needed:

```bash
cp .env.example .env
```

## Running

```bash
source .venv/bin/activate
katipai doctor       # verify dependencies and permissions
katipai up --all     # core + web + tray
katipai status       # show running services
katipai down         # stop everything
```

Or start the pieces manually:

```bash
# Terminal 1 — core service
source .venv/bin/activate && katipai server

# Terminal 2 — menu bar
source .venv/bin/activate && python apps/tray/tray_app.py

# Terminal 3 — web UI
cd apps/web && npm install && npm run dev   # http://localhost:5173
```

Pages: Dashboard, Live Feed, AI Notes, Transcript, General Notes, Review, Jargon, Settings.

## Obsidian

Set the vault path in Settings. Notes are written as:

```
{vault}/KatipAI/
  README.md
  transcript/2026-06-12.md      # daily raw transcript
  notes/daily/2026-06-12.md     # daily AI notes
  general/Notlar.md             # persistent general notes
```

**General note command:** while speaking, say *"bunu genel notlara ekle"* ("add this to general notes") and the note is appended to `general/Notlar.md`.

## API

- `GET /api/status` — status
- `POST /api/pause`, `/api/resume`, `/api/mode/{mode}`
- `GET /api/sessions/today`
- `GET /api/chunks/review-queue`
- `GET/POST /api/jargon`
- `PATCH /api/settings`

WebSocket: `ws://127.0.0.1:8742/ws`

## Models

| Role | Model | Fallback |
|------|-------|----------|
| STT | whisper-large-v3-turbo | whisper-medium-mlx |
| LLM | Qwen3.5-4B-OptiQ-4bit | Qwen2.5-3B-Instruct-4bit |

Models are downloaded from Hugging Face on first use (~4.5 GB total). See [NOTICE.md](NOTICE.md) for third-party and model license information.

## Contributing

Contributions are welcome! See [CONTRIBUTING.md](CONTRIBUTING.md) and our [Code of Conduct](CODE_OF_CONDUCT.md). The [roadmap](docs/ROADMAP.md) and [feature list](docs/FEATURES.md) show where the project is headed.

## License

[MIT](LICENSE) © 2026 Enes İyidil

---

## Türkçe

Arka planda ses dinleyip **tamamen lokal AI** ile not alan macOS uygulaması — uzaktan çalışan yazılımcılar için. Hiçbir veri makineni terk etmez: konuşma tanıma ve özetleme Apple MLX ile cihaz üzerinde çalışır.

### Özellikler

- **Silero VAD** — insan sesi algılandığında kayıt; 2 sn sessizlikte chunk bölme; 60 sn sessizlikte oturum durma.
- **Çift kanal** — mikrofon (*Ben*) + sistem sesi (*Diğer*) ayrı track.
- **STT** — `mlx-community/whisper-large-v3-turbo` (Türkçe).
- **LLM** — `mlx-community/Qwen3.5-4B-OptiQ-4bit` (akıllı hibrit özet).
- **Obsidian** — vault'a günlük index + oturum Markdown dosyaları.
- **Web UI** — dashboard, jargon, düzeltme kuyruğu, ayarlar.
- **Menü bar** — duraklat, modlar, hızlı jargon, durum göstergesi.

### Gizlilik

KatipAI **önce-lokal** çalışır. Ses, transcript, özet ve ses profilin `~/.katipai/` (ve isteğe bağlı Obsidian vault) içinde kalır. Bulut API'si ve telemetri yoktur; HTTP/WebSocket API yalnızca `127.0.0.1`'e bağlanır. Portu açmadan önce lokal güven modeli için [SECURITY.md](SECURITY.md) dosyasını okuyun.

### Gereksinimler

- macOS 13+ (Apple Silicon; M1 Pro önerilir)
- Python 3.11+
- ~8 GB boş RAM (modeller sıralı yüklenir)
- Mikrofon + Ekran Kaydı izni (sistem sesi için Ekran Kaydı gereklidir)

### Kurulum ve Çalıştırma

```bash
chmod +x scripts/install_mac.sh
./scripts/install_mac.sh
cp .env.example .env

source .venv/bin/activate
katipai doctor       # bağımlılık ve izin kontrolü
katipai up --all     # core + web + tray
```

Web arayüzü: `cd apps/web && npm install && npm run dev` → http://localhost:5173

### Katkı

Katkılar memnuniyetle karşılanır! [CONTRIBUTING.md](CONTRIBUTING.md) ve [Davranış Kuralları](CODE_OF_CONDUCT.md) dosyalarına bakın. Yol haritası için [docs/ROADMAP.md](docs/ROADMAP.md), özellik listesi için [docs/FEATURES.md](docs/FEATURES.md).

### Lisans

[MIT](LICENSE) © 2026 Enes İyidil
