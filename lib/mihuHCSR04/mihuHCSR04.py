# ============================================================
# lib/mihuHCSR04/mihuHCSR04.py
# Driver MicroPython para HC-SR04
#
# Portas MIHU:
#   P1 -> ECHO 18, TRIGGER 44
#   P2 -> ECHO 15, TRIGGER 16
#   P3 -> ECHO 17, TRIGGER 43
#   M1 -> ECHO 11, TRIGGER 41
#   M2 -> ECHO 12, TRIGGER 47
#   M3 -> ECHO 13, TRIGGER 42
#   M4 -> ECHO 14, TRIGGER 45
#
# Uso por porta:
#
#   from lib.mihuHCSR04 import hcsr04
#
#   hcsr04.begin(porta="P1")
#   print(hcsr04.readCM())
#
# Uso por pinos:
#
#   hcsr04.begin(
#       echo=18,
#       trigger=44
#   )
#
#   print(hcsr04.readMM())
# ============================================================

from machine import Pin, time_pulse_us
import time


VERSION = "1.0.0"


PORTAS = {
    "P1": (44, 18),
    "P2": (16, 15),
    "P3": (17, 43),
    "M1": (11, 41),
    "M2": (12, 47),
    "M3": (13, 42),
    "M4": (14, 45),
}


DEFAULT_TIMEOUT_US = 30000
DEFAULT_MIN_INTERVAL_MS = 60


class MihuHCSR04:
    """
    Driver HC-SR04 para MicroPython.

    A inicialização dos GPIO acontece uma única vez em begin().

    Depois disso:
        hcsr04.readCM()
        hcsr04.readMM()
        hcsr04.read("cm")
        hcsr04.read("mm")
    """

    def __init__(self):
        self.echo_pin = None
        self.trigger_pin = None

        self.echo_gpio = None
        self.trigger_gpio = None

        self.porta = None
        self.initialized = False

        self.timeout_us = DEFAULT_TIMEOUT_US
        self.min_interval_ms = DEFAULT_MIN_INTERVAL_MS

        self.last_read_ms = None
        self.last_pulse_us = None
        self.last_value_mm = None
        self.last_error = None


    # ========================================================
    # INICIALIZAÇÃO
    # ========================================================

    def begin(
        self,
        porta=None,
        echo=None,
        trigger=None,
        timeout_us=DEFAULT_TIMEOUT_US,
        min_interval_ms=DEFAULT_MIN_INTERVAL_MS,
        echo_pull=None,
    ):
        """
        Inicializa o HC-SR04 uma única vez.

        Opção 1 - usando uma porta MIHU:

            hcsr04.begin(
                porta="P1"
            )

        Opção 2 - usando pinos diretamente:

            hcsr04.begin(
                echo=18,
                trigger=44
            )

        Se 'porta' for informada, ela tem prioridade sobre
        os parâmetros echo/trigger.
        """

        self.timeout_us = int(timeout_us)
        self.min_interval_ms = max(
            0,
            int(min_interval_ms)
        )

        self.last_read_ms = None
        self.last_pulse_us = None
        self.last_value_mm = None
        self.last_error = None


        # ----------------------------------------------------
        # Seleção por porta
        # ----------------------------------------------------

        if porta is not None:

            nome = str(
                porta
            ).strip().upper()

            if nome not in PORTAS:
                raise ValueError(
                    "Porta invalida. Use P1, P2, P3, "
                    "M1, M2, M3 ou M4."
                )

            echo, trigger = PORTAS[
                nome
            ]

            self.porta = nome


        # ----------------------------------------------------
        # Seleção manual de GPIO
        # ----------------------------------------------------

        else:

            if (
                echo is None
                or trigger is None
            ):
                raise ValueError(
                    "Informe porta='P1' ou os pinos "
                    "echo=... e trigger=..."
                )

            echo = int(echo)
            trigger = int(trigger)

            if echo == trigger:
                raise ValueError(
                    "ECHO e TRIGGER devem usar GPIO diferentes."
                )

            self.porta = None


        self.echo_pin = int(
            echo
        )

        self.trigger_pin = int(
            trigger
        )


        # ----------------------------------------------------
        # Configuração física
        # ----------------------------------------------------

        if echo_pull is None:

            self.echo_gpio = Pin(
                self.echo_pin,
                Pin.IN
            )

        elif str(
            echo_pull
        ).strip().upper() in (
            "UP",
            "PULL_UP",
        ):

            self.echo_gpio = Pin(
                self.echo_pin,
                Pin.IN,
                Pin.PULL_UP
            )

        elif str(
            echo_pull
        ).strip().upper() in (
            "DOWN",
            "PULL_DOWN",
        ):

            self.echo_gpio = Pin(
                self.echo_pin,
                Pin.IN,
                Pin.PULL_DOWN
            )

        else:
            raise ValueError(
                "echo_pull deve ser None, 'UP' ou 'DOWN'."
            )


        self.trigger_gpio = Pin(
            self.trigger_pin,
            Pin.OUT,
            value=0
        )


        # Garante TRIGGER inicialmente em LOW.
        self.trigger_gpio.value(
            0
        )

        time.sleep_us(
            5
        )

        self.initialized = True

        return True


    # ========================================================
    # DISPARO / MEDIÇÃO
    # ========================================================

    def _trigger(self):

        self.trigger_gpio.value(
            0
        )

        time.sleep_us(
            2
        )

        self.trigger_gpio.value(
            1
        )

        time.sleep_us(
            10
        )

        self.trigger_gpio.value(
            0
        )


    def _read_pulse(self):
        """
        Gera o pulso TRIGGER e mede a duração HIGH do ECHO.

        Retorna duração em microssegundos.
        """

        if not self.initialized:
            raise RuntimeError(
                "HC-SR04 nao iniciado. Use hcsr04.begin()."
            )


        # ----------------------------------------------------
        # Intervalo mínimo entre disparos
        # ----------------------------------------------------

        agora = time.ticks_ms()

        if (
            self.last_read_ms is not None
            and self.min_interval_ms > 0
            and time.ticks_diff(
                agora,
                self.last_read_ms
            ) < self.min_interval_ms
        ):
            return self.last_pulse_us


        self._trigger()


        try:

            pulse = time_pulse_us(
                self.echo_gpio,
                1,
                self.timeout_us
            )


            # MicroPython pode retornar valor negativo em timeout.
            if pulse < 0:
                raise OSError(
                    "Timeout ECHO: {}".format(
                        pulse
                    )
                )


            self.last_pulse_us = int(
                pulse
            )

            self.last_read_ms = (
                time.ticks_ms()
            )

            self.last_error = None

            return self.last_pulse_us


        except Exception as error:

            self.last_error = error
            self.last_read_ms = (
                time.ticks_ms()
            )

            return None


    # ========================================================
    # CONVERSÃO
    # ========================================================

    @staticmethod
    def _pulse_to_mm(
        pulse_us
    ):
        """
        Distância baseada na velocidade do som ~343 m/s.

        ida + volta:
            mm = pulse_us * 0.343 / 2

        Equivalente:
            mm = pulse_us * 343 / 2000
        """

        if pulse_us is None:
            return None

        return (
            int(
                (
                    int(pulse_us)
                    * 343
                    + 1000
                )
                // 2000
            )
        )


    @staticmethod
    def _convert(
        value_mm,
        unit
    ):

        if value_mm is None:
            return None

        unit = str(
            unit
        ).strip().lower()

        if unit in (
            "mm",
            "milimetro",
            "milimetros",
        ):
            return int(
                value_mm
            )

        if unit in (
            "cm",
            "centimetro",
            "centimetros",
        ):
            return round(
                value_mm / 10.0,
                1
            )

        raise ValueError(
            "Unidade deve ser 'cm' ou 'mm'."
        )


    # ========================================================
    # API PÚBLICA
    # ========================================================

    def read(
        self,
        unit="cm"
    ):
        """
        Lê a distância.

        Padrão:
            hcsr04.read()       -> cm

        Também:
            hcsr04.read("cm")
            hcsr04.read("mm")
        """

        pulse = self._read_pulse()

        if pulse is not None:

            value_mm = (
                self._pulse_to_mm(
                    pulse
                )
            )

            self.last_value_mm = (
                value_mm
            )


        return self._convert(
            self.last_value_mm,
            unit
        )


    def readCM(self):
        """
        Retorna a distância em centímetros.
        """

        return self.read(
            "cm"
        )


    def readMM(self):
        """
        Retorna a distância em milímetros.
        """

        return self.read(
            "mm"
        )


    def getLastPulseUS(self):
        """
        Retorna a duração do último ECHO em microssegundos.
        """

        return self.last_pulse_us


    def info(self):

        return {
            "version": VERSION,
            "initialized": self.initialized,
            "porta": self.porta,
            "echo": self.echo_pin,
            "trigger": self.trigger_pin,
            "timeout_us": self.timeout_us,
            "min_interval_ms": self.min_interval_ms,
            "last_pulse_us": self.last_pulse_us,
            "last_value_mm": self.last_value_mm,
            "last_value_cm": (
                None
                if self.last_value_mm is None
                else round(
                    self.last_value_mm / 10.0,
                    1
                )
            ),
            "last_error": self.last_error,
        }


# ============================================================
# Instância global
# ============================================================

hcsr04 = MihuHCSR04()
