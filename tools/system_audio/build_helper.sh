#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT"

echo "==> Swift helper derleniyor..."
swift build -c release

APP="$ROOT/KatipAIAudioHelper.app"
BIN="$APP/Contents/MacOS/KatipAIAudioHelper"

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$ROOT/.build/release/SystemAudioCapture" "$BIN"
cp "$ROOT/app/Info.plist" "$APP/Contents/Info.plist"
chmod +x "$BIN"

echo "==> App bundle imzalanıyor..."
codesign -s - --force --deep "$APP"

echo "Hazır: $APP"
echo "macOS: Sistem Ayarları → Ekran ve Sistem Sesi Kaydı →"
echo "  «Yalnızca Sistem Sesi Kaydı» bölümüne + ile KatipAI Audio ekleyin"
