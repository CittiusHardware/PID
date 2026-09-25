import sys

try:
    import uselect as select
except ImportError:
    import select

try:
    import ujson as json
except ImportError:
    import json


class SerialCommands:
    def __init__(self):
        self.poll = None

        try:
            self.poll = select.poll()
            self.poll.register(
                sys.stdin,
                select.POLLIN,
            )
        except Exception:
            self.poll = None

    def read(self):
        if self.poll is None:
            return None

        try:
            if not self.poll.poll(0):
                return None

            line = sys.stdin.readline()

        except Exception:
            return None

        if line is None:
            return None

        text = str(line).strip()

        if not text:
            return None

        # Compatibilidade com Electron que pode enviar
        # JSON.stringify("RUN_TEST:RFID").
        try:
            data = json.loads(text)

            if isinstance(data, str):
                return data.strip()

            if isinstance(data, dict):
                return data

        except Exception:
            pass

        return text
