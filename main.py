MODE_FILE = "/boot_mode.txt"


def _load_mode():
    try:
        with open(MODE_FILE, "r") as file:
            mode = file.read().strip().upper()

        if mode in ("TEST", "APP"):
            return mode

    except Exception:
        pass

    return "TEST"


mode = _load_mode()

if mode == "TEST":
    from mihuTest.main import run
else:
    from app.main import run

run()
