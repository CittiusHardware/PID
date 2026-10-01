from time import ticks_us, ticks_diff, ticks_add, sleep_us
from mihuMotor import *

# ESTADOS
STEPUP = 0
RUN = 1
STEPDOWN = 2
BRAKED = 3

# POSICAO
angulo = 360
posicao_atual = m1.read()
posicao_alvo = 1.8 * angulo				# 1° corresponde a ~2
posicao_inicial = posicao_atual

distancia_total = abs(posicao_alvo - posicao_inicial)

# DIVISÃO DOS PASSOS DO PID
rampa_stepup = distancia_total * 0.1 		# Reservando 10% da trajetoria para a rampa de aceleração
rampa_stepdown = distancia_total * 0.167 	# Reservando 16.7% da trajetoria para a rampa de desaceleração
distancia_run = distancia_total - (rampa_stepup + rampa_stepdown)

# VALORES PID
kp_brake = 10
kp = 0.5
ki = 0.01
kd = 0.0

# Direção original do movimento
if posicao_alvo > posicao_atual:
    direcao = 1
else:
    direcao = -1
    
# --------------------- VARIAVEIS --------------------- #
estado = 0

P = 0
I = 0
D = 0

# Para Debug
ultimo_debug_us = 0
estado_anterior_debug = -1
intervalo_debug_us = 20000   # 20 ms
log_debug = []
debug_impresso = False
max_log_debug = 500

# Para controle
periodo_controle_us = 4000
proximo_ciclo = ticks_add(ticks_us(), periodo_controle_us)

# Para amostras
posicao = []
tempo = []
max_amostras = 64
amostras_atuais = 4

pwm = 0
pwm_limite = 1000

erro_anterior = 0

# Velocidades Globais
velocidade_atual = 0
velocidade_desejada = 0
vel_normalizada_desejada = 0
vel_normalizada_atual = 0
velocidade_max = 500

# Variaveis para rampa de decida
stepdown_inicializado = False
posicao_inicial_stepdown = 0
rampa_down_offset = 0
rampa_down_factor = 0

# Variaveis para rampa de subida
stepup_inicializado = False
posicao_inicial_stepup = 0
rampa_offset = 0
rampa_factor = 0

# --------------------- Funções Auxiliares --------------------- #
def limpar_pid():
    global P, I, D, erro_anterior

    P = 0
    I = 0
    D = 0
    erro_anterior = 0
    
    
def atualizar_encoder():
    global posicao_atual
    global velocidade_atual
    global amostras_atuais
    global velocidade_percentual
    global distancia_restante
    global vel_normalizada_atual

    posicao_atual = m1.read()
    tempo_atual = ticks_us()

    # Guarda posição e tempo
    posicao.append(posicao_atual)
    tempo.append(tempo_atual)

    # Calcula a distancia faltante para alcançar o alvo
    distancia_restante = ((posicao_alvo - posicao_atual) * direcao)

    # Mantém máximo de 64 amostras
    while len(posicao) > max_amostras:
        posicao.pop(0)
        tempo.pop(0)
        
    if abs(vel_normalizada_atual) > 80:
        amostras_atuais = 64      # 64

    elif abs(vel_normalizada_atual) > 60:
        amostras_atuais = 32      # 32

    elif abs(vel_normalizada_atual) > 40:
        amostras_atuais = 16      # 16

    else:
        amostras_atuais =  4      # 4
        
    quantidade = min(amostras_atuais, len(posicao))
    
    if quantidade < 2:
        velocidade_atual = 0
        vel_normalizada_atual = 0
        return
        
    # Calcula a velocidade 
    delta_posicao = posicao[-1] - posicao[-quantidade]
    delta_tempo_us = ticks_diff(tempo[-1], tempo[-quantidade])

    if delta_tempo_us <= 0:
        velocidade_atual = 0
        vel_normalizada_atual = 0
        return

    velocidade_atual = (delta_posicao / (delta_tempo_us / 1_000_000))
    vel_normalizada_atual = ((velocidade_atual / velocidade_max) * 100)
    
    
def executar_stepup():
    global estado
    global velocidade_desejada
    global distancia_restante
    global stepup_inicializado

    global posicao_inicial_stepup 
    global rampa_offset
    global rampa_factor

    if not stepup_inicializado:

        # Já está no alvo
        if distancia_restante == 0:
            velocidade_desejada = 0
            estado = BRAKED
            return

        # Posição onde começou a rampa
        posicao_inicial_stepup = posicao_inicial

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
        limpar_pid()
        estado = RUN

def executar_run():
    global estado
    global velocidade_desejada
    
    deslocamento_total = (posicao_atual - posicao_inicial) * direcao
    
    inicio_stepdown = rampa_stepup + distancia_run
    
    if deslocamento_total >= inicio_stepdown:
        limpar_pid()
        estado = STEPDOWN
        return

    # RUN: mantém velocidade desejada constante
    velocidade_desejada = velocidade_max * direcao


def executar_stepdown():
    global estado
    global velocidade_desejada
    global stepdown_inicializado
    
    global posicao_inicial_stepdown
    global rampa_down_offset
    global rampa_down_factor
    
    if not stepdown_inicializado:
        # Posição onde começou a rampa de desaceleração
        posicao_inicial_stepdown = posicao_inicial + (direcao * (distancia_total - rampa_stepdown))

        # Velocidade desejada no momento em que começa o STEP_DOWN
        rampa_down_offset = velocidade_desejada
        
        # Velocidade final da rampa
        velocidade_alvo_down = 0
        
        # Fator da rampa
        rampa_down_factor = ((velocidade_alvo_down - rampa_down_offset) * 1000) / rampa_stepdown
        stepdown_inicializado = True

    # Quanto ainda falta até o alvo
    deslocamento = (posicao_atual - posicao_inicial_stepdown) * direcao

    # Rampa de aceleração
    if deslocamento < rampa_stepdown:
        
        nova_velocidade = (rampa_down_offset + (deslocamento * rampa_down_factor) / 1000)

        # Velocidade mínima enquanto ainda não terminou a rampa
        velocidade_minima = (velocidade_max * 0.04)

        if abs(nova_velocidade) > velocidade_minima:
            velocidade_desejada = nova_velocidade

    # Terminou a rampa
    else:
        velocidade_desejada = 0
        stepdown_inicializado = False
        limpar_pid()
        estado = BRAKED
        executar_brake()


def executar_brake():
    global pwm
    global velocidade_desejada

    velocidade_desejada = 0
    pwm = 0

    m1.brake()
#     
#     erro_brake = posicao_atual - posicao_alvo
#     
#     if erro_brake > 2.0:
#         pwm = -(erro_brake * kp_brake)
#         m1.pwm(int(pwm))
    
def regular_velocidade():
    global pwm
    global P
    global I
    global D
    global erro_anterior
    global vel_normalizada_desejada
    
    # CONVERTE PARA ESCALA EV3 (-100 +100)
    vel_normalizada_desejada = (velocidade_desejada / velocidade_max) * 100

    # Limita TargetSpeed
    if vel_normalizada_desejada > 100:
        vel_normalizada_desejada = 100

    elif vel_normalizada_desejada < -100:
        vel_normalizada_desejada = -100
    
    # REGULADOR DE VELOCIDADE
    erro_velocidade = (vel_normalizada_desejada - vel_normalizada_atual)

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

    # Calcula novo PWM
    pwm = pwm + P + I + D

    # SATURAÇÃO
    if pwm > pwm_limite:
        pwm = pwm_limite

    elif pwm < -pwm_limite:
        pwm = -pwm_limite
    
    # não deixa a potência inverter
    if velocidade_desejada > 0 and pwm < 0:
        pwm = 0
    elif velocidade_desejada < 0 and pwm > 0:
        pwm = 0

    # MOTOR
    m1.pwm(int(pwm))


def debug_controle():
    global ultimo_debug_us
    global estado_anterior_debug
    global debug_impresso

    if debug_impresso:
        return

    agora = ticks_us()

    mudou_estado = (estado != estado_anterior_debug)
    passou_tempo = (ticks_diff(agora, ultimo_debug_us) >= intervalo_debug_us)
    motor_parado = (estado == STEPDOWN and pwm == 0 and velocidade_atual == 0)

    # Grava enquanto nao encerra o percurso
    if estado != BRAKED and not motor_parado:

        if not mudou_estado and not passou_tempo:
            return

        ultimo_debug_us = agora
        estado_anterior_debug = estado

        if len(log_debug) < max_log_debug:
            log_debug.append((estado, posicao_atual, distancia_restante,
                velocidade_atual, velocidade_desejada, vel_normalizada_atual,
                vel_normalizada_desejada, amostras_atuais, P, I, D, pwm))
        return

    # Encerrou o percurso
    debug_impresso = True

    nomes = ("STEPUP", "RUN", "STEPDOWN", "BRAKED")

    print()
    print("========== DEBUG CONTROLE ==========")

    print("Alvo:", posicao_alvo)
    print("Posicao final:", posicao_atual)
    print("Encoder raw:", m1.read())
    print("Erro final:", posicao_alvo - posicao_atual)

    print("Registros:", len(log_debug))
    print()

    for dados in log_debug:
        (estado_log, pos_log, rest_log, v_log, vd_log, vn_log, vnd_log,
         amostras_log,  p_log, i_log, d_log, pwm_log) = dados

        print(
            nomes[estado_log],
            "| Pos:", pos_log,
            "| Rest:", rest_log,
            "| V:", v_log,
            "| VD:", vd_log,
            "| Vn:", vn_log,
            "| VnD:", vnd_log,
            "| Amostras:", amostras_log,
            "| P:", p_log,
            "| I:", i_log,
            "| D:", d_log,
            "| PWM:", pwm_log
        )

    print()
    print("========== FIM DEBUG ==========")
    
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

    if estado in (STEPUP, RUN, STEPDOWN):
        regular_velocidade()
        
    debug_controle()
    restante = ticks_diff(proximo_ciclo, ticks_us())

    if restante > 0:
        sleep_us(restante)

    proximo_ciclo = ticks_add(proximo_ciclo, periodo_controle_us)



