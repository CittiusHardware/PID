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


def tela_aguardando():

    oled.clear()

    oled.text(
        "LEITOR RFID",
        0,
        0,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "Aproxime",
        0,
        20,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "um cartao...",
        0,
        32,
        scale=1,
        color=1,
        sync=True
    )


def tela_sucesso(cartao):

    oled.clear()

    oled.text(
        "CARTAO OK",
        0,
        0,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "UID:",
        0,
        16,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        cartao["uid_hex"],
        0,
        28,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        cartao["text"],
        0,
        44,
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
        20,
        scale=1,
        color=1,
        sync=False
    )

    oled.text(
        "leitura",
        0,
        32,
        scale=1,
        color=1,
        sync=True
    )


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
    presence_misses=4
)


print(
    "MFRC522:",
    rfid.version_hex()
)

print(
    "Aproxime um cartao..."
)


# ============================================================
# TELA INICIAL
# ============================================================

tela_aguardando()


# ============================================================
# LOOP
# ============================================================

while True:

    try:

        cartao = rfid.read_once(
            block=4
        )

        if cartao is not None:

            # ================================================
            # SOM DE ACERTO
            # ================================================

            som.system_ok(
                70
            )


            # ================================================
            # DISPLAY
            # ================================================

            tela_sucesso(
                cartao
            )


            # ================================================
            # SERIAL
            # ================================================

            print()
            print(
                "CARTAO DETECTADO"
            )

            print(
                "UID:",
                cartao["uid_hex"]
            )

            print(
                "BLOCO 4:",
                cartao["text"]
            )

            print()


            # Mostra o resultado por 2 segundos
            sleep_ms(
                2000
            )


            # Volta para tela inicial
            tela_aguardando()


    except Exception as erro:

        # ================================================
        # SOM DE ERRO
        # ================================================

        som.error(
            70
        )


        # ================================================
        # DISPLAY
        # ================================================

        tela_erro()


        # ================================================
        # SERIAL
        # ================================================

        print()
        print(
            "ERRO NA LEITURA RFID:"
        )

        print(
            erro
        )

        print()


        sleep_ms(
            1500
        )


        tela_aguardando()


    sleep_ms(
        100
    )