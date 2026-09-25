# ============================================================
# mihuSensorAPI.py
#
# API UNIFICADA DE SENSORES MIHU
#
# Portas:
#
#   P1
#   P2
#   P3
#   M1
#   M2
#   M3
#   M4
#
# Marcas:
#
#   EST
#   EV6
#   CITTIUS
#
#
# RECURSOS:
#
# - deteccao automatica
# - hot-plug
# - navegacao por portas
# - navegacao por modos
# - limite das 3 UARTs fisicas
# - sensor de toque 0 / 1
# - sensor de som
# - RGB EV6
# - RGB Cittius
# - RGB EV3 original opcional
# - inicializacao global uma unica vez
# - mantem sensor conectado ao entrar/sair da tela
#
#
# IMPORTANTE:
#
# sensores.begin()
#
# deve acontecer UMA VEZ na main.
#
# Depois:
#
# sensores.update()
#
# deve ser chamado continuamente.
#
# ============================================================


from machine import (
    Pin,
    SoftI2C,
)

import time


# ============================================================
# MIHU SENSOR 3
# ============================================================

try:

    from lib import mihuSensor3 as est

except Exception:

    import mihuSensor3 as est


# ============================================================
# HARDWARE F2 / EV6
# ============================================================

try:

    import mihu_hw

except Exception:

    try:

        from lib import mihu_hw

    except Exception:

        mihu_hw = None


# ============================================================
# SENSOR DE COR EV6
# ============================================================

try:

    import cor_sensor

except Exception:

    cor_sensor = None


# ============================================================
# ULTRASSONICO EV6
# ============================================================

try:

    import ultra

except Exception:

    ultra = None


# ============================================================
# VERSAO
# ============================================================

MIHU_SENSOR_API_VERSION = "1.1.0"


# ============================================================
# CONFIGURACAO EV3 RGB
# ============================================================
#
# O sensor EV3 original possui:
#
# modo 4 = RGB-RAW
#
# Porem a copia que estamos analisando:
#
# - anuncia modo 4
# - anuncia RGB-RAW
# - mas pode parar de transmitir ao selecionar modo 4
#
# Por seguranca deixamos False.
#
# Para testar SOMENTE o original:
#
# ENABLE_EST_RGB = True
#
# ============================================================

ENABLE_EST_RGB = False

EST_RGB_MODE = 4


# ============================================================
# STATUS
# ============================================================

STATUS_VAZIO = "VAZIO"

STATUS_IDENTIFICANDO = "IDENTIFICANDO"

STATUS_PRONTO = "PRONTO"

STATUS_ERRO = "ERRO"

STATUS_UART_LIMITE = "UART_LIMITE"


# ============================================================
# MARCAS
# ============================================================

MARCA_EST = "EST"

MARCA_EV6 = "EV6"

MARCA_CITTIUS = "CITTIUS"


# ============================================================
# SENSORES
# ============================================================

SENSOR_COR = "COR"

SENSOR_ULTRASONICO = "ULTRASONICO"

SENSOR_GIROSCOPIO = "GIROSCOPIO"

SENSOR_INFRAVERMELHO = "INFRAVERMELHO"

SENSOR_BOTAO = "BOTAO"

SENSOR_SOM = "SOM"

SENSOR_UART = "UART"


# ============================================================
# PROTOCOLOS
# ============================================================

PROTOCOLO_UART_EV3 = "UART_EV3"

PROTOCOLO_I2C = "I2C"

PROTOCOLO_ONEWIRE = "ONEWIRE"

PROTOCOLO_ADC = "ADC"


# ============================================================
# MODOS PADRONIZADOS
# ============================================================

MODE_COR = "COR"

MODE_REFLEXAO = "REFLEXAO"

MODE_AMBIENTE = "AMBIENTE"

MODE_RGB = "RGB"

MODE_CLEAR = "CLEAR"


MODE_CM = "CM"

MODE_MM = "MM"

MODE_INCH = "INCH"

MODE_ESCUTA = "ESCUTA"


MODE_ANGULO = "ANGULO"

MODE_VELOCIDADE = "VELOCIDADE"

MODE_ANGULO_VELOCIDADE = (
    "ANGULO_VELOCIDADE"
)


MODE_PROXIMIDADE = "PROXIMIDADE"

MODE_BUSCA = "BUSCA"

MODE_CONTROLE = "CONTROLE"


MODE_ESTADO = "ESTADO"

MODE_NIVEL = "NIVEL"


# ============================================================
# TEMPOS
# ============================================================

PRESENCE_CHECK_MS = 350


# ============================================================
# CITTIUS COLOR
# ============================================================

CITTIUS_COLOR_ADDR = 0x39

CITTIUS_COLOR_FREQ = 100000


# ============================================================
# CLASSIFICACAO CITTIUS COLOR
# ============================================================

BLACK_THRESHOLD = 30

WHITE_THRESHOLD = 100


CITTIUS_COLOR_NAMES = {

    1: "VERMELHO",

    2: "VERDE",

    3: "AZUL",

    4: "AMARELO",

    6: "BRANCO",

    7: "PRETO",

    8: "DESCONHECIDA",
}


# ============================================================
# MODO
#
# Estrutura:
#
# (
#     chave,
#     nome para tela,
#     unidade,
#     argumento do driver
# )
#
# ============================================================

def _mode(
    key,
    label,
    unit="",
    argument=None,
):

    return (
        key,
        label,
        unit,
        argument,
    )


# ============================================================
# DRIVER CITTIUS COLOR
# ============================================================

class CittiusColorDriver:


    def __init__(
        self,
        hardware_port,
    ):

        self.port = hardware_port

        self.i2c = None

        self.ready = False

        self.use_burst = True


    # ========================================================
    # CRIA I2C
    # ========================================================

    def _create_i2c(self):

        try:

            return SoftI2C(

                sda=Pin(
                    self.port.gpio_rx
                ),

                scl=Pin(
                    self.port.gpio_tx
                ),

                freq=CITTIUS_COLOR_FREQ,

                timeout=2000,
            )

        except TypeError:

            return SoftI2C(

                sda=Pin(
                    self.port.gpio_rx
                ),

                scl=Pin(
                    self.port.gpio_tx
                ),

                freq=CITTIUS_COLOR_FREQ,
            )


    # ========================================================
    # WRITE
    # ========================================================

    def _write(
        self,
        register,
        value,
    ):

        self.i2c.writeto_mem(

            CITTIUS_COLOR_ADDR,

            register,

            bytes((
                value & 0xFF,
            ))
        )


    # ========================================================
    # READ BYTE
    # ========================================================

    def _read(
        self,
        register,
    ):

        dados = self.i2c.readfrom_mem(

            CITTIUS_COLOR_ADDR,

            register,

            1,
        )


        if not dados:

            raise OSError(
                "Cittius Color sem resposta"
            )


        return dados[0]


    # ========================================================
    # BEGIN
    # ========================================================

    def begin(self):


        if (
            self.ready
            and self.i2c is not None
        ):

            return True


        try:

            self.i2c = (
                self._create_i2c()
            )


            # =================================================
            # IDENTIFICACAO
            # =================================================

            self._read(
                0x92
            )


            # =================================================
            # CONFIGURACAO ORIGINAL
            # =================================================

            self._write(
                0x81,
                0xFF
            )


            self._write(
                0x8F,
                0x02
            )


            self._write(
                0x80,
                0x0B
            )


            time.sleep_ms(
                3
            )


            self.ready = True


            return True


        except Exception:

            self.close()

            return False


    # ========================================================
    # PING
    # ========================================================

    def ping(self):


        try:

            if not self.begin():

                return False


            self._read(
                0x92
            )


            return True


        except Exception:

            return False


    # ========================================================
    # LEITURA BURST
    #
    # 0xB4:
    #
    # command bit
    # auto increment
    # registro 0x14
    #
    # retorna:
    #
    # clear low
    # clear high
    # red low
    # red high
    # green low
    # green high
    # blue low
    # blue high
    #
    # Mantemos LOW BYTE porque a classificacao antiga
    # da Cittius utiliza essa escala.
    # ========================================================

    def _read_rgb_burst(self):


        dados = self.i2c.readfrom_mem(

            CITTIUS_COLOR_ADDR,

            0xB4,

            8,
        )


        if len(dados) != 8:

            raise OSError(
                "RGB Cittius incompleto"
            )


        clear = dados[0]

        red = dados[2]

        green = dados[4]

        blue = dados[6]


        return (
            clear,
            red,
            green,
            blue,
        )


    # ========================================================
    # LEITURA INDIVIDUAL
    #
    # FALLBACK caso o bridge nao aceite burst.
    # ========================================================

    def _read_rgb_individual(self):


        clear = self._read(
            0x94
        )


        red = self._read(
            0x96
        )


        green = self._read(
            0x98
        )


        blue = self._read(
            0x9A
        )


        return (
            clear,
            red,
            green,
            blue,
        )


    # ========================================================
    # RGB
    # ========================================================

    def read_rgb(self):


        if not self.begin():

            raise OSError(
                "Cittius Color nao encontrado"
            )


        try:


            if self.use_burst:


                try:

                    return (
                        self._read_rgb_burst()
                    )


                except Exception:

                    self.use_burst = False


            return (
                self._read_rgb_individual()
            )


        except Exception:


            self.ready = False


            # =================================================
            # UMA TENTATIVA DE RECUPERACAO
            # =================================================

            if not self.begin():

                raise


            if self.use_burst:


                try:

                    return (
                        self._read_rgb_burst()
                    )


                except Exception:

                    self.use_burst = False


            return (
                self._read_rgb_individual()
            )


    # ========================================================
    # CLASSIFICACAO DE COR
    # ========================================================

    @staticmethod
    def detect_color(
        clear,
        red,
        green,
        blue,
    ):


        # ====================================================
        # PRETO
        # ====================================================

        if clear < BLACK_THRESHOLD:

            return 7


        # ====================================================
        # BRANCO
        # ====================================================

        if clear > WHITE_THRESHOLD:

            return 6


        # ====================================================
        # VERDE / AMARELO
        # ====================================================

        if (
            green > red
            and
            green > blue
        ):


            if red > blue:

                return 4


            return 2


        # ====================================================
        # AZUL
        # ====================================================

        if (
            blue > red
            and
            blue > green
            and
            clear > 50
            and
            clear < 70
        ):

            return 3


        # ====================================================
        # AMARELO
        # ====================================================

        if (
            red > blue
            and
            green > blue
        ):

            return 4


        # ====================================================
        # VERMELHO
        # ====================================================

        if (
            red > blue
            and
            green < blue
        ):

            return 1


        # ====================================================
        # DESCONHECIDA / LARANJA
        # ====================================================

        return 8


    # ========================================================
    # LEITURA COMPLETA
    # ========================================================

    def read_all(self):


        (
            clear,
            red,
            green,
            blue,

        ) = self.read_rgb()


        codigo = (
            self.detect_color(

                clear,
                red,
                green,
                blue,
            )
        )


        return {

            "code":
                codigo,

            "name":
                CITTIUS_COLOR_NAMES.get(
                    codigo,
                    "DESCONHECIDA"
                ),

            "clear":
                clear,

            "red":
                red,

            "green":
                green,

            "blue":
                blue,
        }


    # ========================================================
    # CLOSE
    # ========================================================

    def close(self):


        self.i2c = None

        self.ready = False

        self.use_burst = True


        # ====================================================
        # DEVOLVE GPIO PARA ALTA IMPEDANCIA
        # ====================================================

        try:

            Pin(
                self.port.gpio_rx,
                Pin.IN
            )

        except Exception:

            pass


        try:

            Pin(
                self.port.gpio_tx,
                Pin.IN
            )

        except Exception:

            pass



# ============================================================
# EV6 COLOR
# ============================================================

def _ev6_color_read(
    native_port,
    mode,
):


    if cor_sensor is None:

        raise OSError(
            "cor_sensor indisponivel"
        )


    # ========================================================
    # DRIVER NOVO
    #
    # readColor() devolve uma leitura completa.
    # ========================================================

    complete = getattr(
        cor_sensor,
        "readColor",
        None,
    )


    if complete is not None:


        return int(

            complete(
                native_port,
                mode,
            )
        )


    # ========================================================
    # DRIVER ANTIGO
    #
    # getColor / getCorF2 trabalham em etapas.
    # ========================================================

    step = getattr(

        cor_sensor,

        "getColor",

        getattr(
            cor_sensor,
            "getCorF2",
            None,
        )
    )


    if step is None:

        raise OSError(
            "Driver EV6 Color inexistente"
        )


    value = 0


    for _ in range(3):


        value = step(
            native_port,
            mode,
        )


    return int(
        value
    )


# ============================================================
# RGB EV6
# ============================================================

def _ev6_rgb(
    native_port,
):


    if cor_sensor is None:

        raise OSError(
            "cor_sensor indisponivel"
        )


    red = _ev6_color_read(

        native_port,

        cor_sensor.R,
    )


    green = _ev6_color_read(

        native_port,

        cor_sensor.G,
    )


    blue = _ev6_color_read(

        native_port,

        cor_sensor.B,
    )


    return (
        red,
        green,
        blue,
    )


# ============================================================
# NOME EV6 COLOR
# ============================================================

def _ev6_color_name(
    code,
):


    if cor_sensor is None:

        return str(
            code
        )


    function = getattr(
        cor_sensor,
        "getColorName",
        None,
    )


    if function is None:

        return str(
            code
        )


    try:

        return function(
            code
        )

    except Exception:

        return str(
            code
        )


# ============================================================
# SENSOR PORT API
# ============================================================

class SensorPortAPI:


    def __init__(
        self,
        est_port,
        native_port=None,
    ):


        self.hw = est_port

        self.native = (
            native_port
        )


        self.name = getattr(

            est_port,

            "name",

            getattr(
                est_port,
                "nome",
                "?"
            )
        )


        # ====================================================
        # ESTADO
        # ====================================================

        self.status = (
            STATUS_VAZIO
        )


        self.brand = None

        self.sensor = None

        self.protocol = None


        # ====================================================
        # MODOS
        # ====================================================

        self.modes = ()

        self.mode_index = 0


        # ====================================================
        # DRIVER ESPECIAL
        # ====================================================

        self.driver = None


        # ====================================================
        # LEITURA
        # ====================================================

        self.last_value = None

        self.last_error = None


        # ====================================================
        # PRESENCA
        # ====================================================

        self.last_presence_ms = (
            time.ticks_ms()
        )


    # ========================================================
    # FECHA DRIVER
    # ========================================================

    def _close_driver(self):


        if self.driver is not None:


            try:

                self.driver.close()

            except Exception:

                pass


        self.driver = None


    # ========================================================
    # LIMPA IDENTIDADE
    # ========================================================

    def _clear_identity(self):


        self._close_driver()


        self.brand = None

        self.sensor = None

        self.protocol = None


        self.modes = ()

        self.mode_index = 0


        self.last_value = None

        self.last_error = None


    # ========================================================
    # VAZIO
    # ========================================================

    def _set_empty(self):


        if (
            self.status == STATUS_VAZIO
            and
            self.brand is None
            and
            self.sensor is None
        ):

            return


        self._clear_identity()


        self.status = (
            STATUS_VAZIO
        )


    # ========================================================
    # IDENTIFICANDO
    # ========================================================

    def _set_identifying(
        self,
        brand=None,
        sensor=None,
        protocol=None,
    ):


        # Se havia um driver de outra familia,
        # encerra antes de mudar estado.

        if self.driver is not None:

            self._close_driver()


        self.status = (
            STATUS_IDENTIFICANDO
        )


        self.brand = brand

        self.sensor = sensor

        self.protocol = protocol


        self.modes = ()

        self.mode_index = 0


        self.last_value = None

        self.last_error = None


    # ========================================================
    # LIMITE UART
    # ========================================================

    def _set_uart_limit(self):


        self._close_driver()


        self.status = (
            STATUS_UART_LIMITE
        )


        self.brand = None

        self.sensor = SENSOR_UART

        self.protocol = (
            PROTOCOLO_UART_EV3
        )


        self.modes = ()

        self.mode_index = 0


        self.last_value = None

        self.last_error = None


    # ========================================================
    # SET DEVICE
    # ========================================================

    def _set_device(
        self,
        brand,
        sensor,
        protocol,
        modes,
        driver=None,
    ):


        old_identity = (
            self.brand,
            self.sensor,
            self.protocol,
        )


        new_identity = (
            brand,
            sensor,
            protocol,
        )


        # ====================================================
        # TROCOU DRIVER
        # ====================================================

        if (
            self.driver is not None
            and
            self.driver is not driver
        ):


            try:

                self.driver.close()

            except Exception:

                pass


        # ====================================================
        # IDENTIDADE
        # ====================================================

        self.brand = brand

        self.sensor = sensor

        self.protocol = protocol

        self.driver = driver


        self.status = (
            STATUS_PRONTO
        )


        # ====================================================
        # MODOS
        # ====================================================

        self.modes = tuple(
            modes
        )


        # ====================================================
        # SENSOR MUDOU
        # ====================================================

        if old_identity != new_identity:


            self.mode_index = 0

            self.last_value = None

            self.last_error = None


        # ====================================================
        # GARANTE INDICE VALIDO
        # ====================================================

        if (
            self.mode_index
            >= len(self.modes)
        ):

            self.mode_index = 0


    # ========================================================
    # QUANTIDADE DE MODOS
    # ========================================================

    def mode_count(self):

        return len(
            self.modes
        )


    # ========================================================
    # POSSUI MAIS DE UM MODO
    # ========================================================

    def has_modes(self):

        return (
            len(self.modes) > 1
        )


    # ========================================================
    # MODO ATUAL COMPLETO
    # ========================================================

    def current_mode(self):


        if not self.modes:

            return None


        return self.modes[
            self.mode_index
        ]


    # ========================================================
    # CHAVE DO MODO
    # ========================================================

    def mode(self):


        current = (
            self.current_mode()
        )


        if current is None:

            return None


        return current[0]


    # ========================================================
    # NOME DO MODO
    # ========================================================

    def mode_name(self):


        current = (
            self.current_mode()
        )


        if current is None:

            return ""


        return current[1]


    # ========================================================
    # UNIDADE
    # ========================================================

    def unit(self):


        current = (
            self.current_mode()
        )


        if current is None:

            return ""


        return current[2]


    # ========================================================
    # POSSUI RGB
    # ========================================================

    def has_rgb(self):


        if self.sensor != SENSOR_COR:

            return False


        # ====================================================
        # EV6
        # ====================================================

        if self.brand == MARCA_EV6:

            return True


        # ====================================================
        # CITTIUS
        # ====================================================

        if self.brand == MARCA_CITTIUS:

            return True


        # ====================================================
        # EST
        # ====================================================

        if (
            self.brand == MARCA_EST
            and
            ENABLE_EST_RGB
        ):

            return True


        return False


    # ========================================================
    # SET MODE
    # ========================================================

    def set_mode(
        self,
        mode,
    ):


        for index in range(
            len(self.modes)
        ):


            item = self.modes[
                index
            ]


            if (
                item[0] == mode
                or
                item[1] == mode
            ):


                if (
                    self.mode_index
                    != index
                ):

                    self.mode_index = index

                    self.last_value = None

                    self.last_error = None


                return True


        return False


    # ========================================================
    # PROXIMO MODO
    # ========================================================

    def next_mode(self):


        if len(self.modes) <= 1:

            return (
                self.current_mode()
            )


        self.mode_index += 1


        if (
            self.mode_index
            >= len(self.modes)
        ):

            self.mode_index = 0


        self.last_value = None

        self.last_error = None


        return (
            self.current_mode()
        )


    # ========================================================
    # MODO ANTERIOR
    # ========================================================

    def previous_mode(self):


        if len(self.modes) <= 1:

            return (
                self.current_mode()
            )


        self.mode_index -= 1


        if self.mode_index < 0:

            self.mode_index = (
                len(self.modes) - 1
            )


        self.last_value = None

        self.last_error = None


        return (
            self.current_mode()
        )


    # ========================================================
    # ASSINATURA EV6
    #
    # RX TX
    #
    # 00 = vazio
    # 01 = gyro
    # 10 = ultra
    # 11 = color / Cittius color
    # ========================================================

    def _digital_signature(
        self,
        samples=10,
    ):


        rx = Pin(

            self.hw.gpio_rx,

            Pin.IN,

            Pin.PULL_DOWN,
        )


        tx = Pin(

            self.hw.gpio_tx,

            Pin.IN,

            Pin.PULL_DOWN,
        )


        time.sleep_ms(
            3
        )


        counters = [
            0,
            0,
            0,
            0,
        ]


        for _ in range(
            samples
        ):


            a = rx.value()

            b = tx.value()


            index = (
                (a << 1)
                | b
            )


            counters[
                index
            ] += 1


            time.sleep_ms(
                1
            )


        return counters


    # ========================================================
    # NOME EST PELO TYPE
    # ========================================================

    def _est_sensor_from_type(
        self,
        uart_type,
    ):


        if uart_type == est.TYPE_COLOR:

            return SENSOR_COR


        if uart_type == est.TYPE_ULTRASONIC:

            return SENSOR_ULTRASONICO


        if uart_type == est.TYPE_GYRO:

            return SENSOR_GIROSCOPIO


        if uart_type == est.TYPE_INFRARED:

            return SENSOR_INFRAVERMELHO


        return SENSOR_UART


    # ========================================================
    # DETECTA EST
    # ========================================================

    def _detect_est(self):


        try:

            connection = (
                self.hw
                .get_connection_type()
            )

        except Exception:

            return False


        # ====================================================
        # UART
        # ====================================================

        if connection == est.UART:


            # =================================================
            # SEM RECURSO UART
            # =================================================

            try:

                if (
                    self.hw
                    .is_uart_waiting_resource()
                ):


                    self._set_uart_limit()


                    return True


            except Exception:

                pass


            # =================================================
            # TYPE PODE APARECER ANTES DO READY
            # =================================================

            try:

                uart_type = (
                    self.hw
                    .get_uart_type()
                )

            except Exception:

                uart_type = -1


            # =================================================
            # UART AINDA NAO ESTA PRONTA
            #
            # MUITO IMPORTANTE:
            #
            # TYPE = 29
            #
            # nao significa que handshake terminou.
            # =================================================

            try:

                uart_ready = (
                    self.hw
                    .is_uart_ready()
                )

            except Exception:

                uart_ready = False


            if not uart_ready:


                sensor_hint = SENSOR_UART


                if uart_type >= 0:

                    sensor_hint = (
                        self._est_sensor_from_type(
                            uart_type
                        )
                    )


                self._set_identifying(

                    MARCA_EST,

                    sensor_hint,

                    PROTOCOLO_UART_EV3,
                )


                return True


            # =================================================
            # AGORA SIM ESTA PRONTO
            # =================================================

            uart_type = (
                self.hw
                .get_uart_type()
            )


            # =================================================
            # COR
            # =================================================

            if uart_type == est.TYPE_COLOR:


                modes = [


                    _mode(
                        MODE_COR,
                        "COR",
                        "",
                        est.COR,
                    ),


                    _mode(
                        MODE_REFLEXAO,
                        "REFLEXAO",
                        "%",
                        est.REFLEXAO,
                    ),


                    _mode(
                        MODE_AMBIENTE,
                        "AMBIENTE",
                        "%",
                        est.AMBIENTE,
                    ),
                ]


                # =============================================
                # EV3 RGB ORIGINAL
                # =============================================

                if ENABLE_EST_RGB:


                    modes.append(

                        _mode(
                            MODE_RGB,
                            "RGB",
                            "",
                            EST_RGB_MODE,
                        )
                    )


                self._set_device(

                    MARCA_EST,

                    SENSOR_COR,

                    PROTOCOLO_UART_EV3,

                    modes,
                )


                return True


            # =================================================
            # ULTRASSONICO
            # =================================================

            if uart_type == est.TYPE_ULTRASONIC:


                self._set_device(

                    MARCA_EST,

                    SENSOR_ULTRASONICO,

                    PROTOCOLO_UART_EV3,

                    (

                        _mode(
                            MODE_CM,
                            "DISTANCIA",
                            "cm",
                            est.CM,
                        ),

                        _mode(
                            MODE_INCH,
                            "POLEGADAS",
                            "in",
                            est.POLEGADAS,
                        ),

                        _mode(
                            MODE_ESCUTA,
                            "ESCUTA",
                            "",
                            est.ESCUTA,
                        ),
                    ),
                )


                return True


            # =================================================
            # GIROSCOPIO
            # =================================================

            if uart_type == est.TYPE_GYRO:


                self._set_device(

                    MARCA_EST,

                    SENSOR_GIROSCOPIO,

                    PROTOCOLO_UART_EV3,

                    (

                        _mode(
                            MODE_ANGULO,
                            "ANGULO",
                            "graus",
                            est.ANGULO,
                        ),

                        _mode(
                            MODE_VELOCIDADE,
                            "VELOCIDADE",
                            "graus/s",
                            est.VELOCIDADE,
                        ),

                        _mode(
                            MODE_ANGULO_VELOCIDADE,
                            "ANG + VEL",
                            "",
                            est.ANGULO_VELOCIDADE,
                        ),
                    ),
                )


                return True


            # =================================================
            # INFRAVERMELHO
            # =================================================

            if uart_type == est.TYPE_INFRARED:


                self._set_device(

                    MARCA_EST,

                    SENSOR_INFRAVERMELHO,

                    PROTOCOLO_UART_EV3,

                    (

                        _mode(
                            MODE_PROXIMIDADE,
                            "PROXIMIDADE",
                            "%",
                            est.PROXIMIDADE,
                        ),

                        _mode(
                            MODE_BUSCA,
                            "BUSCA",
                            "",
                            est.BUSCA,
                        ),

                        _mode(
                            MODE_CONTROLE,
                            "CONTROLE",
                            "",
                            est.CONTROLE,
                        ),
                    ),
                )


                return True


            # =================================================
            # UART DESCONHECIDA
            # =================================================

            self._set_device(

                MARCA_EST,

                "UART TYPE {}".format(
                    uart_type
                ),

                PROTOCOLO_UART_EV3,

                (),
            )


            return True


        # ====================================================
        # BOTAO / TOQUE
        # ====================================================

        if connection == est.BOTAO:


            self._set_device(

                MARCA_EST,

                SENSOR_BOTAO,

                PROTOCOLO_ADC,

                (

                    _mode(
                        MODE_ESTADO,
                        "ESTADO",
                        "",
                    ),

                ),
            )


            return True


        # ====================================================
        # SOM
        # ====================================================

        if connection == est.SOM:


            self._set_device(

                MARCA_EST,

                SENSOR_SOM,

                PROTOCOLO_ADC,

                (

                    _mode(
                        MODE_NIVEL,
                        "NIVEL",
                        "",
                    ),

                ),
            )


            return True


        return False


    # ========================================================
    # DETECTA EV6 / CITTIUS
    # ========================================================

    def _detect_ev6_cittius(self):


        # ====================================================
        # SEGURANCA
        #
        # So mexemos em RX/TX quando o ADC bruto diz VAZIO.
        #
        # Se estiver:
        #
        # UART
        # BOTAO
        # SOM
        # INDEFINIDO
        #
        # nao tocamos nos pinos.
        # ====================================================

        try:

            raw_type = (
                self.hw
                .get_adc_raw_type()
            )

        except Exception:

            return False


        if raw_type != est.VAZIO:

            return False


        # ====================================================
        # LE ASSINATURA
        # ====================================================

        try:

            counters = (
                self._digital_signature()
            )

        except Exception:

            return False


        c00 = counters[0]

        c01 = counters[1]

        c10 = counters[2]

        c11 = counters[3]


        minimum = 7


        # ====================================================
        # VAZIO
        # ====================================================

        if c00 >= minimum:

            return False


        # ====================================================
        # GIRO EV6
        # ====================================================

        if c01 >= minimum:


            self._set_device(

                MARCA_EV6,

                SENSOR_GIROSCOPIO,

                PROTOCOLO_ONEWIRE,

                (),
            )


            return True


        # ====================================================
        # ULTRASSONICO EV6
        # ====================================================

        if c10 >= minimum:


            if ultra is None:

                return False


            self._set_device(

                MARCA_EV6,

                SENSOR_ULTRASONICO,

                PROTOCOLO_ONEWIRE,

                (

                    _mode(
                        MODE_CM,
                        "DISTANCIA",
                        "cm",
                        ultra.CM,
                    ),

                    _mode(
                        MODE_MM,
                        "DISTANCIA",
                        "mm",
                        ultra.MM,
                    ),

                    _mode(
                        MODE_INCH,
                        "DISTANCIA",
                        "in",
                        ultra.INCH,
                    ),
                ),
            )


            return True


        # ====================================================
        # 11
        #
        # CITTIUS COLOR
        # ou
        # EV6 COLOR
        # ====================================================

        if c11 >= minimum:


            # =================================================
            # PRIMEIRO CITTIUS
            # =================================================

            cittius = (
                CittiusColorDriver(
                    self.hw
                )
            )


            if cittius.begin():


                self._set_device(

                    MARCA_CITTIUS,

                    SENSOR_COR,

                    PROTOCOLO_I2C,

                    (

                        _mode(
                            MODE_COR,
                            "COR",
                            "",
                        ),

                        _mode(
                            MODE_RGB,
                            "RGB",
                            "",
                        ),

                        _mode(
                            MODE_CLEAR,
                            "CLEAR",
                            "",
                        ),
                    ),

                    cittius,
                )


                return True


            cittius.close()


            # =================================================
            # EV6
            # =================================================

            if cor_sensor is None:

                return False


            self._set_device(

                MARCA_EV6,

                SENSOR_COR,

                PROTOCOLO_ONEWIRE,

                (

                    _mode(
                        MODE_COR,
                        "COR",
                        "",
                        cor_sensor.COR,
                    ),

                    _mode(
                        MODE_REFLEXAO,
                        "REFLEXAO",
                        "%",
                        cor_sensor.REFLEXAO,
                    ),

                    _mode(
                        MODE_AMBIENTE,
                        "AMBIENTE",
                        "%",
                        cor_sensor.AMBIENTE,
                    ),

                    _mode(
                        MODE_RGB,
                        "RGB",
                        "",
                    ),
                ),
            )


            return True


        return False


    # ========================================================
    # PRESENCA EV6
    # ========================================================

    def _ev6_present(self):


        try:

            counters = (
                self._digital_signature(
                    samples=6
                )
            )

        except Exception:

            return False


        c01 = counters[1]

        c10 = counters[2]

        c11 = counters[3]


        # ====================================================
        # GIRO
        #
        # Inicialmente pode ser 01 e depois virar 11.
        # ====================================================

        if self.sensor == SENSOR_GIROSCOPIO:


            return (
                c01 >= 4
                or
                c11 >= 4
            )


        # ====================================================
        # ULTRA
        # ====================================================

        if self.sensor == SENSOR_ULTRASONICO:

            return (
                c10 >= 4
            )


        # ====================================================
        # COLOR
        # ====================================================

        if self.sensor == SENSOR_COR:

            return (
                c11 >= 4
            )


        return False


    # ========================================================
    # UPDATE
    # ========================================================

    def update(self):


        now = time.ticks_ms()


        # ====================================================
        # CITTIUS ATIVO
        # ====================================================

        if self.brand == MARCA_CITTIUS:


            if time.ticks_diff(

                now,

                self.last_presence_ms

            ) >= PRESENCE_CHECK_MS:


                self.last_presence_ms = (
                    now
                )


                try:

                    present = (
                        self.driver is not None
                        and
                        self.driver.ping()
                    )

                except Exception:

                    present = False


                if not present:

                    self._set_empty()


            return


        # ====================================================
        # EV6 ATIVO
        # ====================================================

        if self.brand == MARCA_EV6:


            if time.ticks_diff(

                now,

                self.last_presence_ms

            ) >= PRESENCE_CHECK_MS:


                self.last_presence_ms = (
                    now
                )


                if not self._ev6_present():

                    self._set_empty()


            return


        # ====================================================
        # EST
        # ====================================================

        if self._detect_est():

            return


        # ====================================================
        # EV6 / CITTIUS
        # ====================================================

        if self._detect_ev6_cittius():

            return


        # ====================================================
        # NENHUM SENSOR IDENTIFICADO
        # ====================================================

        try:

            raw_type = (
                self.hw
                .get_adc_raw_type()
            )

        except Exception:

            raw_type = est.INDEFINIDO


        # ====================================================
        # AINDA ESTABILIZANDO
        # ====================================================

        if raw_type in (

            est.UART,

            est.BOTAO,

            est.SOM,

            est.INDEFINIDO,

        ):


            self._set_identifying()


            return


        # ====================================================
        # REALMENTE VAZIO
        # ====================================================

        self._set_empty()


    # ========================================================
    # RESULTADO PADRAO
    # ========================================================

    def _result(
        self,
        value,
        text,
        unit=None,
        rgb=None,
        extra=None,
    ):


        if unit is None:

            unit = self.unit()


        result = {

            "ok":
                True,

            "port":
                self.name,

            "status":
                self.status,

            "brand":
                self.brand,

            "sensor":
                self.sensor,

            "protocol":
                self.protocol,

            "mode":
                self.mode(),

            "mode_name":
                self.mode_name(),

            "value":
                value,

            "text":
                text,

            "unit":
                unit,
        }


        # ====================================================
        # RGB PADRONIZADO
        # ====================================================

        if rgb is not None:


            result["rgb"] = {

                "r":
                    int(rgb[0]),

                "g":
                    int(rgb[1]),

                "b":
                    int(rgb[2]),
            }


        # ====================================================
        # EXTRA
        # ====================================================

        if extra is not None:

            result["extra"] = extra


        return result


    # ========================================================
    # LEITURA EST
    # ========================================================

    def _read_est(self):


        current = (
            self.current_mode()
        )


        # ====================================================
        # UART DESCONHECIDA
        # ====================================================

        if current is None:


            return self._result(

                None,

                "SEM LEITURA",

                "",
            )


        argument = (
            current[3]
        )


        # ====================================================
        # COR EST
        # ====================================================

        if self.sensor == SENSOR_COR:


            # =================================================
            # RGB RAW
            # =================================================

            if self.mode() == MODE_RGB:


                values = (
                    self.hw
                    .read_uart_mode(

                        est.TYPE_COLOR,

                        EST_RGB_MODE,
                    )
                )


                if (
                    values is None
                    or
                    len(values) < 3
                ):

                    raise OSError(
                        "RGB incompleto"
                    )


                r = int(
                    round(
                        values[0]
                    )
                )


                g = int(
                    round(
                        values[1]
                    )
                )


                b = int(
                    round(
                        values[2]
                    )
                )


                return self._result(

                    (
                        r,
                        g,
                        b,
                    ),

                    "RGB",

                    "",

                    (
                        r,
                        g,
                        b,
                    ),
                )


            # =================================================
            # COR / REFLEXAO / AMBIENTE
            # =================================================

            value = est.getColor(

                self.hw,

                argument,
            )


            if self.mode() == MODE_COR:


                text = est.getColorName(
                    value
                )


            else:

                text = str(
                    value
                )


            return self._result(

                value,

                text,
            )


        # ====================================================
        # ULTRASSONICO EST
        # ====================================================

        if self.sensor == SENSOR_ULTRASONICO:


            value = est.getUltra(

                self.hw,

                argument,
            )


            return self._result(

                value,

                str(value),
            )


        # ====================================================
        # GIROSCOPIO EST
        # ====================================================

        if self.sensor == SENSOR_GIROSCOPIO:


            value = est.getGyro(

                self.hw,

                argument,
            )


            return self._result(

                value,

                str(value),
            )


        # ====================================================
        # INFRAVERMELHO EST
        # ====================================================

        if self.sensor == SENSOR_INFRAVERMELHO:


            # Por enquanto canal 1.
            # Depois podemos colocar canal no submenu do display.

            value = est.getIR(

                self.hw,

                argument,

                1,
            )


            return self._result(

                value,

                str(value),
            )


        # ====================================================
        # TOQUE
        #
        # 0 = SOLTO
        # 1 = PRESSIONADO
        # ====================================================

        if self.sensor == SENSOR_BOTAO:


            pressed = est.getButton(
                self.hw
            )


            value = (
                1
                if pressed
                else 0
            )


            if value:


                text = (
                    "1 - PRESSIONADO"
                )


            else:


                text = (
                    "0 - SOLTO"
                )


            return self._result(

                value,

                text,

                "",
            )


        # ====================================================
        # SOM
        #
        # IMPORTANTE:
        #
        # getSound atualmente devolve leitura ADC.
        #
        # Portanto NAO usamos "%" aqui.
        # ====================================================

        if self.sensor == SENSOR_SOM:


            value = est.getSound(
                self.hw
            )


            try:

                value = int(
                    value
                )

            except Exception:

                pass


            return self._result(

                value,

                str(value),

                "",
            )


        # ====================================================
        # DESCONHECIDO
        # ====================================================

        return self._result(

            None,

            "SEM LEITURA",

            "",
        )


    # ========================================================
    # LEITURA EV6
    # ========================================================

    def _read_ev6(self):


        current = (
            self.current_mode()
        )


        # ====================================================
        # GIRO EV6
        #
        # Ainda nao temos protocolo de leitura validado.
        # Identificacao funciona normalmente.
        # ====================================================

        if self.sensor == SENSOR_GIROSCOPIO:


            return self._result(

                None,

                "IDENTIFICADO",

                "",
            )


        if current is None:


            return self._result(

                None,

                "SEM MODO",

                "",
            )


        argument = (
            current[3]
        )


        # ====================================================
        # COR EV6
        # ====================================================

        if self.sensor == SENSOR_COR:


            # =================================================
            # RGB
            # =================================================

            if self.mode() == MODE_RGB:


                (
                    r,
                    g,
                    b,

                ) = _ev6_rgb(
                    self.native
                )


                return self._result(

                    (
                        r,
                        g,
                        b,
                    ),

                    "RGB",

                    "",

                    (
                        r,
                        g,
                        b,
                    ),
                )


            # =================================================
            # OUTROS MODOS
            # =================================================

            value = _ev6_color_read(

                self.native,

                argument,
            )


            if self.mode() == MODE_COR:


                text = (
                    _ev6_color_name(
                        value
                    )
                )


            else:

                text = str(
                    value
                )


            return self._result(

                value,

                text,
            )


        # ====================================================
        # ULTRASSONICO EV6
        # ====================================================

        if self.sensor == SENSOR_ULTRASONICO:


            if ultra is None:

                raise OSError(
                    "ultra indisponivel"
                )


            value = ultra.get(

                self.native,

                argument,
            )


            try:

                value = int(
                    value
                )

            except Exception:

                pass


            return self._result(

                value,

                str(value),
            )


        return self._result(

            None,

            "SEM LEITURA",

            "",
        )


    # ========================================================
    # LEITURA CITTIUS
    # ========================================================

    def _read_cittius(self):


        if (
            self.sensor
            != SENSOR_COR
            or
            self.driver is None
        ):

            raise OSError(
                "Driver Cittius indisponivel"
            )


        dados = (
            self.driver.read_all()
        )


        # ====================================================
        # COR
        # ====================================================

        if self.mode() == MODE_COR:


            return self._result(

                dados["code"],

                dados["name"],

                "",
            )


        # ====================================================
        # RGB
        # ====================================================

        if self.mode() == MODE_RGB:


            rgb = (

                dados["red"],

                dados["green"],

                dados["blue"],
            )


            return self._result(

                rgb,

                "RGB",

                "",

                rgb,
            )


        # ====================================================
        # CLEAR
        # ====================================================

        if self.mode() == MODE_CLEAR:


            value = (
                dados["clear"]
            )


            return self._result(

                value,

                str(value),

                "",
            )


        raise OSError(
            "Modo Cittius invalido"
        )


    # ========================================================
    # READ PUBLICO
    # ========================================================

    def read(self):


        # ====================================================
        # NAO PRONTO
        # ====================================================

        if self.status != STATUS_PRONTO:


            return {

                "ok":
                    False,

                "port":
                    self.name,

                "status":
                    self.status,

                "brand":
                    self.brand,

                "sensor":
                    self.sensor,

                "protocol":
                    self.protocol,

                "mode":
                    self.mode(),

                "mode_name":
                    self.mode_name(),

                "value":
                    None,

                "text":
                    self.status,

                "unit":
                    "",
            }


        # ====================================================
        # LEITURA
        # ====================================================

        try:


            if self.brand == MARCA_EST:


                result = (
                    self._read_est()
                )


            elif self.brand == MARCA_EV6:


                result = (
                    self._read_ev6()
                )


            elif self.brand == MARCA_CITTIUS:


                result = (
                    self._read_cittius()
                )


            else:


                raise OSError(
                    "Marca desconhecida"
                )


            # =================================================
            # CACHE
            # =================================================

            self.last_value = (
                result.get(
                    "value"
                )
            )


            self.last_error = None


            return result


        except Exception as error:


            self.last_error = str(
                error
            )


            return {

                "ok":
                    False,

                "port":
                    self.name,

                "status":
                    STATUS_ERRO,

                "brand":
                    self.brand,

                "sensor":
                    self.sensor,

                "protocol":
                    self.protocol,

                "mode":
                    self.mode(),

                "mode_name":
                    self.mode_name(),

                "value":
                    None,

                "text":
                    "ERRO",

                "unit":
                    self.unit(),

                "error":
                    self.last_error,
            }


    # ========================================================
    # INFO
    # ========================================================

    def info(self):


        uart_waiting = False

        uart_slot = None

        uart_type = -1

        baud = 0


        # ====================================================
        # DIAGNOSTICO UART
        # ====================================================

        try:

            uart_waiting = (
                self.hw
                .is_uart_waiting_resource()
            )

        except Exception:

            pass


        try:

            uart_slot = (
                self.hw
                .get_uart_slot()
            )

        except Exception:

            pass


        try:

            uart_type = (
                self.hw
                .get_uart_type()
            )

        except Exception:

            pass


        try:

            baud = (
                self.hw
                .get_baud()
            )

        except Exception:

            pass


        # ====================================================
        # ADC
        # ====================================================

        adc = None


        try:

            adc = (
                self.hw
                .get_adc()
            )

        except Exception:

            pass


        # ====================================================
        # RETORNO
        # ====================================================

        return {

            "port":
                self.name,

            "status":
                self.status,

            "connected":
                self.status
                == STATUS_PRONTO,

            "uart_limit":
                self.status
                == STATUS_UART_LIMITE,

            "uart_waiting":
                uart_waiting,

            "uart_slot":
                uart_slot,

            "uart_type":
                uart_type,

            "baud":
                baud,

            "brand":
                self.brand,

            "sensor":
                self.sensor,

            "protocol":
                self.protocol,

            "mode":
                self.mode(),

            "mode_name":
                self.mode_name(),

            "mode_index":
                self.mode_index,

            "mode_count":
                self.mode_count(),

            "has_modes":
                self.has_modes(),

            "has_rgb":
                self.has_rgb(),

            "unit":
                self.unit(),

            "adc":
                adc,

            "last_value":
                self.last_value,

            "error":
                self.last_error,
        }



# ============================================================
# SENSOR API CENTRAL
# ============================================================

class SensorAPI:


    def __init__(self):


        # ====================================================
        # INICIALIZACAO
        # ====================================================

        self.started = False


        # ====================================================
        # VERIFICA MIHU_HW
        # ====================================================

        if mihu_hw is None:


            raise ImportError(
                "mihu_hw indisponivel"
            )


        # ====================================================
        # PORTAS
        # ====================================================

        self.ports = (


            SensorPortAPI(
                est.P1,
                mihu_hw.P1,
            ),


            SensorPortAPI(
                est.P2,
                mihu_hw.P2,
            ),


            SensorPortAPI(
                est.P3,
                mihu_hw.P3,
            ),


            SensorPortAPI(
                est.M1,
                mihu_hw.M1,
            ),


            SensorPortAPI(
                est.M2,
                mihu_hw.M2,
            ),


            SensorPortAPI(
                est.M3,
                mihu_hw.M3,
            ),


            SensorPortAPI(
                est.M4,
                mihu_hw.M4,
            ),
        )


        # ====================================================
        # PORTA SELECIONADA
        # ====================================================

        self.port_index = 0


        # ====================================================
        # MAPA POR NOME
        # ====================================================

        self.by_name = {}


        for port in self.ports:


            self.by_name[
                port.name
            ] = port


    # ========================================================
    # BEGIN
    #
    # IDEMPOTENTE
    #
    # A main chama uma vez.
    #
    # Se pageSensores chamar novamente por engano,
    # NAO reinicia as portas.
    # ========================================================

    def begin(self):


        if self.started:

            return self


        # ====================================================
        # PRIMEIRA AMOSTRA ADS1115
        # ====================================================

        try:

            est.ADS1115.update()

        except Exception:

            pass


        # ====================================================
        # INICIALIZA AS 7 PORTAS UMA VEZ
        # ====================================================

        for port in self.ports:


            try:

                port.hw.begin()

            except Exception as error:


                print(
                    port.name,
                    "| BEGIN ERRO:",
                    error
                )


        self.started = True


        return self


    # ========================================================
    # STARTED?
    # ========================================================

    def is_started(self):

        return self.started


    # ========================================================
    # UPDATE
    #
    # Deve rodar continuamente na main.
    # ========================================================

    def update(self):


        # ====================================================
        # SE ESQUECER BEGIN, INICIA AUTOMATICAMENTE
        # ====================================================

        if not self.started:

            self.begin()


        # ====================================================
        # ADS1115
        #
        # UMA atualizacao global por ciclo.
        # ====================================================

        try:

            est.ADS1115.update()

        except Exception:

            pass


        # ====================================================
        # TODAS AS PORTAS
        # ====================================================

        for port in self.ports:


            # =================================================
            # EST / ANALOGICO
            #
            # Enquanto EV6 ou Cittius assumem os GPIOs,
            # nao deixamos mihuSensor3 mexer na mesma porta.
            # =================================================

            if port.brand not in (

                MARCA_EV6,

                MARCA_CITTIUS,

            ):


                try:

                    port.hw.service_update()

                except Exception:

                    pass


            # =================================================
            # API
            # =================================================

            try:

                port.update()

            except Exception as error:


                port.last_error = str(
                    error
                )


        return self


    # ========================================================
    # ALIAS
    # ========================================================

    service = update


    # ========================================================
    # GET PORT
    # ========================================================

    def get(
        self,
        name,
    ):


        return self.by_name.get(
            str(name)
        )


    # ========================================================
    # []
    #
    # sensores["P1"]
    # ========================================================

    def __getitem__(
        self,
        name,
    ):


        return self.get(
            name
        )


    # ========================================================
    # PORTA ATUAL
    # ========================================================

    def current(self):


        return self.ports[
            self.port_index
        ]


    # ========================================================
    # NOME ATUAL
    # ========================================================

    def current_name(self):


        return (
            self.current()
            .name
        )


    # ========================================================
    # SELECIONA PORTA
    # ========================================================

    def select_port(
        self,
        port,
    ):


        # ====================================================
        # PELO NOME
        # ====================================================

        if isinstance(
            port,
            str
        ):


            for index in range(
                len(self.ports)
            ):


                if (
                    self.ports[index].name
                    == port
                ):


                    self.port_index = index


                    return (
                        self.current()
                    )


            return None


        # ====================================================
        # PELO INDICE
        # ====================================================

        try:

            index = int(
                port
            )

        except Exception:

            return None


        if (
            index < 0
            or
            index >= len(self.ports)
        ):

            return None


        self.port_index = index


        return (
            self.current()
        )


    # ========================================================
    # PROXIMA PORTA
    # ========================================================

    def next_port(self):


        self.port_index += 1


        if (
            self.port_index
            >= len(self.ports)
        ):

            self.port_index = 0


        return (
            self.current()
        )


    # ========================================================
    # PORTA ANTERIOR
    # ========================================================

    def previous_port(self):


        self.port_index -= 1


        if self.port_index < 0:

            self.port_index = (
                len(self.ports) - 1
            )


        return (
            self.current()
        )


    # ========================================================
    # PROXIMO MODO
    # ========================================================

    def next_mode(self):


        return (
            self.current()
            .next_mode()
        )


    # ========================================================
    # MODO ANTERIOR
    # ========================================================

    def previous_mode(self):


        return (
            self.current()
            .previous_mode()
        )


    # ========================================================
    # SET MODE
    # ========================================================

    def set_mode(
        self,
        mode,
    ):


        return (
            self.current()
            .set_mode(
                mode
            )
        )


    # ========================================================
    # INFO ATUAL
    # ========================================================

    def info(self):


        return (
            self.current()
            .info()
        )


    # ========================================================
    # READ ATUAL
    # ========================================================

    def read(self):


        return (
            self.current()
            .read()
        )


    # ========================================================
    # INFO DE TODAS
    # ========================================================

    def info_all(self):


        result = []


        for port in self.ports:


            result.append(
                port.info()
            )


        return result


    # ========================================================
    # QUANTIDADE
    # ========================================================

    def count(self):

        return len(
            self.ports
        )



# ============================================================
# INSTANCIA GLOBAL
#
# ESTA INSTANCIA DEVE SER COMPARTILHADA POR:
#
# main.py
# pageSensores.py
# outras telas
#
# NUNCA criar SensorAPI() novamente em cada pagina.
# ============================================================

sensores = SensorAPI()


# ============================================================
# FUNCOES DE CONVENIENCIA
# ============================================================

def begin():

    return sensores.begin()


def update():

    return sensores.update()


def current():

    return sensores.current()


def selectPort(
    port
):

    return sensores.select_port(
        port
    )


def nextPort():

    return sensores.next_port()


def previousPort():

    return sensores.previous_port()


def nextMode():

    return sensores.next_mode()


def previousMode():

    return sensores.previous_mode()


def read():

    return sensores.read()


def info():

    return sensores.info()


def infoAll():

    return sensores.info_all()


# ============================================================
# EXPORTACOES
# ============================================================

__all__ = (

    # ========================================================
    # CENTRAL
    # ========================================================

    "SensorAPI",

    "SensorPortAPI",

    "sensores",


    # ========================================================
    # FUNCOES
    # ========================================================

    "begin",

    "update",

    "current",

    "selectPort",

    "nextPort",

    "previousPort",

    "nextMode",

    "previousMode",

    "read",

    "info",

    "infoAll",


    # ========================================================
    # STATUS
    # ========================================================

    "STATUS_VAZIO",

    "STATUS_IDENTIFICANDO",

    "STATUS_PRONTO",

    "STATUS_ERRO",

    "STATUS_UART_LIMITE",


    # ========================================================
    # MARCAS
    # ========================================================

    "MARCA_EST",

    "MARCA_EV6",

    "MARCA_CITTIUS",


    # ========================================================
    # SENSORES
    # ========================================================

    "SENSOR_COR",

    "SENSOR_ULTRASONICO",

    "SENSOR_GIROSCOPIO",

    "SENSOR_INFRAVERMELHO",

    "SENSOR_BOTAO",

    "SENSOR_SOM",

    "SENSOR_UART",


    # ========================================================
    # MODOS
    # ========================================================

    "MODE_COR",

    "MODE_REFLEXAO",

    "MODE_AMBIENTE",

    "MODE_RGB",

    "MODE_CLEAR",

    "MODE_CM",

    "MODE_MM",

    "MODE_INCH",

    "MODE_ESCUTA",

    "MODE_ANGULO",

    "MODE_VELOCIDADE",

    "MODE_ANGULO_VELOCIDADE",

    "MODE_PROXIMIDADE",

    "MODE_BUSCA",

    "MODE_CONTROLE",

    "MODE_ESTADO",

    "MODE_NIVEL",
)