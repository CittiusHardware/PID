# adc.py
# Detecção elétrica das sete portas.
#
# P1, P2 e P3 usam o ADC interno do ESP32-S3.
# M1, M2, M3 e M4 usam o ADS1115 no endereço 0x48.
#
# Padrão público:
#     0 até 4095
#
# A classificação elétrica preserva as escalas calibradas
# originais. Cada atualização obtém somente uma nova amostra.
# A filtragem usa mediana progressiva, sem delays.

from machine import ADC, Pin, I2C
import time

from .constants import (
    UART,
    BOTAO,
    SOM,
    VAZIO,
    INDEFINIDO,
    ADC_UART_MIN,
    ADC_UART_MAX,
    ADC_BOTAO_MIN,
    ADC_BOTAO_MAX,
    ADC_SOM_MIN,
    ADC_SOM_MAX,
    ADC_VAZIO_MIN,
    ADS_ADC_UART_MIN,
    ADS_ADC_UART_MAX,
    ADS_ADC_BOTAO_MIN,
    ADS_ADC_BOTAO_MAX,
    ADS_ADC_SOM_MIN,
    ADS_ADC_SOM_MAX,
    ADS_ADC_VAZIO_MIN,
    ADS1115_I2C_ID,
    ADS1115_SDA,
    ADS1115_SCL,
    ADS1115_FREQ,
    ADS1115_ADDRESS,
    ADC_SOURCE_INTERNAL,
    ADC_SOURCE_ADS1115,
    ADS1115_CONVERSION_US,
    ADC_PUBLIC_MIN,
    ADC_PUBLIC_MAX,
    ADC_FILTER_SAMPLES,
)


def _odd_samples(value):
    value = max(
        1,
        int(value),
    )

    if value % 2 == 0:
        value += 1

    return value


def _median(values):
    if not values:
        return 0

    ordered = list(values)
    ordered.sort()

    return int(
        ordered[len(ordered) // 2]
    )


def _clamp(value, minimum, maximum):
    value = int(value)

    if value < minimum:
        return minimum

    if value > maximum:
        return maximum

    return value


def _u16_from_12bit(value):
    value = _clamp(
        value,
        ADC_PUBLIC_MIN,
        ADC_PUBLIC_MAX,
    )

    return (
        value * 65535
    ) // ADC_PUBLIC_MAX


def _public_from_ads(value):
    value = _clamp(
        value,
        0,
        32767,
    )

    return (
        value * ADC_PUBLIC_MAX
    ) // 32767


class ADCDetector:
    """
    ADC interno de P1, P2 e P3.

    O objeto ADC é criado somente na primeira leitura.
    """

    source = ADC_SOURCE_INTERNAL
    channel = None

    def __init__(
        self,
        gpio_adc,
        filter_samples=ADC_FILTER_SAMPLES,
    ):
        self.gpio_adc = int(gpio_adc)
        self.adc = None

        self.filter_samples = _odd_samples(
            filter_samples
        )

        # Escala pública 0..4095.
        self.valor_raw = 0
        self.valor = 0

        # Escala histórica 0..65535 usada na classificação.
        self.valor_classificacao = 0

        self.tipo = INDEFINIDO
        self.valido = False
        self.last_error = None

        self._samples = []

    # ========================================================
    # INICIALIZAÇÃO
    # ========================================================

    def _start(self):
        if self.adc is not None:
            return True

        try:
            adc = ADC(
                Pin(self.gpio_adc)
            )

            try:
                adc.atten(
                    ADC.ATTN_11DB
                )
            except Exception:
                pass

            try:
                adc.width(
                    ADC.WIDTH_12BIT
                )
            except Exception:
                pass

            self.adc = adc
            self.last_error = None
            return True

        except Exception as error:
            self.adc = None
            self.valido = False
            self.last_error = error
            return False

    # ========================================================
    # LEITURA
    # ========================================================

    def _read_12bit(self):
        if not self._start():
            return None

        try:
            try:
                value = self.adc.read()
            except AttributeError:
                value = (
                    self.adc.read_u16()
                    >> 4
                )

            value = _clamp(
                value,
                ADC_PUBLIC_MIN,
                ADC_PUBLIC_MAX,
            )

            self.last_error = None
            return value

        except Exception as error:
            self.valido = False
            self.last_error = error
            return None

    def _push_sample(self, value):
        self._samples.append(
            int(value)
        )

        while (
            len(self._samples)
            > self.filter_samples
        ):
            self._samples.pop(0)

        self.valor = _median(
            self._samples
        )

        self.valor_classificacao = (
            _u16_from_12bit(
                self.valor
            )
        )

    def ler_uma_amostra(self):
        """
        Obtém uma amostra física e retorna 0..4095.
        """

        value = self._read_12bit()

        if value is None:
            return self.valor

        self.valor_raw = value
        self._push_sample(value)
        self.valido = True

        return self.valor_raw

    def ler_filtrado(self):
        """
        Obtém uma amostra e retorna a mediana progressiva.
        """

        self.ler_uma_amostra()
        return self.valor

    @staticmethod
    def classificar(valor):

        if ADC_UART_MIN <= valor <= ADC_UART_MAX:
            return UART

        if ADC_BOTAO_MIN <= valor <= ADC_BOTAO_MAX:
            return BOTAO

        if ADC_SOM_MIN <= valor <= ADC_SOM_MAX:
            return SOM

        if valor >= ADC_VAZIO_MIN:
            return VAZIO

        return INDEFINIDO

    def atualizar(self, forcar=False):
        """
        Lê uma amostra e classifica usando a escala calibrada.

        Retorna:
            mudou, tipo, valor_publico_0_a_4095
        """

        del forcar

        self.ler_uma_amostra()

        if not self.valido:
            novo_tipo = INDEFINIDO
        else:
            novo_tipo = self.classificar(
                self.valor_classificacao
            )

        mudou = novo_tipo != self.tipo
        self.tipo = novo_tipo

        return (
            mudou,
            self.tipo,
            self.valor,
        )

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    def get_tipo(self):
        return self.tipo

    def get_valor(self):
        return self.valor

    def get_raw_value(self):
        return self.valor_raw

    def get_filtered_raw(self):
        # Para o ADC interno, a escala física já é 12 bits.
        return self.valor

    def get_classification_value(self):
        return self.valor_classificacao

    def get_data(self):
        return {
            "source": self.source,
            "channel": self.channel,
            "gpio": self.gpio_adc,
            "raw": self.valor_raw,
            "filtered": self.valor,
            "classification_value": (
                self.valor_classificacao
            ),
            "value": self.valor,
            "percent": (
                self.valor * 100
            ) // ADC_PUBLIC_MAX,
            "type": self.tipo,
            "valid": self.valido,
            "filter_samples": (
                self.filter_samples
            ),
            "last_error": self.last_error,
        }

    def reset_filter(self):
        self._samples = []
        self.valor_raw = 0
        self.valor = 0
        self.valor_classificacao = 0
        self.tipo = INDEFINIDO
        self.valido = False
        return True

    def is_valid(self):
        return self.valido

    def get_source(self):
        return self.source

    def get_channel(self):
        return self.channel

    def get_error(self):
        return self.last_error

    def end(self):
        if self.adc is not None:
            try:
                self.adc.deinit()
            except Exception:
                pass

        self.adc = None
        self.reset_filter()
        self.last_error = None
        return True


class ADS1115Scanner:
    """
    Varredura contínua dos quatro canais do ADS1115.

    O I2C é criado somente na primeira atualização.
    """

    REG_CONVERSION = 0x00
    REG_CONFIG = 0x01

    def __init__(
        self,
        i2c=None,
        i2c_id=ADS1115_I2C_ID,
        sda=ADS1115_SDA,
        scl=ADS1115_SCL,
        freq=ADS1115_FREQ,
        address=ADS1115_ADDRESS,
    ):
        self._external_i2c = i2c
        self.i2c = None

        self.i2c_id = int(i2c_id)
        self.sda = int(sda)
        self.scl = int(scl)
        self.freq = int(freq)
        self.address = int(address)

        self.values = [0, 0, 0, 0]
        self.valid = [
            False,
            False,
            False,
            False,
        ]
        self.sequence = [0, 0, 0, 0]

        self.current_channel = -1
        self.waiting_conversion = False
        self.ready_at_us = 0

        self.online = False
        self.last_error = None
        self.retry_at_ms = 0

    def _start(self):
        if self.i2c is not None:
            return True

        try:
            if self._external_i2c is not None:
                self.i2c = (
                    self._external_i2c
                )
            else:
                self.i2c = I2C(
                    self.i2c_id,
                    sda=Pin(self.sda),
                    scl=Pin(self.scl),
                    freq=self.freq,
                )

            self.last_error = None
            return True

        except Exception as error:
            self.i2c = None
            self.online = False
            self.last_error = error
            return False

    def _write_register(
        self,
        register,
        value,
    ):
        data = bytes((
            (value >> 8) & 0xFF,
            value & 0xFF,
        ))

        if hasattr(
            self.i2c,
            "writeto_mem",
        ):
            self.i2c.writeto_mem(
                self.address,
                register,
                data,
            )
            return

        self.i2c.writeto(
            self.address,
            bytes((register,))
            + data,
        )

    def _read_register(
        self,
        register,
    ):
        if hasattr(
            self.i2c,
            "readfrom_mem",
        ):
            return self.i2c.readfrom_mem(
                self.address,
                register,
                2,
            )

        self.i2c.writeto(
            self.address,
            bytes((register,)),
            False,
        )

        return self.i2c.readfrom(
            self.address,
            2,
        )

    def _start_conversion(
        self,
        channel,
    ):
        config = (
            0x8000
            | ((0x04 + channel) << 12)
            | 0x0200
            | 0x0100
            | 0x00E0
            | 0x0003
        )

        self._write_register(
            self.REG_CONFIG,
            config,
        )

        self.current_channel = channel
        self.waiting_conversion = True

        self.ready_at_us = time.ticks_add(
            time.ticks_us(),
            ADS1115_CONVERSION_US,
        )

    def _read_conversion(self):
        data = self._read_register(
            self.REG_CONVERSION
        )

        value = (
            data[0] << 8
        ) | data[1]

        if value & 0x8000:
            value -= 0x10000

        if value < 0:
            value = 0

        channel = self.current_channel

        self.values[channel] = value
        self.valid[channel] = True
        self.sequence[channel] += 1

        self.online = True
        self.last_error = None

    def update(self):
        now_ms = time.ticks_ms()
        now_us = time.ticks_us()

        if self.last_error is not None:
            if time.ticks_diff(
                now_ms,
                self.retry_at_ms,
            ) < 0:
                return False

            self.last_error = None
            self.waiting_conversion = False

        if not self._start():
            self.retry_at_ms = time.ticks_add(
                now_ms,
                100,
            )
            return False

        try:
            if self.waiting_conversion:
                if time.ticks_diff(
                    now_us,
                    self.ready_at_us,
                ) < 0:
                    return False

                self._read_conversion()
                self.waiting_conversion = False

            next_channel = (
                self.current_channel + 1
            ) & 0x03

            self._start_conversion(
                next_channel
            )

            return True

        except Exception as error:
            self.online = False
            self.last_error = error
            self.waiting_conversion = False

            self.retry_at_ms = time.ticks_add(
                now_ms,
                100,
            )

            return False

    def get_channel_value(
        self,
        channel,
    ):
        if channel < 0 or channel > 3:
            raise ValueError(
                "Canal ADS1115 deve estar entre 0 e 3"
            )

        return (
            self.valid[channel],
            self.values[channel],
        )

    def get_channel_sample(
        self,
        channel,
    ):
        valid, value = (
            self.get_channel_value(
                channel
            )
        )

        return (
            valid,
            value,
            self.sequence[channel],
        )

    def is_online(self):
        return self.online

    def get_error(self):
        return self.last_error

    def info(self):
        return {
            "started": self.i2c is not None,
            "online": self.online,
            "i2c_id": self.i2c_id,
            "sda": self.sda,
            "scl": self.scl,
            "frequency": self.freq,
            "address": self.address,
            "current_channel": (
                self.current_channel
            ),
            "last_error": self.last_error,
        }

    def end(self):
        if (
            self._external_i2c is None
            and self.i2c is not None
        ):
            try:
                self.i2c.deinit()
            except Exception:
                pass

        self.i2c = None
        self.waiting_conversion = False
        self.current_channel = -1
        self.online = False
        self.last_error = None

        self.values = [0, 0, 0, 0]
        self.valid = [
            False,
            False,
            False,
            False,
        ]
        self.sequence = [0, 0, 0, 0]

        return True


class ADS1115Detector:
    """
    Detector de M1, M2, M3 e M4.

    A classificação usa o valor ADS1115 original.
    A leitura pública é convertida para 0..4095.
    """

    source = ADC_SOURCE_ADS1115

    def __init__(
        self,
        scanner,
        channel,
        filter_samples=ADC_FILTER_SAMPLES,
    ):
        if channel < 0 or channel > 3:
            raise ValueError(
                "Canal ADS1115 deve estar entre 0 e 3"
            )

        self.scanner = scanner
        self.channel = int(channel)
        self.gpio_adc = None

        self.filter_samples = _odd_samples(
            filter_samples
        )

        self.valor_raw = 0
        self.valor_filtrado_raw = 0
        self.valor = 0

        self.tipo = INDEFINIDO
        self.valido = False
        self.last_error = None

        self._samples = []
        self._last_sequence = -1

    @staticmethod
    def classificar(valor):

        if (
            ADS_ADC_UART_MIN
            <= valor
            <= ADS_ADC_UART_MAX
        ):
            return UART

        if (
            ADS_ADC_BOTAO_MIN
            <= valor
            <= ADS_ADC_BOTAO_MAX
        ):
            return BOTAO

        if (
            ADS_ADC_SOM_MIN
            <= valor
            <= ADS_ADC_SOM_MAX
        ):
            return SOM

        if valor >= ADS_ADC_VAZIO_MIN:
            return VAZIO

        return INDEFINIDO

    def _push_sample(self, raw_value):
        self._samples.append(
            int(raw_value)
        )

        while (
            len(self._samples)
            > self.filter_samples
        ):
            self._samples.pop(0)

        self.valor_filtrado_raw = (
            _median(self._samples)
        )

        self.valor = _public_from_ads(
            self.valor_filtrado_raw
        )

    def ler_uma_amostra(self):
        # Avança o scanner sem esperar pela conversão.
        self.scanner.update()

        (
            valid,
            raw_value,
            sequence,
        ) = self.scanner.get_channel_sample(
            self.channel
        )

        self.valido = valid
        self.last_error = (
            self.scanner.get_error()
        )

        if not valid:
            return self.valor

        self.valor_raw = int(raw_value)

        # Não repete a mesma conversão no filtro.
        if sequence != self._last_sequence:
            self._last_sequence = sequence
            self._push_sample(
                self.valor_raw
            )

        return self.valor

    def ler_filtrado(self):
        return self.ler_uma_amostra()

    def atualizar(self, forcar=False):
        del forcar

        self.ler_uma_amostra()

        if not self.valido:
            novo_tipo = INDEFINIDO
        else:
            novo_tipo = self.classificar(
                self.valor_filtrado_raw
            )

        mudou = novo_tipo != self.tipo
        self.tipo = novo_tipo

        return (
            mudou,
            self.tipo,
            self.valor,
        )

    def get_tipo(self):
        return self.tipo

    def get_valor(self):
        return self.valor

    def get_raw_value(self):
        return self.valor_raw

    def get_filtered_raw(self):
        return self.valor_filtrado_raw

    def get_classification_value(self):
        return self.valor_filtrado_raw

    def get_data(self):
        return {
            "source": self.source,
            "channel": self.channel,
            "gpio": None,
            "raw": self.valor_raw,
            "filtered": (
                self.valor_filtrado_raw
            ),
            "classification_value": (
                self.valor_filtrado_raw
            ),
            "value": self.valor,
            "percent": (
                self.valor * 100
            ) // ADC_PUBLIC_MAX,
            "type": self.tipo,
            "valid": self.valido,
            "filter_samples": (
                self.filter_samples
            ),
            "last_error": self.last_error,
        }

    def reset_filter(self):
        self._samples = []
        self._last_sequence = -1
        self.valor_raw = 0
        self.valor_filtrado_raw = 0
        self.valor = 0
        self.tipo = INDEFINIDO
        self.valido = False
        self.last_error = None
        return True

    def is_valid(self):
        return self.valido

    def get_source(self):
        return self.source

    def get_channel(self):
        return self.channel

    def get_error(self):
        return self.last_error
