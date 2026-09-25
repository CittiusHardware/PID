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
kp = 0.1
ki = 0.01
kd = 0.0

# --------------------- VARIAVEIS --------------------- #
estado = 0

P = 0
I = 0
D = 0

erro_anterior = 0
contador_debug = 0

fator_antecipacao = 1.5

posicao = []
tempo = []

posicao_alvo = 620
margem_distancia_alvo = 100

amostras_longe = 15
amostras_perto = 5

velocidade_atual = 0
velocidade_desejada = 0
velocidade_max = 800

pwm_atual = 0
stepup_inicializado = False
stepdown_inicializado = False

posicao_inicial_stepdown = 0
distancia_stepdown = 0

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
        
    posicao_prevista = posicao_atual + (velocidade_ev3 * fator_antecipacao)
    
    if direcao > 0:
        if posicao_prevista  >= posicao_alvo:
            estado = STEPDOWN
            return
    else:
        if posicao_prevista <= posicao_alvo:
            estado = STEPDOWN
            return

    # RUN: mantém velocidade constante
    velocidade_desejada = velocidade_max * direcao


def executar_stepdown():
    global estado
    global velocidade_desejada

    global stepdown_inicializado
    global posicao_inicial_stepdown
    global distancia_stepdown

    if not stepdown_inicializado:

        posicao_inicial_stepdown = posicao_atual

        distancia_stepdown = (posicao_alvo - posicao_atual) * direcao

        # Se já chegou/passou do alvo
        if distancia_stepdown <= 0:
            velocidade_desejada = 0
            estado = BRAKED
            executar_brake()
            return

        stepdown_inicializado = True

    distancia_restante = (posicao_alvo - posicao_atual) * direcao

    # Chegou ou passou do alvo
    if distancia_restante <= 0:
        velocidade_desejada = 0
        stepdown_inicializado = False
        estado = BRAKED
        executar_brake()
        return

    # RAMPA DE DESACELERAÇÃO
    fator_restante = (distancia_restante / distancia_stepdown)

    # Segurança
    if fator_restante > 1:
        fator_restante = 1

    elif fator_restante < 0:
        fator_restante = 0

    # VELOCIDADE DESEJADA
    velocidade_desejada = (velocidade_max * fator_restante * direcao)
    
    # VELOCIDADE MÍNIMA
    velocidade_minima = (velocidade_max * 0.01)

    if abs(velocidade_desejada) < velocidade_minima:
        velocidade_desejada = (velocidade_minima * direcao)
        
# def executar_stepdown():
#     global estado
#     global velocidade_desejada
#     global velocidade_atual
#     
#     global stepdown_inicializado
#     global posicao_inicial_stepdown
#     global distancia_stepdown
#     
#     if not stepdown_inicializado:
#         posicao_inicial_stepdown = posicao_atual
#         
#         distancia_stepdown = abs(posicao_alvo - posicao_atual)
#         
#         if distancia_stepdown <= 0:
#             velocidade_desejada = 0
#             estado = BRAKED
#             executar_brake()
#             return
#         
#         stepdown_inicializado = True
#         
#         if direcao > 0:
#             if posicao_atual >= posicao_alvo:
#                 velocidade_desejada = 0
#                 stepdown_inicializado = False
#                 estado = BRAKED
#                 executar_brake()
#                 return
#             
#         else:
#             if posicao_atual <= posicao_alvo:
#                 velocidade_desejada = 0
#                 stepdown_inicializado = False
#                 estado = BRAKED
#                 executar_brake()
#                 return
# 
#         distancia_restante = abs(posicao_alvo - posicao_atual)
#         
#         # Fator de desaceleração
#         fator_restante = (distancia_restante / distancia_stepdown)
#         
#         if fator_restante > 1:
#             fator_restante = 1
#         elif fator_restante < 0:
#             fator_restante = 0
# 
#         # TargetSpeed
#         velocidade_desejada = (velocidade_max * fator_restante * direcao)
# 
#         # Velocidade mínima enquanto ainda está andando
#         velocidade_minima = (velocidade_max * 0.01)
# 
#         if abs(velocidade_desejada) < velocidade_minima:
#             velocidade_desejada = (velocidade_minima * direcao)
        
        
        
#     velocidade_ev3_desejada = distancia_restante
# 
#     # EV3 trabalha com velocidade entre -100 e +100
#     if velocidade_ev3_desejada > 100:
#         velocidade_ev3_desejada = 100
# 
#     elif velocidade_ev3_desejada < -100:
#         velocidade_ev3_desejada = -100
# 
#     # Velocidade atual convertida para escala EV3
#     velocidade_ev3_atual = (velocidade_atual / velocidade_max) * 100
# 
#     if velocidade_ev3_atual > 100:
#         velocidade_ev3_atual = 100
# 
#     elif velocidade_ev3_atual < -100:
#         velocidade_ev3_atual = -100
#         
#     # Se ainda estamos acima de 5 e o motor está mais
#     # rápido que o TargetSpeed, LEGO força TargetSpeed = 1
#     if abs(velocidade_ev3_desejada) > 5:
#         if (velocidade_ev3_desejada * direcao < velocidade_ev3_atual * direcao):
#             velocidade_ev3_desejada = 1 * direcao
#             
#     # Volta da escala EV3 para nossa velocidade real
#     velocidade_desejada = (velocidade_ev3_desejada / 100) * velocidade_max
#     
#     if direcao > 0:
#         if posicao_atual >= posicao_alvo:
#             velocidade_desejada = 0
#             estado = BRAKED
#             executar_brake()
#             return
#         
#     else:
#         if posicao_atual <= posicao_alvo:
#             velocidade_desejada = 0
#             estado = BRAKED
#             executar_brake()
#             return


def executar_brake():
    global pwm_atual

    m1.brake()
    pwm_atual = 0
    
    
def regular_velocidade():
    global pwm_atual
    global P
    global I
    global D
    global erro_anterior
    
    # CONVERTE PARA ESCALA EV3 (-100 +100)
    velocidade_desejada_ev3 = (velocidade_desejada / velocidade_max) * 100
    velocidade_atual_ev3 = (velocidade_atual / velocidade_max) * 100

    # Limita TargetSpeed
    if velocidade_desejada_ev3 > 100:
        velocidade_desejada_ev3 = 100

    elif velocidade_desejada_ev3 < -100:
        velocidade_desejada_ev3 = -100
    
    # REGULADOR DE VELOCIDADE
    erro_velocidade = (velocidade_desejada_ev3 - velocidade_atual_ev3)

    # Proporcional 
    P = (erro_velocidade * kp)
    
    # Integral
    I = (I * 0.9) + (erro_velocidade * ki)
    
    # Limite da integral
    if I > 100:
        I = 100
    elif I < -100:
        I = -100
    
    # Derivada
    D = (erro_velocidade - erro_anterior) * kd
    
    # Guarda erro
    erro_anterior = erro_velocidade

    # Controle incremental
    pwm_atual = pwm_atual + P + I + D

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
    
# --------------------- Função Principal --------------------- #
while True:
    atualizar_encoder()
    
    contador_debug += 1

    if contador_debug >= 25:
        contador_debug = 0
        print(
            "Estado", estado,
            "Pos:", posicao_atual,
            "VD:", velocidade_desejada,
            "V:", velocidade_atual,
            "P:", P,
            "I:", I,
            "D:", D,
            "PWM:", pwm_atual
        )
        
    if estado == STEPUP:
        executar_stepup()

    elif estado == RUN:
        executar_run()

    elif estado == STEPDOWN:
        executar_stepdown()

    elif estado == BRAKED:
        executar_brake()

    if estado == STEPUP or estado == RUN or estado == STEPDOWN:
        regular_velocidade()

    sleep_ms(2)

