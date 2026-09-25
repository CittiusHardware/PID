from time import ticks_ms, ticks_diff, sleep_ms

# Segredo de produção:
# segure BACK durante o boot pelo tempo abaixo.
SECRET_HOLD_MS = 5000
MODE_FILE = "/boot_mode.txt"

try:
    from lib.mihuButton import readKey
except ImportError:
    try:
        from lib.mihuButton.mihuButton import readKey
    except ImportError:
        readKey = None


def _load_mode():
    try:
        with open(MODE_FILE, "r") as file:
            mode = file.read().strip().upper()

        if mode in ("TEST", "APP"):
            return mode

    except Exception:
        pass

    # Unidade de fábrica inicia em TEST.
    return "TEST"


def _save_mode(mode):
    try:
        with open(MODE_FILE, "w") as file:
            file.write(mode)
        return True
    except Exception:
        return False


def _secret_back_held():
    if readKey is None:
        return False

    started = None

    while True:
        key = readKey()
        now = ticks_ms()

        if key == "BACK":
            if started is None:
                started = now

            if ticks_diff(now, started) >= SECRET_HOLD_MS:
                # Espera soltar para não carregar a aplicação
                # já com BACK pressionado.
                while readKey() == "BACK":
                    sleep_ms(20)

                return True

        else:
            # Se não começou a segurar no início do boot,
            # não bloqueia a inicialização esperando 5 segundos.
            if started is None:
                return False

            started = None
            return False

        sleep_ms(20)


mode = _load_mode()

if _secret_back_held():
    mode = "APP" if mode == "TEST" else "TEST"
    _save_mode(mode)

# boot.py termina aqui. O main.py lê novamente o modo persistido.
