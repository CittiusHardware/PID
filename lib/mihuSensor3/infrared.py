# infrared.py
# Funções do sensor infravermelho EV3 UART tipo 33.

from .constants import (
    TYPE_INFRARED,
    PROXIMIDADE,
    BUSCA,
    CONTROLE,
)


def _signed8(valor):

    valor = int(round(valor))

    if valor > 127:
        valor -= 256

    return valor


def getIR(
    porta,
    funcao=PROXIMIDADE,
    canal=1
):

    if funcao not in (
        PROXIMIDADE,
        BUSCA,
        CONTROLE
    ):

        raise ValueError(
            "Modo do infravermelho invalido"
        )

    if canal < 1 or canal > 4:

        raise ValueError(
            "Canal deve estar entre 1 e 4"
        )

    valores = porta.read_uart_mode(
        TYPE_INFRARED,
        funcao
    )

    if funcao == PROXIMIDADE:

        return int(round(valores[0]))

    if funcao == BUSCA:

        indice = (canal - 1) * 2

        if len(valores) <= indice + 1:
            return 0, -128

        direcao = _signed8(
            valores[indice]
        )

        distancia = _signed8(
            valores[indice + 1]
        )

        return direcao, distancia

    # CONTROLE: um código por canal.
    indice = canal - 1

    if len(valores) <= indice:
        return 0

    return int(round(valores[indice]))
