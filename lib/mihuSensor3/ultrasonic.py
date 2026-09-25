# ultrasonic.py
# Funções do sensor ultrassônico EV3 UART tipo 30.

from .constants import (
    TYPE_ULTRASONIC,
    CM,
    POLEGADAS,
    ESCUTA,
)


def getUltra(porta, unidade=CM):

    if unidade not in (
        CM,
        POLEGADAS,
        ESCUTA
    ):

        raise ValueError(
            "Modo do ultrassonico invalido"
        )

    valores = porta.read_uart_mode(
        TYPE_ULTRASONIC,
        unidade
    )

    valor = valores[0]

    if unidade == ESCUTA:
        return bool(int(round(valor)))

    return valor
