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
kp_velocidade = 0.1

# --------------------- VARIAVEIS --------------------- #
estado = 0

posicao = []
tempo = []

posicao_alvo = 480
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

    global stepup_inicializado
    global posicao_inicial_stepup
    global direcao

    global rampa_stepup
    global rampa_offset
    global rampa_factor

    if not stepup_inicializado:

        distancia_total = abs(posicao_alvo - posicao_atual)

        # Já está no alvo
        if distancia_total == 0:
            velocidade_desejada = 0
            estado = BRAKED
            return

        # Direção original do movimento
        if posicao_alvo > posicao_atual:
            direcao = 1
        else:
            direcao = -1

        # Posição onde começou a rampa
        posicao_inicial_stepup = posicao_atual

        # Máximo: 80 pulsos
        # Movimento curto: no máximo metade da distância
        rampa_stepup = min(80, max(1, distancia_total // 2))

        # Equivalente ao RampUpOffset
        rampa_offset = velocidade_atual

        # Velocidade final da rampa
        velocidade_alvo = (velocidade_max * direcao)

        # Equivalente ao RampUpFactor
        rampa_factor = ((velocidade_alvo - rampa_offset) * 1000) / rampa_stepup

        stepup_inicializado = True

    # Quanto já percorremos desde o início da rampa
    deslocamento = (posicao_atual - posicao_inicial_stepup) * direcao

    # Evita deslocamento negativo por ruído/recuo inicial
    if deslocamento < 0:
        deslocamento = 0

    if deslocamento < rampa_stepup:
        
        velocidade_desejada = (rampa_offset + (deslocamento * rampa_factor) / 1000)
        velocidade_minima = (velocidade_max * 0.06)

        if abs(velocidade_desejada) < velocidade_minima:
            velocidade_desejada = (velocidade_minima * direcao)

        # Segurança
        if velocidade_desejada > velocidade_max:
            velocidade_desejada = velocidade_max

        elif velocidade_desejada < -velocidade_max:
            velocidade_desejada = -velocidade_max

    else:
        velocidade_desejada = (velocidade_max * direcao)
        stepup_inicializado = False
        estado = RUN

def executar_run():
    global estado
    global velocidade_desejada
    global velocidade_atual

    distancia_restante = posicao_alvo - posicao_atual

    # Velocidade normalizada para a escala usada pelo EV3
    velocidade_ev3 = (velocidade_atual / velocidade_max) * 100

#     if velocidade_ev3 > 100:
#         velocidade_ev3 = 100
#     elif velocidade_ev3 < -100:
#         velocidade_ev3 = -100
        
    posicao_prevista = posicao_atual + (velocidade_ev3 / 2)
    
    if direcao > 0:
        if posicao_prevista  >= posicao_alvo:
            estado = STEPDOWN
            return
    else:
        if posicao_prevista <= posicao_alvo:
            estado = STEPDOWN
            return

#     # Equivalente ao GetCompareCounts() do EV3
#     antecipacao = abs(velocidade_ev3) / 2
#     
# 
#     # Verifica se já chegou na região de desaceleração
#     if abs(distancia_restante) <= antecipacao:
#         estado = STEPDOWN
#         return

    # RUN: mantém velocidade constante
    velocidade_desejada = velocidade_max * direcao

def executar_stepdown():
    global estado
    global velocidade_desejada
    global velocidade_atual

    distancia_restante = posicao_alvo - posicao_atual

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
    if abs(velocidade_ev3_desejada) > 5:
        if (velocidade_ev3_desejada * direcao < velocidade_ev3_atual * direcao):
            velocidade_ev3_desejada = 1 * direcao
            
    # Volta da escala EV3 para nossa velocidade real
    velocidade_desejada = (velocidade_ev3_desejada / 100) * velocidade_max
    
    if direcao > 0:
        if posicao_atual >= posicao_alvo:
            velocidade_desejada = 0
            estado = BRAKED
            return
        
    else:
        if posicao_atual <= posicao_alvo:
            velocidade_desejada = 0
            estado = BRAKED
            return


def executar_brake():
    print("Estado", estado,
        "Pos:", posicao_atual,
        "VelDesejada:", velocidade_desejada,
        "Vel:", velocidade_atual,
        "PWM:", pwm_atual
    )
    m1.brake()
    
    
def regular_velocidade():
    global pwm_atual
    
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

    print("Estado", estado,
        "Pos:", posicao_atual,
        "VelDesejada:", velocidade_desejada,
        "Vel:", velocidade_atual,
        "PWM:", pwm_atual
    )
    
# --------------------- Função Principal --------------------- #
while True:
    atualizar_encoder()

    estado_anterior = estado

    # Atualiza o estado e calcula velocidade_desejada
    if estado == STEPUP:
        executar_stepup()

    elif estado == RUN:
        executar_run()

    elif estado == STEPDOWN:
        executar_stepdown()

    elif estado == BRAKED:
        
        executar_brake()

    # Se houve mudança de estado, não utiliza a velocidade_desejada do estado anterior
    if estado != estado_anterior:
        sleep_ms(10)
        continue

    # Estados que utilizam controle de velocidade
    if estado == STEPUP or estado == RUN or estado == STEPDOWN:
        regular_velocidade()

    sleep_ms(10)

