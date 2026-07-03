#!/usr/bin/env python3
"""Eski KatipAI vault yapısını temizle (sessions/, archive/, eski daily/)."""

import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.config import settings


def clean():
    if not settings.vault_path:
        print("Vault yolu ayarlı değil (.env)")
        sys.exit(1)

    base = settings.vault_path / "KatipAI"
    if not base.exists():
        print("KatipAI klasörü yok, temizlenecek bir şey yok.")
        return

    remove_dirs = ["sessions", "archive", "daily"]
    for name in remove_dirs:
        path = base / name
        if path.exists():
            shutil.rmtree(path)
            print(f"Silindi: {path}")

    # Eski README varsa koru, yeni yapı writer tarafından oluşturulacak
    print("Temizlik tamamlandı.")


if __name__ == "__main__":
    clean()
