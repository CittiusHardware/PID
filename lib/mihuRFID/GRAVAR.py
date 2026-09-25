from machine import Pin, I2C
from time import sleep_ms

from mihuRFID import MihuRFID
from lib.mihuSound import som
from lib.mihuOled import mihuOled as oled
from lib.mihuArduino import *


# ============================================================
# DISPLAY
# ============================================================

__MIHU_USES_DISPLAY__ = True

oled.init()


def tela_aguardando(valor):

    oled.clear()

    oled.text(
        "GRAVAR RFID",
        0,
        0,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "Valor:",
        0,
        16,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        str(valor),
        42,
        16,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "Aproxime",
        0,
        36,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "o cartao...",
        0,
        48,
        scale=1,
        color=1,
        sync=True
    )


def tela_gravando(valor):

    oled.clear()

    oled.text(
        "GRAVANDO...",
        0,
        0,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "Bloco: 4",
        0,
        20,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "Valor:",
        0,
        36,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        str(valor),
        42,
        36,
        scale=1,
        color=1,
        sync=True
    )


def tela_sucesso(valor):

    oled.clear()

    oled.text(
        "GRAVACAO OK",
        0,
        0,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "Bloco: 4",
        0,
        20,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "Valor:",
        0,
        36,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        str(valor),
        42,
        36,
        scale=1,
        color=1,
        sync=True
    )


def tela_erro():

    oled.clear()

    oled.text(
        "ERRO RFID",
        0,
        0,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "Falha na",
        0,
        22,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "gravacao",
        0,
        36,
        scale=1,
        color=1,
        sync=True
    )


def tela_conferindo():

    oled.clear()

    oled.text(
        "CONFERINDO",
        0,
        0,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "Leitura final",
        0,
        24,
        scale=1,
        color=1,
        sync=True
    )


# ============================================================
# CONFIGURACAO
# ============================================================

valor = "T10"


# ============================================================
# I2C
# ============================================================

i2c = I2C(
    0,
    sda=Pin(39),
    scl=Pin(40),
    freq=100000
)


# ============================================================
# RFID
# ============================================================

rfid = MihuRFID(
    i2c,
    address=0x28,
    debug=True
)


print(
    "MFRC522:",
    rfid.version_hex()
)

print()
print(
    "Valor que sera gravado:",
    valor
)

print(
    "Aproxime o cartao..."
)


# ============================================================
# TELA INICIAL
# ============================================================

tela_aguardando(
    valor
)


# ============================================================
# AGUARDA O CARTAO
# ============================================================

while True:

    if rfid.card_present():
        break

    sleep_ms(
        100
    )


# ============================================================
# GRAVACAO
# ============================================================

tela_gravando(
    valor
)


print()
print(
    "Gravando",
    valor,
    "no bloco 4..."
)


ok = rfid.write_text(
    valor,
    block=4,
    verify=True,
    retries=3,
    settle_ms=100
)


# ============================================================
# RESULTADO DA GRAVACAO
# ============================================================

print()


if ok:

    print(
        "=============================="
    )

    print(
        " GRAVACAO CONFIRMADA"
    )

    print(
        "=============================="
    )

    print(
        "Valor:",
        valor
    )


else:

    print(
        "=============================="
    )

    print(
        " FALHA NA GRAVACAO"
    )

    print(
        "=============================="
    )

    print(
        "Status:",
        rfid.last_write_status,
        rfid.status_name(
            rfid.last_write_status
        )
    )

    print(
        "Tentativas:",
        rfid.last_write_attempts
    )


# ============================================================
# LEITURA FINAL DE CONFERENCIA
# ============================================================

valor_lido = None


if ok:

    tela_conferindo()


    print()
    print(
        "Fazendo leitura final..."
    )


    # Reinicia completamente o campo RF
    rfid._rf_cycle(
        off_ms=100,
        on_ms=100
    )


    valor_lido = rfid.read_text(
        block=4
    )


    print(
        "Valor gravado solicitado:",
        valor
    )

    print(
        "Valor realmente lido:",
        valor_lido
    )


# ============================================================
# RESULTADO FINAL
# ============================================================

if (
    ok
    and valor_lido == valor
):

    # --------------------------------------------------------
    # ACERTO
    # --------------------------------------------------------

    som.system_ok(
        70
    )


    tela_sucesso(
        valor
    )


    print()
    print(
        "CONFIRMACAO FINAL OK"
    )


else:

    # --------------------------------------------------------
    # ERRO
    # --------------------------------------------------------

    som.error(
        70
    )


    tela_erro()


    print()
    print(
        "ERRO: O VALOR NAO FOI GRAVADO"
    )