VERSION = "0.4.0"

STATUS_PENDING = "PENDING"
STATUS_RUNNING = "RUNNING"
STATUS_PASS = "PASS"
STATUS_FAIL = "FAIL"
STATUS_NOT_IMPLEMENTED = "NOT_IMPLEMENTED"

# ============================================================
# TIMEOUTS
# ============================================================
# Cada periférico possui um timeout próprio.
# Os testes implementados já utilizam estes valores.
# Os próximos testes devem usar timeout_for(NAME).

TEST_TIMEOUT_MS = {
    "DISPLAY": 15000,
    "BUTTONS": 60000,
    "RFID": 15000,
    "LIGHT_LEFT": 10000,
    "LIGHT_RIGHT": 10000,
    "LEDS": 20000,
    "SOUND": 12000,
    "GYROSCOPE": 10000,
    "SD_CARD": 15000,
    "RJ_SENSORS": 20000,
    "RJ_MOTORS": 20000,
    "ADS_BATTERY": 10000,
    "ADS_MOTORS": 10000,
    "PCA_LEDS": 15000,
    "IR_LED": 10000,
    "REMOTE_CONTROL": 15000,
}


def timeout_for(name, default=10000):
    return int(
        TEST_TIMEOUT_MS.get(
            str(name).upper(),
            default,
        )
    )


# ============================================================
# RFID
# ============================================================

RFID_BLOCK = 4
RFID_ADDRESS = 0x28

I2C_ID = 0
I2C_SDA = 39
I2C_SCL = 40
I2C_FREQ = 100000



# ============================================================
# LIGHT SENSORS - BH1750
# ============================================================
#
# Mapeamento físico adotado:
#   LEFT  -> lux1 -> 0x5C
#   RIGHT -> lux2 -> 0x23
#
# Se a revisão física da placa estiver invertida, troque apenas
# LIGHT_LEFT_SOURCE e LIGHT_RIGHT_SOURCE.

LIGHT_LEFT_SOURCE = "lux1"
LIGHT_RIGHT_SOURCE = "lux2"

LIGHT_LEFT_ADDRESS = 0x5C
LIGHT_RIGHT_ADDRESS = 0x23

# Média inicial usada como referência.
LIGHT_BASE_SAMPLES = 5

# Intervalo entre leituras.
LIGHT_SAMPLE_INTERVAL_MS = 120

# Mudança mínima exigida para comprovar resposta do sensor.
# O teste usa o MAIOR valor entre:
#   LIGHT_MIN_DELTA_LUX
#   baseline * LIGHT_DELTA_PERCENT / 100
LIGHT_MIN_DELTA_LUX = 8
LIGHT_DELTA_PERCENT = 20

# Exige algumas leituras consecutivas acima do delta para
# não aprovar por um pico isolado.
LIGHT_CONFIRM_READS = 3

# ============================================================
# BUTTONS
# ============================================================

# Limite por botão dentro do teste sequencial.
BUTTON_STEP_TIMEOUT_MS = 10000

# Ordem física solicitada:
# CIMA, ESQUERDA, VOLTAR, BAIXO, OK, DIREITA
#
# A tela permanece em inglês:
# UP, LEFT, BACK, DOWN, OK, RIGHT

BUTTON_SEQUENCE = (
    "UP",
    "LEFT",
    "BACK",
    "DOWN",
    "OK",
    "RIGHT",
)


# ============================================================
# FULL TEST
# ============================================================

FULL_TEST_ORDER = (
    "DISPLAY",
    "BUTTONS",
    "RFID",
    "LIGHT_LEFT",
    "LIGHT_RIGHT",
    "LEDS",
    "SOUND",
    "GYROSCOPE",
    "SD_CARD",
    "RJ_SENSORS",
    "RJ_MOTORS",
    "ADS_BATTERY",
    "ADS_MOTORS",
    "PCA_LEDS",
    "IR_LED",
    "REMOTE_CONTROL",
)
