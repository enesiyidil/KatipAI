# Contributing to KatipAI

Thanks for your interest in improving KatipAI! This document explains how to set up your environment, the workflow we use, and what the CI checks.

> Kısa Türkçe özet en alttadır.

## Ways to contribute

- Report bugs and request features via [Issues](https://github.com/enesiyidil/KatipAI/issues).
- Improve documentation (including English/Turkish parity).
- Fix bugs or implement items from the [roadmap](docs/ROADMAP.md) / [feature list](docs/FEATURES.md).

For anything larger than a small fix, please **open an issue first** so we can agree on the approach before you invest time.

## Development setup

KatipAI runs fully only on macOS (Apple Silicon) because of MLX, ScreenCaptureKit and CoreAudio. However, most of the Python core and the entire web UI can be developed and tested on any platform — that is exactly the surface the CI verifies.

### Python core

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
```

The MLX packages (`mlx-whisper`, `mlx-lm`) are installed only on macOS via platform markers, so `pip install` works on Linux/Windows for development and testing.

### Web UI

```bash
cd apps/web
npm install
```

## Workflow

1. Fork the repository and create a branch: `feat/short-description` or `fix/short-description`.
2. Make your change with focused commits.
3. Run the checks locally (see below).
4. Open a pull request against `main` and fill in the PR template.

We keep a single long-lived branch (`main`). Feature work happens on short-lived `feat/*` / `fix/*` branches merged via pull request.

**Do not push to `main`.** Only the maintainer merges. Incoming PRs need a review from [@enesiyidil](https://github.com/enesiyidil) (code owner), green CI (`python` and `web`), and resolved conversations. New commits after an approval dismiss that review.

## Checks (run before pushing)

```bash
# Python
ruff check core tests
pytest -q

# Web
cd apps/web && npm test && npm run build
```

CI runs these on every pull request:

- **python** job: Ubuntu, Python 3.12 — `ruff check` + `pytest`.
- **web** job: Node 22 — `npm test` + `npm run build`.

Tests intentionally avoid loading real ML models, the microphone, or the Swift helper, so they run anywhere. Please do not add tests that require MLX weights, a microphone, or macOS-only APIs to the default suite.

## Coding style

- Python: 4-space indentation, type hints, kept `ruff`-clean.
- Keep changes minimal and focused; avoid unrelated refactors in the same PR.
- Do not commit secrets, real `.env` files, audio recordings, transcripts, or your voice profile.

## Reporting security issues

Please do **not** open a public issue for vulnerabilities. Follow [SECURITY.md](SECURITY.md).

---

## Türkçe (özet)

- Büyük değişikliklerden önce lütfen bir **issue açın**.
- Kurulum: `python -m venv .venv && source .venv/bin/activate && pip install -e ".[dev]"`. MLX paketleri yalnızca macOS'ta kurulur; Linux/Windows'ta çekirdek geliştirme ve testler çalışır.
- Dal isimlendirme: `feat/*`, `fix/*`; PR `main`'e açılır. `main`'e doğrudan push yok; birleşme için maintainer onayı ve yeşil CI gerekir.
- Göndermeden önce: `ruff check core tests`, `pytest -q`, ve web için `npm test && npm run build`.
- Sır, gerçek `.env`, ses kaydı, transcript veya ses profili commit etmeyin.
- Güvenlik açıkları için herkese açık issue açmayın; [SECURITY.md](SECURITY.md) izleyin.
