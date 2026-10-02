from time import ticks_us, ticks_diff, ticks_add, sleep_us
from mihuMotor import *

# ESTADOS
STEPUP = 0
RUN = 1
STEPDOWN = 2
BRAKED = 3

# POSICAO
angulo = 360
posicao_inicial = m1.read()
deslocamento_alvo = int(1.96 * angulo) # 1° corresponde a ~2 pulsos
posicao_alvo = posicao_inicial + deslocamento_alvo
posicao_anterior = posicao_inicial
distancia_total = abs(deslocamento_alvo)

# DIVISÃO DOS PASSOS DO PID
rampa_stepup = distancia_total * 0.10 		# Reservando 10% da trajetoria para a rampa de aceleração
rampa_stepdown = distancia_total * 0.20 	# Reservando 16.7% da trajetoria para a rampa de desaceleração
distancia_run = distancia_total - (rampa_stepup + rampa_stepdown)

# VALORES PID
kp_brake = 150
kp = 0.05
ki = 0.0
kd = 0.1

# Direção original do movimento
if posicao_alvo > posicao_inicial:
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
periodo_controle_us = 2000
proximo_ciclo = ticks_add(ticks_us(), periodo_controle_us)
timeout_velocidade_us = 100_000
tempo_anterior = ticks_us()

# Para amostras
posicao = []
tempo = []
amostras_atuais = 4

pwm = 0
erro_anterior = 0
erro_brake = 0

# Velocidades Globais
velocidade_atual = 0
velocidade_desejada = 0
velocidade_instantanea = 0
vel_normalizada_desejada = 0
vel_normalizada_atual = 0
velocidade_max = 500
velocidade_escala_100 = 1000

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
    global posicao_anterior

    global velocidade_atual
    global velocidade_instantanea
    global vel_normalizada_atual

    global amostras_atuais
    global distancia_restante
    global tempo_anterior

    # LEITURA ATUAL
    posicao_atual = m1.read()
    tempo_atual = ticks_us()

    # Distância restante não depende de nova borda
    distancia_restante = ((posicao_alvo - posicao_atual) * direcao)

    # NÃO HOUVE NOVA ALTERAÇÃO DO ENCODER
    if posicao_atual == posicao_anterior:
        # Somente depois de muito tempo sem alteração é considerado que o motor parou.
        if ticks_diff(tempo_atual, tempo_anterior) >= timeout_velocidade_us:
            velocidade_atual = 0
            velocidade_instantanea = 0
            vel_normalizada_atual = 0
        return


    # HOUVE NOVA ALTERAÇÃO DO ENCODER
    posicao.append(posicao_atual)
    tempo.append(tempo_atual)

    # Atualiza posicao e tempo anterior
    tempo_anterior = tempo_atual
    posicao_anterior = posicao_atual

    # BUFFER de 65 pontos permitem calcular uma janela de até 64 intervalos.
    while len(posicao) > 65:
        posicao.pop(0)
        tempo.pop(0)


    # Se nao existem 2 eventos, mantem velocidade_atual como estava
    if len(posicao) < 2:
        return

    # VELOCIDADE INSTANTÂNEA
    delta_posicao = (posicao[-1] - posicao[-2])
    delta_tempo_us = ticks_diff(tempo[-1], tempo[-2])

    if delta_tempo_us <= 0:
        return

    velocidade_instantanea = (delta_posicao / (delta_tempo_us / 1_000_000))
    velocidade_instantanea = (velocidade_instantanea / velocidade_escala_100) * 100 # Normaliza velocidade instantanea

    # ESCOLHE JANELA
    if estado == RUN:
        amostras_atuais = 16
        
    else:
        if abs(vel_normalizada_atual) > 80:
            amostras_atuais = 64      # 64

        elif abs(vel_normalizada_atual) > 60:
            amostras_atuais = 32      # 32

        elif abs(vel_normalizada_atual) > 40:
            amostras_atuais = 16      # 16

        else:
            amostras_atuais =  4      # 4

    # Se nao existe amostras o suficiente para a janela escolhida, mantem a velocidade anterior
    if (len(posicao) - 1) < amostras_atuais:
        return

    # VELOCIDADE FILTRADA
    delta_posicao = (posicao[-1] - posicao[-1 - amostras_atuais])
    delta_tempo_us = ticks_diff(tempo[-1], tempo[-1 - amostras_atuais])

    if delta_tempo_us <= 0:
        return

    velocidade_atual = (delta_posicao /(delta_tempo_us / 1_000_000))
    vel_normalizada_atual = (velocidade_atual / velocidade_escala_100) * 100
    
    # Limita -100 ... +100
    if vel_normalizada_atual > 100:
        vel_normalizada_atual = 100

    elif vel_normalizada_atual < -100:
        vel_normalizada_atual = -100
    
    
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
        velocidade_minima = (velocidade_escala_100 * 0.06)

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

''' O RUN pode trabalhar de 2 formas:
* Percorrendo um caminho predefindo (distancia_run)
* Estipulando quando começar a desacelerar pela previsao prevista'''
def executar_run():
    global estado
    global velocidade_desejada
    
    deslocamento_total = (posicao_atual - posicao_inicial) * direcao
#     
#     inicio_stepdown = rampa_stepup + distancia_run
#     ----------- 1 opção de lógica -----------       
#     if deslocamento_total >= inicio_stepdown:
#         limpar_pid()
#         estado = STEPDOWN
#         return
#     ----------- 2 opção de lógica -----------       
    deslocamento_previsto = (deslocamento_total + abs(vel_normalizada_atual / 2))
    if deslocamento_previsto >= distancia_total:
        limpar_pid()
        estado = STEPDOWN
        return

    # RUN: mantém velocidade desejada constante
    velocidade_desejada = velocidade_max * direcao

''' O STEPDOWN pode trabalhar de 2 formas:
* Rampa linear: a velocidade cai linearmente conforme a distancia percorrida
* A distancia determina a velocidade desejada'''
def executar_stepdown():
    global estado
    global velocidade_desejada
    global stepdown_inicializado
    
    global posicao_inicial_stepdown
    global rampa_down_offset
    global rampa_down_factor
    
    if not stepdown_inicializado:
#     ----------- 1 opção de lógica -----------       
        # Posição onde começou a rampa de desaceleração
#         posicao_inicial_stepdown = posicao_inicial + (direcao * (distancia_total - rampa_stepdown))
        posicao_inicial_stepdown = posicao_atual

        # Velocidade desejada no momento em que começa o STEP_DOWN
        rampa_down_offset = abs(velocidade_atual) * direcao
        
        # Velocidade final da rampa
        velocidade_alvo_down = 0
        
        # Fator da rampa
        rampa_down_factor = ((velocidade_alvo_down - rampa_down_offset) * 1000) / rampa_stepdown
        stepdown_inicializado = True

    # Quanto ainda falta até o alvo
    deslocamento = (posicao_atual - posicao_inicial_stepdown) * direcao

    if deslocamento < rampa_stepdown:
        if(velocidade_atual > 0):
            nova_velocidade = (rampa_down_offset + (deslocamento * rampa_down_factor) / 1000)
            velocidade_minima = (velocidade_escala_100 * 0.04) # Velocidade mínima enquanto ainda não terminou a rampa

            if abs(nova_velocidade) > velocidade_minima:
                velocidade_desejada = nova_velocidade
            
#     ----------- 2 opção de lógica -----------       
#         erro_posicao = posicao_alvo - posicao_atual
#         distancia_para_alvo = erro_posicao * direcao
#         
#         if distancia_para_alvo > 0:
#             vel_normalizada_alvo = erro_posicao
#             
#             if vel_normalizada_alvo > 100:
#                 vel_normalizada_alvo = 100
#             elif vel_normalizada_alvo < -100:
#                 vel_normalizada_alvo = -100
#             
#             if abs(vel_normalizada_alvo) > 5:
#                 if (vel_normalizada_alvo * direcao < vel_normalizada_atual * direcao):
#                     vel_normalizada_alvo = 1 * direcao
#         
#             velocidade_desejada = ((vel_normalizada_alvo / 100) * velocidade_escala_100)
        
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
    global erro_brake

    velocidade_desejada = 0
    pwm = 0
    m1.brake()

#     erro_brake = posicao_atual - posicao_alvo
#     
#     if abs(erro_brake) > 0.5:
#         pwm = -(erro_brake * kp_brake)
#         
#         # SATURAÇÃO
#         if pwm > 4095:
#             pwm = 4095
# 
#         elif pwm < -4095:
#             pwm = -4095
#             
#         m1.pwm(int(pwm))
    
def regular_velocidade():
    global pwm
    global P
    global I
    global D
    global erro_anterior
    global vel_normalizada_desejada
    global vel_normalizada_atual
    
    # CONVERTE PARA ESCALA EV3 (-100 +100)
    vel_normalizada_desejada = (velocidade_desejada / velocidade_escala_100) * 100

    # Limita Velocidade Desejada
    if vel_normalizada_desejada > 100:
        vel_normalizada_desejada = 100

    elif vel_normalizada_desejada < -100:
        vel_normalizada_desejada = -100
        
    # Limita Velocidade Atual
    if vel_normalizada_atual > 100:
        vel_normalizada_atual = 100

    elif vel_normalizada_atual < -100:
        vel_normalizada_atual = -100
    
    # REGULADOR DE VELOCIDADE
    erro_velocidade = (vel_normalizada_desejada - vel_normalizada_atual)

    # Proporcional 
    P = (erro_velocidade * kp)
    
    # Integral
    I = (I * 0.9) + (erro_velocidade * ki)
    
    # Derivada
    D = (erro_velocidade - erro_anterior) * kd
    
    # Guarda erro
    erro_anterior = erro_velocidade

    # Calcula novo PWM
    pwm = pwm + P + I + D
    
    # não deixa a potência inverter
    if velocidade_desejada > 0 and pwm < 0:
        pwm = 0
    elif velocidade_desejada < 0 and pwm > 0:
        pwm = 0

    # MOTOR
    m1.pwm(int(pwm))

# Variáveis globais
braked_inicio_us = None
posicao_braked_inicial = None

def debug_controle():
    global ultimo_debug_us
    global estado_anterior_debug
    global debug_impresso
    global braked_inicio_us
    global posicao_braked_inicial

    if debug_impresso:
        return

    agora = ticks_us()

    mudou_estado = (estado != estado_anterior_debug)
    passou_tempo = (ticks_diff(agora, ultimo_debug_us) >= intervalo_debug_us)

    # Continua armazenando o debug normalmente
    if estado != BRAKED:

        # Só grava quando muda de estado ou quando passa o intervalo do debug
        if not mudou_estado and not passou_tempo:
            return

        ultimo_debug_us = agora
        estado_anterior_debug = estado

        if len(log_debug) < max_log_debug:

            log_debug.append((estado, posicao_atual, distancia_restante, velocidade_atual, velocidade_desejada,
                              amostras_atuais, P, I, D, rampa_down_offset, rampa_down_factor, pwm))

        return


    # ENTROU NO BRAKED
    if braked_inicio_us is None:

        braked_inicio_us = agora
        posicao_braked_inicial = posicao_atual

        estado_anterior_debug = BRAKED
        ultimo_debug_us = agora

        print()
        print("========== ENTROU NO BRAKED ==========")

        print(
            "BRAKED",
            "| Pos:", posicao_atual,
            "| Alvo:", posicao_alvo,
            "| Erro:", erro_brake,
            "| PWM:", pwm,
            "| V:", velocidade_atual,
            "| Avanco:", posicao_atual - posicao_braked_inicial
        )

    # OBSERVA O MOTOR DURANTE O BRAKED
    if ticks_diff(agora, ultimo_debug_us) >= intervalo_debug_us:
        ultimo_debug_us = agora

        print(
            "BRAKED",
            "| Pos:", posicao_atual,
            "| Raw:", m1.read(),
            "| V:", velocidade_atual,
            "| Avanco:", posicao_atual - posicao_braked_inicial
        )


    # AINDA NÃO PASSARAM 500 ms
    if ticks_diff(agora, braked_inicio_us) < 500_000:
        return

    # PASSARAM 500 ms
    debug_impresso = True
    posicao_final_real = m1.read()

    nomes = ("STEPUP","RUN", "STEPDOWN", "BRAKED")

    print()
    print("========== DEBUG CONTROLE ==========")
    print("Alvo:", posicao_alvo)
    print("Posicao ao entrar BRAKED:", posicao_braked_inicial)
    print("Posicao apos 500 ms:", posicao_final_real)
    print("Avanco apos BRAKED:", posicao_final_real - posicao_braked_inicial)
    print("Erro final real:", posicao_alvo - posicao_final_real)
    print("Registros:", len(log_debug))
    print()

    # IMPRIME O HISTÓRICO DO MOVIMENTO
    for dados in log_debug:
        (estado_log, pos_log, rest_log, v_log, vd_log, amostras_log,
         p_log, i_log, d_log, rd_offset, rd_factor, pwm_log) = dados
        
        print(
            nomes[estado_log],
            "| Pos:", pos_log,
            "| Rest:", rest_log,
            "| V:", v_log,
            "| VD:", vd_log,
            "| Amostras:", amostras_log,
            "| P:", p_log,
            "| I:", i_log,
            "| D:", d_log,
            "| Offset:", rd_offset,
            "| Factor:", rd_factor,
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



