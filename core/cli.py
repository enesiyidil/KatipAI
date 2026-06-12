import argparse
import logging

logging.basicConfig(level=logging.INFO)


def main():
    parser = argparse.ArgumentParser(prog="katipai")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("server", help="FastAPI core servisini başlat")
    sub.add_parser("test-vad", help="VAD testi (mikrofon 10 sn)")

    args = parser.parse_args()
    if args.command == "server":
        from core.main import run_server

        run_server()
    elif args.command == "test-vad":
        _test_vad()
    else:
        parser.print_help()


def _test_vad():
    import time

    import numpy as np
    import sounddevice as sd

    from core.audio.vad_processor import SileroVAD

    vad = SileroVAD()
    print("10 saniye dinleniyor... Konuşun.")
    detected = 0

    def callback(indata, frames, time_info, status):
        nonlocal detected
        if vad.is_speech(indata[:, 0]):
            detected += 1
            print(".", end="", flush=True)

    with sd.InputStream(samplerate=16000, channels=1, callback=callback, blocksize=480):
        time.sleep(10)
    print(f"\nKonuşma frame sayısı: {detected}")
