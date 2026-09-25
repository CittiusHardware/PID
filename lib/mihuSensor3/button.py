# button.py
# Leitura direta e nao bloqueante do botao/toque.
#
# O ADC continua sendo usado pelo servico para a tela e para o
# reconhecimento automatico do sensor. A funcao do aluno nao espera
# essa classificacao, porque o valor ADC pode mudar enquanto o botao
# esta pressionado.
#
# O estado digital e lido no RX da porta:
#   P1 -> GPIO 18
#   P2 -> GPIO 15
#   P3 -> GPIO 17
#   M1 -> GPIO 11
#   M2 -> GPIO 12
#   M3 -> GPIO 13
#   M4 -> GPIO 14


def getButton(porta):
    """
    Retorna True quando o botao esta pressionado.

    Esta leitura nao chama wait_connection() e nao depende do tipo
    ADC atual da porta. Assim, pressionar o botao nao provoca timeout
    mesmo quando a identificacao eletrica muda temporariamente.
    """

    return porta.get_button()


def isPressed(porta):
    return getButton(porta)
