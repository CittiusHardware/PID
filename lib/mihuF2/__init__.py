# mihuF2/__init__.py
# Biblioteca única para sensores F2 de cor e ultrassônico.
#
# Uso:
#     from mihuF2 import *
#
#     print(p1.idF2())
#     print(p1.readColor(REFLECTION))
#     print(p1.readUltra(CM))

from mihu_hw import (
    P1,
    P2,
    P3,
    M1,
    M2,
    M3,
    M4,
)

import cor_sensor
import ultra

try:
    from time import (
        ticks_ms,
        ticks_diff,
        sleep_ms,
    )
except ImportError:
    # Compatibilidade para validação fora do MicroPython.
    import time as _time

    def ticks_ms():
        return int(
            _time.monotonic() * 1000
        )

    def ticks_diff(now, before):
        return now - before

    def sleep_ms(milliseconds):
        _time.sleep(
            milliseconds / 1000
        )


# Intervalo mínimo seguro entre leituras completas de cor.
COLOR_INTERVAL_MS = 100


# ============================================================
# IDENTIFICAÇÃO DOS SENSORES
# ============================================================

F2_COLOR = "COLOR"
F2_ULTRA = "ULTRA"
F2_NONE = "NONE"


# ============================================================
# MODOS DO SENSOR DE COR
# ============================================================

COLOR = cor_sensor.COR
NAME = 100
REFLECTION = cor_sensor.REFLEXAO
AMBIENT = cor_sensor.AMBIENTE

RED = cor_sensor.R
GREEN = cor_sensor.G
BLUE = cor_sensor.B

CODE = COLOR
COLOR_CODE = COLOR


# Compatibilidade em português.
COR = COLOR
NOME = NAME
REFLEXAO = REFLECTION
AMBIENTE = AMBIENT

R = RED
G = GREEN
B = BLUE


_COLOR_NATIVE_MODES = (
    COLOR,
    REFLECTION,
    AMBIENT,
    RED,
    GREEN,
    BLUE,
)

_COLOR_VALID_MODES = _COLOR_NATIVE_MODES + (
    NAME,
)


# ============================================================
# UNIDADES DO SENSOR ULTRASSÔNICO
# ============================================================

CM = ultra.CM
MM = ultra.MM
INCH = ultra.INCH

CENTIMETER = CM
MILLIMETER = MM

CENTIMETERS = CM
MILLIMETERS = MM
INCHES = INCH


_ULTRA_VALID_UNITS = (
    CM,
    MM,
    INCH,
)


# ============================================================
# FUNÇÕES NATIVAS
# ============================================================

_COLOR_READ_COMPLETE = getattr(
    cor_sensor,
    "readColor",
    None,
)

_COLOR_READ_STEP = getattr(
    cor_sensor,
    "getColor",
    getattr(
        cor_sensor,
        "getCorF2",
        None,
    ),
)


if (
    _COLOR_READ_COMPLETE is None
    and _COLOR_READ_STEP is None
):
    raise ImportError(
        "cor_sensor nao possui readColor, "
        "getColor ou getCorF2"
    )


if not hasattr(
    ultra,
    "get",
):
    raise ImportError(
        "O modulo ultra nao possui get"
    )


# ============================================================
# PORTA F2
# ============================================================

class F2Port:
    """
    Uma única porta com todos os métodos F2.

    Métodos:
        idF2()
        readColor()
        readUltra()
    """

    def __init__(
        self,
        hardware_port,
        name,
    ):
        self._hardware_port = hardware_port
        self.name = name

        # Controle interno da frequência de leitura do sensor
        # de cor. O código do aluno não precisa usar sleep().
        self._last_color_ms = None

    @property
    def port(self):
        return self._hardware_port

    # --------------------------------------------------------
    # SENSOR DE COR
    # --------------------------------------------------------

    def _waitColorInterval(self):
        """
        Garante o intervalo mínimo exigido pelo sensor.

        A espera ocorre apenas quando a leitura anterior foi
        recente. Se o programa do aluno já esperou tempo
        suficiente, não há atraso adicional.
        """

        if self._last_color_ms is None:
            return

        elapsed = ticks_diff(
            ticks_ms(),
            self._last_color_ms,
        )

        remaining = (
            COLOR_INTERVAL_MS
            - elapsed
        )

        if remaining > 0:
            sleep_ms(
                remaining
            )

    def _readColorNative(
        self,
        mode,
    ):
        """
        Usa uma leitura completa quando o firmware possui
        readColor(). No firmware antigo, completa as três
        etapas de getColor().
        """

        self._waitColorInterval()

        if _COLOR_READ_COMPLETE is not None:
            value = _COLOR_READ_COMPLETE(
                self._hardware_port,
                mode,
            )

        else:
            value = 0

            # O firmware atual completa a leitura em três
            # chamadas consecutivas na mesma porta.
            for _ in range(3):
                value = _COLOR_READ_STEP(
                    self._hardware_port,
                    mode,
                )

        # Marca o instante em que a transação foi concluída.
        self._last_color_ms = ticks_ms()

        return int(value)

    def readColor(
        self,
        mode=COLOR,
    ):
        """
        Modos:
            COLOR
            NAME
            REFLECTION
            AMBIENT
            RED
            GREEN
            BLUE
        """

        if mode not in _COLOR_VALID_MODES:
            raise ValueError(
                "Invalid color mode"
            )

        if mode == NAME:
            code = self._readColorNative(
                COLOR
            )

            return cor_sensor.getColorName(
                code
            )

        return self._readColorNative(
            mode
        )

    def readColorName(self):
        return self.readColor(
            NAME
        )

    # --------------------------------------------------------
    # SENSOR ULTRASSÔNICO
    # --------------------------------------------------------

    def readUltra(
        self,
        unit=CM,
    ):
        """
        Unidades:
            CM
            MM
            INCH
        """

        if unit not in _ULTRA_VALID_UNITS:
            raise ValueError(
                "Invalid ultrasonic unit"
            )

        return int(
            ultra.get(
                self._hardware_port,
                unit,
            )
        )

    def readDistance(
        self,
        unit=CM,
    ):
        return self.readUltra(
            unit
        )

    def distance(
        self,
        unit=CM,
    ):
        return self.readUltra(
            unit
        )

    # --------------------------------------------------------
    # IDENTIFICAÇÃO AUTOMÁTICA
    # --------------------------------------------------------

    def _colorResponds(self):
        """
        Procura uma resposta coerente do sensor de cor.

        São testados vários canais porque COLOR pode retornar
        zero quando nenhuma cor é reconhecida.
        """

        try:
            color_code = self._readColorNative(
                COLOR
            )

            reflection = self._readColorNative(
                REFLECTION
            )

            ambient = self._readColorNative(
                AMBIENT
            )

            red = self._readColorNative(
                RED
            )

            green = self._readColorNative(
                GREEN
            )

            blue = self._readColorNative(
                BLUE
            )

        except Exception:
            return False

        if 1 <= color_code <= 7:
            return True

        values = (
            reflection,
            ambient,
            red,
            green,
            blue,
        )

        for value in values:
            if value > 0:
                return True

        return False

    def _ultraResponds(self):
        """
        O driver nativo retorna zero quando não recebe uma
        distância válida.
        """

        try:
            first = int(
                ultra.get(
                    self._hardware_port,
                    CM,
                )
            )

            second = int(
                ultra.get(
                    self._hardware_port,
                    CM,
                )
            )

        except Exception:
            return False

        return (
            first > 0
            or second > 0
        )

    def idF2(self):
        """
        Retorna:
            "COLOR"
            "ULTRA"
            "NONE"

        A detecção testa primeiro o protocolo de cor e depois
        o protocolo ultrassônico.
        """

        if self._colorResponds():
            return F2_COLOR

        if self._ultraResponds():
            return F2_ULTRA

        return F2_NONE

    def __repr__(self):
        return "F2Port({})".format(
            self.name
        )


# ============================================================
# PORTAS
# ============================================================

p1 = F2Port(P1, "P1")
p2 = F2Port(P2, "P2")
p3 = F2Port(P3, "P3")

# Prefixo sensor_ evita conflito com motores m1...m4.
sensor_m1 = F2Port(M1, "M1")
sensor_m2 = F2Port(M2, "M2")
sensor_m3 = F2Port(M3, "M3")
sensor_m4 = F2Port(M4, "M4")


__all__ = (
    "F2Port",
    "p1",
    "p2",
    "p3",
    "sensor_m1",
    "sensor_m2",
    "sensor_m3",
    "sensor_m4",

    "F2_COLOR",
    "F2_ULTRA",
    "F2_NONE",

    "COLOR_INTERVAL_MS",

    "COLOR",
    "NAME",
    "REFLECTION",
    "AMBIENT",
    "RED",
    "GREEN",
    "BLUE",
    "CODE",
    "COLOR_CODE",

    "COR",
    "NOME",
    "REFLEXAO",
    "AMBIENTE",
    "R",
    "G",
    "B",

    "CM",
    "MM",
    "INCH",
    "CENTIMETER",
    "MILLIMETER",
    "CENTIMETERS",
    "MILLIMETERS",
    "INCHES",
)
