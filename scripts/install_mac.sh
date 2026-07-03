#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "==> KatipAI kurulumu"

if ! command -v python3 &>/dev/null; then
  echo "Python 3.11+ gerekli"
  exit 1
fi

if ! command -v brew &>/dev/null; then
  echo "Homebrew gerekli: https://brew.sh"
  exit 1
fi

brew list ffmpeg &>/dev/null || brew install ffmpeg
brew list portaudio &>/dev/null || brew install portaudio

python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e .

echo "==> Sistem sesi aracı derleniyor (ScreenCaptureKit)..."
if command -v swift &>/dev/null; then
  (cd tools/system_audio && swift build -c release)
  echo "Sistem sesi aracı hazır."
else
  echo "Swift bulunamadı — sistem sesi devre dışı kalacak, sadece mikrofon."
fi

mkdir -p "$HOME/.katipai"

echo ""
echo "Kurulum tamamlandı!"
echo ""
echo "Başlatmak için:"
echo "  source .venv/bin/activate"
echo "  katipai doctor          # bağımlılık kontrolü"
echo "  katipai up --all        # core + web + tray"
echo "  katipai down            # durdur"
echo "  katipai status          # durum"
echo ""
echo "Web arayüzü (ayrı): cd apps/web && npm install && npm run dev"
