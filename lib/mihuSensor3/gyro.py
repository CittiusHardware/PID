# gyro.py
# Funções do giroscópio EV3 UART tipo 32.

from .constants import (
    TYPE_GYRO,
    ANGULO,
    VELOCIDADE,
    ANGULO_VELOCIDADE,
)


def getGyro(porta, funcao=ANGULO):

    if funcao not in (
        ANGULO,
        VELOCIDADE,
        ANGULO_VELOCIDADE
    ):

        raise ValueError(
            "Modo do giroscopio invalido"
        )

    valores = porta.read_uart_mode(
        TYPE_GYRO,
        funcao
    )

    if funcao == ANGULO_VELOCIDADE:

        if len(valores) < 2:
            return (
                int(round(valores[0])),
                0
            )

        return (
            int(round(valores[0])),
            int(round(valores[1]))
        )

    return int(round(valores[0]))
