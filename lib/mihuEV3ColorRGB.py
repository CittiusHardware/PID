# ============================================================
# mihuEV3ColorRGB.py
#
# TESTE SEPARADO
#
# Sensor LEGO EV3 Color
# RGB-RAW
#
# NÃO altera:
#
# - mihuSensor3
# - color.py
# - constants.py
# - mihuSensorAPI
# ============================================================

from time import (
    sleep_ms,
    ticks_ms,
    ticks_diff,
)


# ============================================================
# SENSOR
# ============================================================

TYPE_COLOR = 29


# ============================================================
# MODOS EV3 COLOR
# ============================================================

COL_REFLECT = 0
COL_AMBIENT = 1
COL_COLOR = 2

REF_RAW = 3
RGB_RAW = 4
COL_CAL = 5


# ============================================================
# AUXILIAR
# ============================================================

def _to_int(valor):

    return int(
        round(
            valor
        )
    )


# ============================================================
# ESPERA O SENSOR FICAR REALMENTE PRONTO
#
# IMPORTANTE:
#
# TYPE 29 recebido
#
# NÃO significa ainda:
#
# UART pronta
#
# Precisamos esperar:
#
# TYPE
#  ↓
# ACK
#  ↓
# mudança 2400 -> 57600
#  ↓
# DATA MODE
#  ↓
# READY
# ============================================================

def waitReady(
    porta,
    timeout_ms=5000
):

    inicio = ticks_ms()


    while ticks_diff(
        ticks_ms(),
        inicio
    ) < timeout_ms:


        # ----------------------------------------------------
        # Continua avançando o protocolo.
        # ----------------------------------------------------

        porta.service_update()


        # ----------------------------------------------------
        # Primeiro confirma TYPE.
        # ----------------------------------------------------

        try:

            tipo = (
                porta.get_uart_type()
            )

        except Exception:

            tipo = -1


        # ----------------------------------------------------
        # Depois confirma READY.
        # ----------------------------------------------------

        if tipo == TYPE_COLOR:

            try:

                if porta.is_uart_ready():

                    return True

            except Exception:

                pass


        sleep_ms(1)


    return False


# ============================================================
# VERIFICA SE ESTÁ PRONTO
# ============================================================

def isReady(
    porta
):

    try:

        return (
            porta.get_uart_type()
            == TYPE_COLOR

            and

            porta.is_uart_ready()
        )

    except Exception:

        return False


# ============================================================
# RGB
# ============================================================

def getRGB(
    porta,
    timeout_ms=3000
):

    # --------------------------------------------------------
    # Se o sensor ainda estiver terminando handshake,
    # espera.
    # --------------------------------------------------------

    if not isReady(
        porta
    ):

        if not waitReady(
            porta,
            timeout_ms=5000
        ):

            raise OSError(
                "EV3 Color: sensor nao ficou pronto"
            )


    # --------------------------------------------------------
    # Solicita modo 4 = RGB-RAW
    # --------------------------------------------------------

    valores = porta.read_uart_mode(
        TYPE_COLOR,
        RGB_RAW,
        timeout_ms=timeout_ms
    )


    if valores is None:

        raise OSError(
            "EV3 Color: sem dados RGB"
        )


    if len(valores) < 3:

        raise OSError(
            "EV3 Color: RGB incompleto"
        )


    r = _to_int(
        valores[0]
    )


    g = _to_int(
        valores[1]
    )


    b = _to_int(
        valores[2]
    )


    return (
        r,
        g,
        b
    )


# ============================================================
# RGB RAW COMPLETO
#
# Vamos deixar isso disponível para descobrir quantos
# elementos o sensor físico está realmente entregando.
# ============================================================

def getRGBRaw(
    porta,
    timeout_ms=3000
):

    if not isReady(
        porta
    ):

        if not waitReady(
            porta,
            timeout_ms=5000
        ):

            raise OSError(
                "EV3 Color: sensor nao ficou pronto"
            )


    valores = porta.read_uart_mode(
        TYPE_COLOR,
        RGB_RAW,
        timeout_ms=timeout_ms
    )


    if valores is None:

        raise OSError(
            "EV3 Color: sem RGB RAW"
        )


    resultado = []


    for valor in valores:

        resultado.append(
            _to_int(
                valor
            )
        )


    return tuple(
        resultado
    )


# ============================================================
# CLASSE
# ============================================================

class EV3ColorRGB:


    def __init__(
        self,
        porta
    ):

        self.porta = porta

        self.red = 0

        self.green = 0

        self.blue = 0

        self.raw = ()

        self.ready = False


    # ========================================================
    # ESPERA PRONTO
    # ========================================================

    def begin(
        self,
        timeout_ms=5000
    ):

        self.ready = waitReady(
            self.porta,
            timeout_ms
        )


        return self.ready


    # ========================================================
    # ESTÁ PRONTO?
    # ========================================================

    def isReady(self):

        self.ready = isReady(
            self.porta
        )


        return self.ready


    # ========================================================
    # ATUALIZA
    # ========================================================

    def update(
        self,
        timeout_ms=3000
    ):

        valores = self.porta.read_uart_mode(
            TYPE_COLOR,
            RGB_RAW,
            timeout_ms=timeout_ms
        )


        if valores is None:

            raise OSError(
                "EV3 Color: sem RGB"
            )


        if len(valores) < 3:

            raise OSError(
                "EV3 Color: pacote RGB incompleto"
            )


        self.red = _to_int(
            valores[0]
        )


        self.green = _to_int(
            valores[1]
        )


        self.blue = _to_int(
            valores[2]
        )


        raw = []


        for valor in valores:

            raw.append(
                _to_int(
                    valor
                )
            )


        self.raw = tuple(
            raw
        )


        self.ready = True


        return (
            self.red,
            self.green,
            self.blue
        )


    # ========================================================
    # GET
    # ========================================================

    def get(
        self,
        timeout_ms=3000
    ):

        if not self.isReady():

            if not self.begin(
                timeout_ms=5000
            ):

                raise OSError(
                    "EV3 Color: nao ficou pronto"
                )


        return self.update(
            timeout_ms
        )


    # ========================================================
    # VALORES
    # ========================================================

    def getRed(self):

        return self.red


    def getGreen(self):

        return self.green


    def getBlue(self):

        return self.blue


    def getRaw(self):

        return self.raw


    # ========================================================
    # INFO
    # ========================================================

    def info(self):

        return {

            "ready":
                self.ready,

            "red":
                self.red,

            "green":
                self.green,

            "blue":
                self.blue,

            "raw":
                self.raw,
        }