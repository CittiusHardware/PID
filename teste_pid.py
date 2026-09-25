from time import ticks_us, ticks_diff, sleep_ms
from mihuMotor import *

# ESTADOS
STEPUP = 0
RUN = 1
STEPDOWN = 2
BRAKED = 3

# POSICAO
posicao_atual = m1.read()

# VALORES PID
kp_posicao = 5

kp_velocidade = 0.1

# --------------------- VARIAVEIS --------------------- #
estado = 0

posicao = []
tempo = []

posicao_alvo = 300
margem_distancia_alvo = 100

amostras_longe = 15
amostras_perto = 5

velocidade_atual = 0
velocidade_desejada = 0
velocidade_max = 800

pwm_atual = 0

stepup_inicializado = False

# --------------------- Funções Auxiliares --------------------- #
def atualizar_encoder():
    global posicao_atual
    global velocidade_atual

    posicao_atual = m1.read()
    tempo_atual = ticks_us()

    # Cada posição recebe exatamente o seu tempo
    posicao.append(posicao_atual)
    tempo.append(tempo_atual)

    # Calcula a distancia faltante para atingir o alvo
    erro_posicao = posicao_alvo - posicao_atual

    # Define qual margem sera utilizada 
    if abs(erro_posicao) >= margem_distancia_alvo:
        amostras = amostras_longe
    else:
        amostras = amostras_perto

    # Mantém os vetores de posição e tempo sincronizados "tirando" o valor da posição 0 da lista
    while len(posicao) > amostras:
        posicao.pop(0)
        tempo.pop(0)

    # Calcula a velocidade 
    delta_posicao = posicao[-1] - posicao[0]
    delta_tempo_us = ticks_diff(tempo[-1], tempo[0])

    if delta_tempo_us <= 0:
        velocidade_atual = 0
        return

    velocidade_atual = (delta_posicao / (delta_tempo_us / 1_000_000))


def executar_stepup():
    global estado
    global velocidade_desejada
    global pwm_atual

    distancia_restante = posicao_alvo - posicao_atual

    # DIREÇÃO
    if distancia_restante > 0:
        direcao = 1
    elif distancia_restante < 0:
        direcao = -1
    else:
        estado = STEPDOWN
        return


    # Velocidade normalizada em -100 ... +100
    velocidade_ev3 = (velocidade_atual / velocidade_max) * 100

    if velocidade_ev3 > 100:
        velocidade_ev3 = 100

    elif velocidade_ev3 < -100:
        velocidade_ev3 = -100


    # Se a posição prevista já alcança o alvo,
    # começa a desaceleração
    antecipacao = abs(velocidade_ev3) / 2

    if abs(distancia_restante) <= antecipacao:
        estado = STEPDOWN

        print("RUN -> STEPDOWN",
              "Pos:", posicao_atual,
              "Restante:", distancia_restante,
              "Antecipacao:", antecipacao)
        return


    # Mantém velocidade constante
    velocidade_desejada = (velocidade_max * direcao)

    # REGULADOR DE VELOCIDADE
    erro_velocidade = (velocidade_desejada - velocidade_atual)

    # Proporcional 
    P = (erro_velocidade * kp_velocidade)

    # Controle incremental
    pwm_atual += P

    # SATURAÇÃO
    if pwm_atual > 4095:
        pwm_atual = 4095

    elif pwm_atual < -4095:
        pwm_atual = -4095

    # Não deixa potência apontar contra TargetSpeed
    if velocidade_desejada > 0 and pwm_atual < 0:
        pwm_atual = 0

    elif velocidade_desejada < 0 and pwm_atual > 0:
        pwm_atual = 0

    # MOTOR
    m1.pwm(int(pwm_atual))

    print(
        "RUN",
        "Pos:", posicao_atual,
        "Restante:", distancia_restante,
        "VelDesejada:", velocidade_desejada,
        "Vel:", velocidade_atual,
        "VelEV3:", velocidade_ev3,
        "Antecipacao:", antecipacao,
        "PWM:", pwm_atual
    )

def executar_run():
    global estado
    global velocidade_desejada
    global pwm_atual

    distancia_restante = posicao_alvo - posicao_atual

    # Direção do movimento
    if distancia_restante > 0:
        direcao = 1
    elif distancia_restante < 0:
        direcao = -1
    else:
        estado = STEPDOWN
        return

    # Velocidade normalizada para a escala usada pelo EV3
    velocidade_ev3 = (velocidade_atual / velocidade_max) * 100

    if velocidade_ev3 > 100:
        velocidade_ev3 = 100
    elif velocidade_ev3 < -100:
        velocidade_ev3 = -100

    # Equivalente ao GetCompareCounts() do EV3
    antecipacao = abs(velocidade_ev3) / 2

    # Verifica se já chegou na região de desaceleração
    if abs(distancia_restante) <= antecipacao:
        estado = STEPDOWN
        return

    # RUN: mantém velocidade constante
    velocidade_desejada = velocidade_max * direcao

    # Erro de velocidade
    erro_velocidade = velocidade_desejada - velocidade_atual

    # Termo proporcional
    P = erro_velocidade * kp_velocidade

    # Controle incremental
    pwm_atual += P

    # Saturação
    if pwm_atual > 4095:
        pwm_atual = 4095
    elif pwm_atual < -4095:
        pwm_atual = -4095

    # Proteção semelhante ao dRegulateSpeed() do EV3
    if velocidade_desejada > 0 and pwm_atual < 0:
        pwm_atual = 0
    elif velocidade_desejada < 0 and pwm_atual > 0:
        pwm_atual = 0

    m1.pwm(int(pwm_atual))

    print("RUN",
          "Pos:", posicao_atual,
          "Restante:", distancia_restante,
          "VelDesejada:", velocidade_desejada,
          "VelAtual:", velocidade_atual,
          "Antecipacao:", antecipacao,
          "PWM:", pwm_atual
    )

def executar_stepdown():
    global estado
    global velocidade_desejada
    global pwm_atual

    distancia_restante = posicao_alvo - posicao_atual

    # Direção
    if distancia_restante > 0:
        direcao = 1
    elif distancia_restante < 0:
        direcao = -1
    else:
        estado = BRAKED
        return

    velocidade_ev3_desejada = distancia_restante

    # EV3 trabalha com velocidade entre -100 e +100
    if velocidade_ev3_desejada > 100:
        velocidade_ev3_desejada = 100

    elif velocidade_ev3_desejada < -100:
        velocidade_ev3_desejada = -100

    # Velocidade atual convertida para escala EV3
    velocidade_ev3_atual = (velocidade_atual / velocidade_max) * 100

    if velocidade_ev3_atual > 100:
        velocidade_ev3_atual = 100

    elif velocidade_ev3_atual < -100:
        velocidade_ev3_atual = -100

    # Se ainda estamos acima de 5 e o motor está mais
    # rápido que o TargetSpeed, LEGO força TargetSpeed = 1
    # =====================================================

    if abs(velocidade_ev3_desejada) > 5:
        if (velocidade_ev3_desejada * direcao < velocidade_ev3_atual * direcao):
            velocidade_ev3_desejada = 1 * direcao
            
    # Volta da escala EV3 para nossa velocidade real
    velocidade_desejada = (velocidade_ev3_desejada / 100) * velocidade_max

    # REGULADOR DE VELOCIDADE
    erro_velocidade = (velocidade_desejada - velocidade_atual)

    P = erro_velocidade * kp_velocidade

    pwm_atual += P

    # Saturação
    if pwm_atual > 4095:
        pwm_atual = 4095

    elif pwm_atual < -4095:
        pwm_atual = -4095

    # Mesmo bloqueio de inversão usado pelo dRegulateSpeed()
    if velocidade_desejada > 0 and pwm_atual < 0:
        pwm_atual = 0

    elif velocidade_desejada < 0 and pwm_atual > 0:
        pwm_atual = 0

    m1.pwm(int(pwm_atual))

    print(
        "STEPDOWN",
        "Pos:", posicao_atual,
        "Restante:", distancia_restante,
        "VelEV3:", velocidade_ev3_desejada,
        "VelDesejada:", velocidade_desejada,
        "VelAtual:", velocidade_atual,
        "PWM:", pwm_atual
    )
    

def executar_breake():
    m1.brake()
    
# --------------------- Função Principal --------------------- #
while True:
    atualizar_encoder()

    if estado == STEPUP:
        executar_stepup()

    elif estado == RUN:
        executar_run()

    elif estado == STEPDOWN:
        executar_stepdown()

    elif estado == BRAKED:
        executar_brake()

    sleep_ms(10)