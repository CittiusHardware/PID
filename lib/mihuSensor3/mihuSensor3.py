# mihuSensor3.py
# API pública da biblioteca.

from .constants import *
from .adc import (
    ADS1115Scanner,
    ADS1115Detector,
)
from .uart_manager import UARTManager
from .port import MihuSensorPort
from .service import SensorService

from .color import (
    getColor,
    getColorName,
)

from .ultrasonic import getUltra
from .gyro import getGyro
from .infrared import getIR

from .button import (
    getButton,
    isPressed,
)

from .sound import getSound


MIHU_SENSOR3_VERSION = "5.5.2-uart-retry-once"


# =====================================================
# =============== RECURSOS COMPARTILHADOS =============
# =====================================================

# Somente três UARTs físicas podem existir ao mesmo tempo.
UARTS = UARTManager((0, 1, 2))

# M1-M4 compartilham o mesmo ADS1115 em 0x48.
ADS1115 = ADS1115Scanner(
    i2c_id=ADS1115_I2C_ID,
    sda=ADS1115_SDA,
    scl=ADS1115_SCL,
    freq=ADS1115_FREQ,
    address=ADS1115_ADDRESS,
)


# =====================================================
# ================= ADC INTERNO P1-P3 ==================
# =====================================================

P1 = MihuSensorPort(
    nome="P1",
    gpio_adc=1,
    uart_id=1,
    gpio_rx=18,
    gpio_tx=44,
    uart_manager=UARTS
)

P2 = MihuSensorPort(
    nome="P2",
    gpio_adc=2,
    uart_id=2,
    gpio_rx=15,
    gpio_tx=16,
    uart_manager=UARTS
)

P3 = MihuSensorPort(
    nome="P3",
    gpio_adc=3,
    uart_id=0,
    gpio_rx=17,
    gpio_tx=43,
    uart_manager=UARTS
)


# =====================================================
# ================= ADS1115 M1-M4 ======================
# =====================================================

M1 = MihuSensorPort(
    nome="M1",
    gpio_rx=11,
    gpio_tx=41,
    detector=ADS1115Detector(
        ADS1115,
        ADS1115_M1_CHANNEL
    ),
    uart_manager=UARTS
)

M2 = MihuSensorPort(
    nome="M2",
    gpio_rx=12,
    gpio_tx=47,
    detector=ADS1115Detector(
        ADS1115,
        ADS1115_M2_CHANNEL
    ),
    uart_manager=UARTS
)

M3 = MihuSensorPort(
    nome="M3",
    gpio_rx=13,
    gpio_tx=42,
    detector=ADS1115Detector(
        ADS1115,
        ADS1115_M3_CHANNEL
    ),
    uart_manager=UARTS
)

M4 = MihuSensorPort(
    nome="M4",
    gpio_rx=14,
    gpio_tx=45,
    detector=ADS1115Detector(
        ADS1115,
        ADS1115_M4_CHANNEL
    ),
    uart_manager=UARTS
)


PORTAS = (
    P1,
    P2,
    P3,
    M1,
    M2,
    M3,
    M4
)

PORTS = PORTAS

SERVICO = SensorService(
    PORTAS,
    adc_services=(ADS1115,)
)


def iniciarSensores(
    discovery_ms=BOOT_DISCOVERY_MS,
    timeout_ms=BOOT_TIMEOUT_MS
):
    """
    Chamar antes de setupAluno().
    """

    return SERVICO.prepare_boot(
        discovery_ms=discovery_ms,
        timeout_ms=timeout_ms
    )


def atualizarSensores():
    """
    Chamar continuamente no laço principal do sistema.
    """

    SERVICO.update()


# Compatibilidade.
def update(porta=None):

    if porta is None:
        atualizarSensores()
    else:
        porta.service_update()


def sensoresProntos(porta=None):

    return SERVICO.is_ready(porta)


def relatorioSensores():

    return SERVICO.report()


def restart(porta):

    porta.reset()


def reiniciar(porta):

    restart(porta)


def _update_adc(porta):
    """
    Atualiza somente uma amostra física, sem bloquear.
    """

    if (
        porta.get_adc_source()
        == ADC_SOURCE_ADS1115
    ):
        ADS1115.update()

    porta.detector.atualizar(
        forcar=True
    )


def getADC(porta):
    """
    Retorna o ADC em 12 bits, de 0 a 4095.

    O mesmo intervalo é usado em P1-P3 e M1-M4.
    """

    _update_adc(porta)
    return porta.get_adc()


def getADCRaw(porta):
    """
    Retorna a última amostra na escala física do detector.

    P1-P3:
        0 a 4095.

    M1-M4:
        escala original do ADS1115.
    """

    _update_adc(porta)
    return porta.get_adc_raw()


def getADCFiltered(porta):
    """
    Retorna a mediana progressiva na escala física.
    """

    _update_adc(porta)
    return porta.get_adc_filtered_raw()


def getADCPercent(porta):
    """
    Retorna o ADC normalizado entre 0 e 100.
    """

    value = getADC(porta)

    return (
        int(value) * 100
    ) // ADC_PUBLIC_MAX


def getADCData(porta):
    """
    Diagnóstico completo do ADC da porta.
    """

    _update_adc(porta)

    data = dict(
        porta.get_adc_data()
    )

    data.update({
        "port": porta.nome,
        "connection": (
            porta.get_connection_type()
        ),
        "sensor": (
            porta.get_sensor_type()
        ),
    })

    return data


def resetADC(porta):
    """
    Limpa a mediana e o estado de classificação da porta.
    """

    return porta.reset_adc_filter()


def getConnection(porta):

    return porta.get_connection_type()


def getSensorType(porta):

    return porta.get_sensor_type()


def getUARTType(porta):

    return porta.get_uart_type()


def getBaud(porta):

    return porta.get_baud()


def getUARTSlot(porta):

    return porta.get_uart_slot()


def isUARTEnabled(porta):

    return porta.is_uart_enabled()


def isUARTWaiting(porta):

    return porta.is_uart_waiting_resource()


def getUARTUsage():

    return UARTS.report()


def getUARTRetryCount(porta):
    """Número de reinicializações lógicas usadas na conexão atual."""
    return porta.get_uart_initial_retry_count()


def isUARTRetryExhausted(porta):
    """True quando a única segunda tentativa inicial já foi usada."""
    return porta.is_uart_retry_exhausted()


def hasUARTBeenReady(porta):
    """True depois que a conexão atual já chegou à primeira leitura."""
    return porta.has_uart_ever_ready()


def getStatus(porta):

    return {
        "porta": porta.nome,
        "adc": porta.get_adc(),
        "adc_percentual": (
            porta.get_adc() * 100
        ) // ADC_PUBLIC_MAX,
        "adc_fonte": porta.get_adc_source(),
        "ads_canal": porta.get_adc_channel(),
        "adc_valor_bruto": porta.get_adc_raw(),
        "adc_valor_filtrado": (
            porta.get_adc_filtered_raw()
        ),
        "adc_classificacao_valor": (
            porta.get_adc_classification_value()
        ),
        "adc_erro": porta.get_adc_error(),
        "adc_bruto": porta.get_adc_raw_type(),
        "adc_candidato": porta.get_adc_candidate(),
        "adc_candidato_ms": porta.get_adc_candidate_ms(),
        "uart_vazio_pendente": porta.is_uart_empty_pending(),
        "uart_vazio_ms": porta.get_uart_empty_candidate_ms(),
        "conexao": porta.get_connection_type(),
        "sensor": porta.get_sensor_type(),
        "uart_type": porta.get_uart_type(),
        "uart_slot": porta.get_uart_slot(),
        "uart_sem_recurso": porta.is_uart_waiting_resource(),
        "baud": porta.get_baud(),
        "uart_ativa": porta.is_uart_enabled(),
        "pronto": porta.is_ready(),
        "uart_status": porta.uart_sensor.get_status(),
        "uart_retry_count": porta.get_uart_initial_retry_count(),
        "uart_retry_exhausted": porta.is_uart_retry_exhausted(),
        "uart_ever_ready": porta.has_uart_ever_ready(),
        "modo": porta.uart_sensor.get_current_mode(),
    }


def printStatus(porta=None):

    lista = PORTAS if porta is None else (porta,)

    for item in lista:

        estado = getStatus(item)

        print(
            estado["porta"],
            "| ADC:", estado["adc"],
            "| ADC%:", estado["adc_percentual"],
            "| RAW:", estado["adc_valor_bruto"],
            "| FILTRADO:", estado["adc_valor_filtrado"],
            "| FONTE:", estado["adc_fonte"],
            "| CANAL:", estado["ads_canal"],
            "| CONEXAO:", estado["conexao"],
            "| SENSOR:", estado["sensor"],
            "| UART_TYPE:", estado["uart_type"],
            "| UART_SLOT:", estado["uart_slot"],
            "| BAUD:", estado["baud"],
            "| UART_ATIVA:", estado["uart_ativa"],
            "| SEM_RECURSO:", estado["uart_sem_recurso"],
            "| PRONTO:", estado["pronto"],
            "| RETRY:", estado["uart_retry_count"],
            "| RETRY_FIM:", estado["uart_retry_exhausted"],
            "| MODO:", estado["modo"]
        )



def finalizarSensores():
    """
    Libera ADCs, ADS1115 e UARTs das sete portas.
    """

    for porta in PORTAS:
        try:
            porta.reset()
        except Exception:
            pass

        detector = getattr(
            porta,
            "detector",
            None,
        )

        if (
            detector is not None
            and hasattr(detector, "end")
        ):
            try:
                detector.end()
            except Exception:
                pass

    try:
        ADS1115.end()
    except Exception:
        pass

    return True


end = finalizarSensores
