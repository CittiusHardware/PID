# color.py
# Funções do sensor de cor EV3 UART tipo 29.

from .constants import (
    TYPE_COLOR,
    REFLEXAO,
    AMBIENTE,
    COR,
)


def getColor(porta, funcao):

    if funcao not in (
        REFLEXAO,
        AMBIENTE,
        COR
    ):

        raise ValueError(
            "Funcao de cor invalida"
        )

    valores = porta.read_uart_mode(
        TYPE_COLOR,
        funcao
    )

    return int(round(valores[0]))


def getColorName(codigo):

    nomes = (
        "SEM_COR",
        "PRETO",
        "AZUL",
        "VERDE",
        "AMARELO",
        "VERMELHO",
        "BRANCO",
        "MARROM"
    )

    if (
        codigo < 0
        or codigo >= len(nomes)
    ):
        return "DESCONHECIDA"

    return nomes[codigo]
