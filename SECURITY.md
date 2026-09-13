# Security Policy

> Kısa Türkçe özet en alttadır.

## Reporting a vulnerability

Please **do not** open a public issue for security vulnerabilities.

Instead, report privately using GitHub's [private vulnerability reporting](https://github.com/enesiyidil/KatipAI/security/advisories/new) (Security tab → "Report a vulnerability"). We aim to acknowledge reports within a few days.

When possible, include:

- affected version / commit
- steps to reproduce
- impact and any suggested mitigation

## Trust model and local data

KatipAI is a **local-first, single-user desktop application**. Understanding its trust boundary is important:

- The HTTP/WebSocket API binds to `127.0.0.1:8742` (loopback only). It is **not authenticated** — anyone (or any process) that can reach the loopback interface on your machine can control recording, read chunks, and manage the voice profile. Treat the machine running KatipAI as the trust boundary; do not port-forward, reverse-proxy, or otherwise expose the port to a network.
- CORS is restricted to the local web UI origins (`http://127.0.0.1:5173`, `http://localhost:5173`).
- Sensitive data stays on disk under your home directory:
  - `~/.katipai/katipai.db` — sessions, chunks, transcripts, jargon, corrections
  - `~/.katipai/audio/` — recorded audio (WAV)
  - `~/.katipai/voice_enrollment.webm` and the voice-profile embedding in the DB
  - your Obsidian vault (if configured) — transcripts and notes
- No data is sent to any cloud service. Models are downloaded from Hugging Face on first use; after that, inference is fully offline.

## Handling recordings in bug reports

Do **not** attach real audio recordings, transcripts, or voice-profile files to public issues. Redact any personal content and prefer synthetic examples.

## Supported versions

The project is pre-1.0. Security fixes are applied to the latest `main`.

---

## Türkçe (özet)

- Güvenlik açıkları için **herkese açık issue açmayın**; GitHub'ın özel güvenlik raporlama özelliğini kullanın (Security sekmesi → "Report a vulnerability").
- KatipAI **önce-lokal, tek kullanıcılı** bir masaüstü uygulamasıdır. API yalnızca `127.0.0.1:8742`'ye bağlanır ve **kimlik doğrulaması yoktur**; portu ağa açmayın.
- Ses, transcript ve ses profili verileri `~/.katipai/` (ve varsa Obsidian vault) içinde tutulur. Bulut yoktur.
- Hata bildirimlerine gerçek ses/transcript/ses profili dosyaları eklemeyin.
