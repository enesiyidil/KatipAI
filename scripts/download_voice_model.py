#!/usr/bin/env python3
"""Download a lightweight speaker embedding ONNX model for voice profile."""

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from core.config import settings

# Small speaker verification model (sherpa-onnx style 3dspeaker embedding)
MODEL_URL = (
    "https://github.com/k2-fsa/sherpa-onnx/releases/download/speaker-recongition-models/"
    "3dspeaker_speech_eres2net_base_sv_zh-cn_3dspeaker_16k.onnx"
)


def main() -> None:
    dest_dir = settings.data_dir / "models"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest = dest_dir / "speaker_embedding.onnx"

    if dest.exists():
        print(f"Model already exists: {dest}")
        return

    print(f"Downloading speaker embedding model to {dest}...")
    try:
        urllib.request.urlretrieve(MODEL_URL, dest)
        print("Done.")
    except Exception as e:
        print(f"Download failed: {e}")
        print("Voice profile will use spectral fallback until model is available.")
        sys.exit(1)


if __name__ == "__main__":
    main()
