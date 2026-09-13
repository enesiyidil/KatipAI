import argparse
import logging
import sys

logging.basicConfig(level=logging.INFO)


def main():
    parser = argparse.ArgumentParser(
        prog="katipai",
        description="KatipAI — lokal ses dinleme ve not asistanı",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("server", help="FastAPI core servisini başlat (ön plan)")
    sub.add_parser("test-vad", help="VAD testi (mikrofon 10 sn)")

    doctor_p = sub.add_parser("doctor", help="Bağımlılık ve ortam kontrolü")
    doctor_p.add_argument("--fix-hints", action="store_true", help=argparse.SUPPRESS)

    up_p = sub.add_parser("up", help="Tüm servisleri arka planda başlat")
    up_p.add_argument("--web", action="store_true", help="Web arayüzünü başlat (vite :5173)")
    up_p.add_argument("--tray", action="store_true", help="Menü bar uygulamasını başlat (macOS)")
    up_p.add_argument("--all", action="store_true", help="Core + web + tray")

    sub.add_parser("down", help="Tüm yönetilen servisleri durdur")
    sub.add_parser("status", help="Servis durumunu göster")

    restart_p = sub.add_parser("restart", help="down → up")
    restart_p.add_argument("--web", action="store_true")
    restart_p.add_argument("--tray", action="store_true")
    restart_p.add_argument("--all", action="store_true")

    args = parser.parse_args()

    if args.command == "server":
        from core.main import run_server

        run_server()
    elif args.command == "test-vad":
        _test_vad()
    elif args.command == "doctor":
        from core.supervisor import print_doctor, run_doctor

        sys.exit(print_doctor(run_doctor()))
    elif args.command == "up":
        from core.supervisor import run_up

        run_up(web=args.web or args.all, tray=args.tray or args.all)
    elif args.command == "down":
        from core.supervisor import run_down

        run_down()
    elif args.command == "status":
        from core.supervisor import run_status

        run_status()
    elif args.command == "restart":
        from core.supervisor import run_restart

        run_restart(web=args.web or args.all, tray=args.tray or args.all)
    else:
        parser.print_help()


def _test_vad():
    import time

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
