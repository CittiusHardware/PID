"""
lightSensor.py

Biblioteca educacional para dois sensores BH1750.

Importação:
    from lightSensor import lux1, lux2, light

Uso:
    print(lux1.read())
    print(lux2.read())

A biblioteca não inicializa o I2C durante a importação.
A primeira chamada de read(), available(), reset() ou scan()
faz a inicialização automaticamente.

Configuração padrão MIHU-S3:
    I2C:  0
    SDA:  GPIO 39
    SCL:  GPIO 40
    Freq: 400 kHz

Sensores:
    lux1: endereço 0x5C
    lux2: endereço 0x23
"""

from machine import I2C, Pin
import time


VERSION = "1.0.0"

DEFAULT_I2C_ID = 0
DEFAULT_SDA = 39
DEFAULT_SCL = 40
DEFAULT_FREQUENCY = 400000

LUX1_ADDRESS = 0x5C
LUX2_ADDRESS = 0x23

POWER_DOWN = 0x00
POWER_ON = 0x01
RESET = 0x07

CONTINUOUS_HIGH_RESOLUTION = 0x10
CONTINUOUS_HIGH_RESOLUTION_2 = 0x11
CONTINUOUS_LOW_RESOLUTION = 0x13

ONE_TIME_HIGH_RESOLUTION = 0x20
ONE_TIME_HIGH_RESOLUTION_2 = 0x21
ONE_TIME_LOW_RESOLUTION = 0x23

DEFAULT_MODE = CONTINUOUS_HIGH_RESOLUTION

STARTUP_TIME_MS = 180
RECONNECT_INTERVAL_MS = 500


_MODE_NAMES = {
    "high": CONTINUOUS_HIGH_RESOLUTION,
    "alta": CONTINUOUS_HIGH_RESOLUTION,
    "high2": CONTINUOUS_HIGH_RESOLUTION_2,
    "alta2": CONTINUOUS_HIGH_RESOLUTION_2,
    "low": CONTINUOUS_LOW_RESOLUTION,
    "baixa": CONTINUOUS_LOW_RESOLUTION,
    "one_high": ONE_TIME_HIGH_RESOLUTION,
    "unica_alta": ONE_TIME_HIGH_RESOLUTION,
    "one_high2": ONE_TIME_HIGH_RESOLUTION_2,
    "unica_alta2": ONE_TIME_HIGH_RESOLUTION_2,
    "one_low": ONE_TIME_LOW_RESOLUTION,
    "unica_baixa": ONE_TIME_LOW_RESOLUTION,
}

_MODE_LABELS = {
    CONTINUOUS_HIGH_RESOLUTION: "high",
    CONTINUOUS_HIGH_RESOLUTION_2: "high2",
    CONTINUOUS_LOW_RESOLUTION: "low",
    ONE_TIME_HIGH_RESOLUTION: "one_high",
    ONE_TIME_HIGH_RESOLUTION_2: "one_high2",
    ONE_TIME_LOW_RESOLUTION: "one_low",
}


class LightBus:
    """
    Barramento I2C compartilhado.

    O I2C é criado sob demanda. O aluno normalmente não precisa
    manipular este objeto diretamente.
    """

    def __init__(
        self,
        i2c_id=DEFAULT_I2C_ID,
        sda=DEFAULT_SDA,
        scl=DEFAULT_SCL,
        frequency=DEFAULT_FREQUENCY,
    ):
        self._i2c_id = int(i2c_id)
        self._sda = int(sda)
        self._scl = int(scl)
        self._frequency = int(frequency)

        self._i2c = None
        self._available = False
        self._last_error = None
        self._generation = 0

    def _start(self):
        if self._i2c is not None:
            return True

        try:
            self._i2c = I2C(
                self._i2c_id,
                sda=Pin(self._sda),
                scl=Pin(self._scl),
                freq=self._frequency,
            )

            self._available = True
            self._last_error = None
            self._generation += 1
            return True

        except Exception as error:
            self._i2c = None
            self._available = False
            self._last_error = error
            return False

    # Compatibilidade com códigos anteriores.
    def begin(self):
        return self._start()

    def use(self, i2c):
        """
        Usa um I2C já criado.

        Não é necessário para o uso comum.
        """

        if i2c is None:
            raise ValueError(
                "O objeto I2C nao pode ser None."
            )

        self._i2c = i2c
        self._available = True
        self._last_error = None
        self._generation += 1
        return True

    def set(
        self,
        i2c_id=None,
        sda=None,
        scl=None,
        frequency=None,
    ):
        """
        Altera a configuração do barramento.

        A nova configuração será aplicada na próxima operação.
        """

        if i2c_id is not None:
            self._i2c_id = int(i2c_id)

        if sda is not None:
            self._sda = int(sda)

        if scl is not None:
            self._scl = int(scl)

        if frequency is not None:
            self._frequency = int(frequency)

        self._i2c = None
        self._available = False
        self._generation += 1
        return True

    def config(
        self,
        i2c_id=None,
        sda=None,
        scl=None,
        frequency=None,
    ):
        """
        Compatibilidade: consulta ou altera a configuração.
        """

        if (
            i2c_id is None
            and sda is None
            and scl is None
            and frequency is None
        ):
            return self.info()

        return self.set(
            i2c_id=i2c_id,
            sda=sda,
            scl=scl,
            frequency=frequency,
        )

    def scan(self):
        if not self._start():
            return []

        try:
            addresses = self._i2c.scan()
            self._available = True
            self._last_error = None
            return addresses

        except Exception as error:
            self._available = False
            self._last_error = error
            return []

    def available(self):
        return self._start()

    def i2c(self):
        if not self._start():
            return None

        return self._i2c

    def lastError(self):
        return self._last_error

    def info(self):
        return {
            "i2c_id": self._i2c_id,
            "sda": self._sda,
            "scl": self._scl,
            "frequency": self._frequency,
            "started": self._i2c is not None,
            "available": self._available,
        }


class LightSensor:
    """
    Um sensor de luminosidade BH1750.

    API educacional:
        lux1.read()
        lux1.set("high")
        lux1.reset()
        lux1.available()
        lux1.info()
    """

    def __init__(
        self,
        bus,
        address,
        name="lux",
        mode=DEFAULT_MODE,
    ):
        self._bus = bus
        self._address = int(address)
        self._name = str(name)
        self._mode = int(mode)

        self._started = False
        self._bus_generation = -1
        self._connected = False
        self._last_error = None

        self._last_value = 0
        self._last_float = 0.0
        self._last_raw = 0

        self._started_ms = 0
        self._last_attempt_ms = -RECONNECT_INTERVAL_MS

    def _resolve_mode(self, mode):
        if isinstance(mode, str):
            key = mode.strip().lower()

            if key not in _MODE_NAMES:
                raise ValueError(
                    "Modo invalido. Use high, high2, low, "
                    "one_high, one_high2 ou one_low."
                )

            return _MODE_NAMES[key]

        mode = int(mode)

        if mode not in _MODE_LABELS:
            raise ValueError(
                "Comando de modo BH1750 invalido."
            )

        return mode

    def _start(self, force=False):
        now = time.ticks_ms()

        same_bus = (
            self._bus_generation
            == self._bus._generation
        )

        if (
            self._started
            and self._connected
            and same_bus
            and not force
        ):
            return True

        if not force:
            elapsed = time.ticks_diff(
                now,
                self._last_attempt_ms,
            )

            if (
                elapsed < RECONNECT_INTERVAL_MS
                and not self._connected
            ):
                return False

        self._last_attempt_ms = now
        i2c = self._bus.i2c()

        if i2c is None:
            self._started = False
            self._connected = False
            self._last_error = (
                self._bus.lastError()
            )
            return False

        try:
            i2c.writeto(
                self._address,
                bytes((POWER_ON,)),
            )
            i2c.writeto(
                self._address,
                bytes((self._mode,)),
            )

            self._started = True
            self._connected = True
            self._last_error = None
            self._started_ms = time.ticks_ms()
            self._bus_generation = (
                self._bus._generation
            )
            return True

        except Exception as error:
            self._started = False
            self._connected = False
            self._last_error = error
            return False

    # Compatibilidade com códigos anteriores.
    def begin(self, force=False):
        return self._start(force=force)

    def _wait_first_measurement(self):
        elapsed = time.ticks_diff(
            time.ticks_ms(),
            self._started_ms,
        )

        remaining = STARTUP_TIME_MS - elapsed

        if remaining > 0:
            time.sleep_ms(remaining)

    def _read_measurement(self):
        if not self._start():
            return None

        self._wait_first_measurement()

        try:
            data = self._bus.i2c().readfrom(
                self._address,
                2,
            )

            if data is None or len(data) != 2:
                raise OSError(
                    "Resposta invalida do BH1750."
                )

            raw = (
                (int(data[0]) << 8)
                | int(data[1])
            )
            lux = raw / 1.2

            self._last_raw = raw
            self._last_float = lux
            self._last_value = int(lux + 0.5)

            self._connected = True
            self._last_error = None

            # Modos one-time desligam o sensor após a leitura.
            if self._mode in (
                ONE_TIME_HIGH_RESOLUTION,
                ONE_TIME_HIGH_RESOLUTION_2,
                ONE_TIME_LOW_RESOLUTION,
            ):
                self._started = False

            return lux, raw

        except Exception as error:
            self._started = False
            self._connected = False
            self._last_error = error
            return None

    def read(self):
        """
        Retorna a luminosidade em lux como inteiro.

        Se o sensor não responder, retorna 0.
        """

        result = self._read_measurement()

        if result is None:
            return 0

        lux, raw = result
        del raw
        return int(lux + 0.5)

    def readFloat(self, decimals=2):
        """
        Retorna a luminosidade com casas decimais.
        """

        result = self._read_measurement()

        if result is None:
            return 0.0

        lux, raw = result
        del raw
        return round(lux, int(decimals))

    def raw(self):
        """
        Retorna a leitura bruta de 16 bits.
        """

        result = self._read_measurement()

        if result is None:
            return 0

        lux, raw = result
        del lux
        return raw

    def set(self, mode="high"):
        """
        Define o modo de medição.

        Exemplos:
            lux1.set("high")
            lux1.set("low")
            lux1.set("one_high")
        """

        self._mode = self._resolve_mode(mode)
        self._started = False
        self._connected = False
        return True

    def reset(self):
        """
        Reinicia o sensor.
        """

        if not self._start(force=True):
            return False

        try:
            i2c = self._bus.i2c()

            i2c.writeto(
                self._address,
                bytes((RESET,)),
            )
            i2c.writeto(
                self._address,
                bytes((self._mode,)),
            )

            self._started = True
            self._connected = True
            self._started_ms = time.ticks_ms()
            self._last_error = None
            return True

        except Exception as error:
            self._started = False
            self._connected = False
            self._last_error = error
            return False

    def on(self):
        return self._start(force=True)

    def off(self):
        i2c = self._bus.i2c()

        if i2c is None:
            return False

        try:
            i2c.writeto(
                self._address,
                bytes((POWER_DOWN,)),
            )

            self._started = False
            self._connected = False
            self._last_error = None
            return True

        except Exception as error:
            self._started = False
            self._connected = False
            self._last_error = error
            return False

    def available(self):
        return self._start()

    def last(self):
        """
        Retorna o último valor válido sem nova leitura.
        """

        return self._last_value

    def address(self):
        return self._address

    def name(self):
        return self._name

    def mode(self):
        return self._mode

    def modeName(self):
        return _MODE_LABELS.get(
            self._mode,
            "unknown",
        )

    def lastError(self):
        return self._last_error

    def info(self):
        return {
            "library_version": VERSION,
            "name": self._name,
            "address": self._address,
            "address_hex": "0x{:02X}".format(
                self._address
            ),
            "mode": self._mode,
            "mode_name": self.modeName(),
            "started": self._started,
            "connected": self._connected,
            "last_value": self._last_value,
            "last_error": self._last_error,
        }

    # Compatibilidade com a biblioteca anterior.
    def get(self):
        return self.read()

    def getFloat(self, decimals=2):
        return self.readFloat(decimals)

    def value(self):
        return self.read()

    def connected(self):
        return self.available()

    def hexAddress(self):
        return "0x{:02X}".format(
            self._address
        )

    def powerOn(self):
        return self.on()

    def powerOff(self):
        return self.off()


class LightSensors:
    """
    Gerencia os dois sensores.

    API:
        light.read()
        light.average()
        light.difference()
        light.brighter()
    """

    def __init__(
        self,
        bus,
        sensor1,
        sensor2,
    ):
        self._bus = bus
        self.lux1 = sensor1
        self.lux2 = sensor2

    def read(self):
        """
        Retorna:
            (valor_lux1, valor_lux2)
        """

        return (
            self.lux1.read(),
            self.lux2.read(),
        )

    def average(self):
        value1, value2 = self.read()
        return int(
            ((value1 + value2) / 2) + 0.5
        )

    def difference(self):
        """
        Retorna lux1 - lux2.

        Positivo: lux1 está recebendo mais luz.
        Negativo: lux2 está recebendo mais luz.
        """

        value1, value2 = self.read()
        return value1 - value2

    def brighter(self, tolerance=5):
        """
        Retorna:
            "lux1"
            "lux2"
            "igual"
        """

        value1, value2 = self.read()
        tolerance = abs(int(tolerance))

        if value1 > value2 + tolerance:
            return "lux1"

        if value2 > value1 + tolerance:
            return "lux2"

        return "igual"

    def set(self, mode="high"):
        return (
            self.lux1.set(mode),
            self.lux2.set(mode),
        )

    def reset(self):
        return (
            self.lux1.reset(),
            self.lux2.reset(),
        )

    def available(self):
        return (
            self.lux1.available(),
            self.lux2.available(),
        )

    def scan(self):
        return self._bus.scan()

    def use(self, i2c):
        self._bus.use(i2c)

        self.lux1._started = False
        self.lux2._started = False
        self.lux1._connected = False
        self.lux2._connected = False
        return True

    def config(
        self,
        i2c_id=None,
        sda=None,
        scl=None,
        frequency=None,
    ):
        result = self._bus.set(
            i2c_id=i2c_id,
            sda=sda,
            scl=scl,
            frequency=frequency,
        )

        self.lux1._started = False
        self.lux2._started = False
        self.lux1._connected = False
        self.lux2._connected = False
        return result

    def info(self):
        return {
            "library_version": VERSION,
            "bus": self._bus.info(),
            "lux1": self.lux1.info(),
            "lux2": self.lux2.info(),
        }

    # Compatibilidade.
    def get(self):
        return self.read()

    def all(self):
        return self.read()

    def addresses(self):
        return (
            self.lux1.address(),
            self.lux2.address(),
        )


# Objetos globais. Nenhum acessa o hardware neste momento.
lightBus = LightBus()

lux1 = LightSensor(
    lightBus,
    LUX1_ADDRESS,
    name="lux1",
)

lux2 = LightSensor(
    lightBus,
    LUX2_ADDRESS,
    name="lux2",
)

light = LightSensors(
    lightBus,
    lux1,
    lux2,
)
