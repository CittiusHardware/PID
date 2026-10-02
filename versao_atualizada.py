from time import ticks_us, ticks_diff, ticks_add, sleep_us
from mihuMotor import *
# from mihuEncoder import getEncoderSnapshot

# ESTADOS
STEPUP = 0
RUN = 1
FINALIZADO = 2
nomes = ("STEPUP", "RUN", "FINALIZADO")

# POSICAO
posicao_inicial = m1.read()
posicao_atual = posicao_inicial
posicao_anterior = posicao_inicial

distancia_total = 3 * 720

# DIVISAO DA TRAJETORIA
rampa_stepup = distancia_total * 0.10          # 10% da trajetória para STEPUP
distancia_run = distancia_total - rampa_stepup # Todo o restante será RUN

# VALORES PID DE VELOCIDADE
kp = 0.05
ki = 0.0
kd = 0.3

# VARIAVEIS GERAIS
estado = STEPUP
P = 0
I = 0
D = 0

pwm = 0
erro_anterior = 0
pid_run_inicializado = False
amostras_atuais = 4

# DEBUG
ultimo_debug_us = 0
estado_anterior_debug = -1
intervalo_debug_us = 20_000      # 20 ms
log_debug = []
velocidades_run = []
debug_impresso = False
max_log_debug = 500

# CONTROLE
periodo_controle_us = 2_000       # 2 ms
proximo_ciclo = ticks_add(ticks_us(), periodo_controle_us)
timeout_velocidade_us = 100_000   # 100 ms
tempo_anterior = 0


# VELOCIDADES
velocidade_atual = 0
velocidade_desejada = 0
vel_normalizada_desejada = 0
vel_normalizada_atual = 0

# Indica que atualizar_encoder() acabou de produzir uma nova velocidade filtrada válida.
velocidade_nova = False

# Velocidade máxima desejada
velocidade_max = 500

# Velocidade física correspondente a 100 na escala normalizada
velocidade_escala_100 = 1000

# POSICAO / DISTANCIA
deslocamento_total = 0
distancia_restante = distancia_total

# STEPUP
stepup_inicializado = False
posicao_inicial_stepup = 0
rampa_offset = 0
rampa_factor = 0


# ============================================================
# FUNCOES AUXILIARES
# ============================================================
def limpar_pid():
    global P
    global I
    global D
    global erro_anterior

    P = 0
    I = 0
    D = 0
    erro_anterior = 0
    

def regular_velocidade():
    global pwm
    global P
    global I
    global D
    global erro_anterior
    global vel_normalizada_desejada
    global vel_normalizada_atual
    global pid_run_inicializado
    
    # CONVERTE VELOCIDADE DESEJADA PARA ESCALA -100 ... +100
    vel_normalizada_desejada = (velocidade_desejada / velocidade_escala_100) * 100

    # Limite da velocidade desejada
    if vel_normalizada_desejada > 100:
        vel_normalizada_desejada = 100

    elif vel_normalizada_desejada < -100:
        vel_normalizada_desejada = -100

    # Limite da velocidade atual
    if vel_normalizada_atual > 100:
        vel_normalizada_atual = 100

    elif vel_normalizada_atual < -100:
        vel_normalizada_atual = -100

    atualizar_pid = True

    if estado == RUN:        
        if not velocidade_nova:
            atualizar_pid = False

    # PID
    if atualizar_pid:

        erro_velocidade = (vel_normalizada_desejada - vel_normalizada_atual)
        
        # PROPORCIONAL
        P = erro_velocidade * kp

        # INTEGRAL 
        I = (I * 0.9 + erro_velocidade * ki)
        
        # DERIVADA
        if estado == RUN and not pid_run_inicializado:
            erro_anterior = erro_velocidade
            D = 0
            pid_run_inicializado = True
            
        else:
            D = (erro_velocidade - erro_anterior) * kd

        # Guarda erro para próxima atualização
        erro_anterior = erro_velocidade

        # CONTROLADOR INCREMENTAL
        pwm = (pwm + P + I + D)

        # NAO PERMITE INVERSAO DO PWM
        if velocidade_desejada > 0 and pwm < 0:
            pwm = 0

        elif velocidade_desejada < 0 and pwm > 0:
            pwm = 0

    m1.pwm(int(pwm))


# LEITURA DO ENCODER E CALCULO DA VELOCIDADE
def atualizar_encoder():

    global posicao_atual
    global posicao_anterior

    global deslocamento_total
    global distancia_restante

    global velocidade_atual
    global vel_normalizada_atual

    global amostras_atuais
    global tempo_anterior
    global velocidade_nova

    velocidade_nova = False
    
    if estado == RUN:
        amostras_atuais = 16
    else:
        if abs(vel_normalizada_atual) > 80:
            amostras_atuais = 64

        elif abs(vel_normalizada_atual) > 60:
            amostras_atuais = 32

        elif abs(vel_normalizada_atual) > 40:
            amostras_atuais = 16

        else:
            amostras_atuais = 4



    # LEITURA ATUAL
    (posicao_atual, tempo_evento_atual, posicao_referencia,tempo_referencia,
     historico_ok, ) = mihuEncoder.getEncoderWindowSnapshot(1, amostras_atuais, )
    
    # DESLOCAMENTO RELATIVO AO INICIO
    deslocamento_total = (posicao_atual - posicao_inicial)
    distancia_restante = (distancia_total - deslocamento_total)
    
    # Ainda nao existe timestamp valido
    if tempo_evento_atual == 0:
        return

    # Ainda não temos dois instantes para calcular velocidade.
    if tempo_anterior == 0:
        posicao_anterior = posicao_atual
        tempo_anterior = tempo_evento_atual
        return

    # Nao houve nova transição do encoder
    if tempo_evento_atual == tempo_anterior:
        tempo_atual = ticks_us()
        
        # Depois de 100 ms sem mudança considera velocidade igual a zero.
        if ticks_diff(tempo_atual, tempo_anterior) >= timeout_velocidade_us:

            if (velocidade_atual != 0 or vel_normalizada_atual != 0):
                velocidade_atual = 0
                vel_normalizada_atual = 0
                velocidade_nova = True

        return

    # MARCA O EVENTO ATUAL COMO PROCESSADO
    tempo_anterior = tempo_evento_atual
    posicao_anterior = posicao_atual
    
    # Não há amostras o suficiente
    if not historico_ok:
        return
    
    # Velocidade na janela de amostras
    delta_posicao = (posicao_atual - posicao_referencia)
    delta_tempo_us = ticks_diff(tempo_evento_atual, posicao_referencia)
    
    if delta_tempo_us <= 0:
        return

    velocidade_atual = ((delta_posicao * 1_000_000) / delta_tempo_us)
    # Normaliza velocidade 
    vel_normalizada_atual = (velocidade_atual / velocidade_escala_100) * 100

    # Limita -100 ... +100
    if vel_normalizada_atual > 100:
        vel_normalizada_atual = 100

    elif vel_normalizada_atual < -100:
        vel_normalizada_atual = -100

    # Nova velocidade válida
    velocidade_nova = True


# ============================================================
# FUNÇÕES PARA MAQUINA DE ESTADOS
# ============================================================
def executar_stepup():
    global estado
    global velocidade_desejada
    global stepup_inicializado
    global posicao_inicial_stepup
    global rampa_offset
    global rampa_factor
    global pwm
    global pid_run_inicializado
    global velocidade_nova
    
    if deslocamento_total >= distancia_total:
        velocidade_desejada = 0
        pwm = 0
        m1.pwm(0)
        estado = FINALIZADO
        return

    # INICIALIZA STEPUP
    if not stepup_inicializado:

        # Posição física onde começou a rampa
        posicao_inicial_stepup = posicao_inicial

        # Equivalente ao RampUpOffset
        rampa_offset = velocidade_atual

        # Velocidade final da rampa
        velocidade_alvo = velocidade_max

        # Equivalente ao RampUpFactor
        rampa_factor = ((velocidade_alvo - rampa_offset) * 1000) / rampa_stepup
        stepup_inicializado = True

    # QUANTO JA PERCORREMOS NO STEPUP
    deslocamento = (posicao_atual - posicao_inicial_stepup)

    if deslocamento < 0:
        deslocamento = 0

    # AINDA ESTA DENTRO DA RAMPA
    if deslocamento < rampa_stepup:
        
        velocidade_desejada = (rampa_offset + (deslocamento * rampa_factor) / 1000)
        
        # Velocidade mínima equivalente a 6%
        velocidade_minima = (velocidade_escala_100 * 0.06)

        if abs(velocidade_desejada) < velocidade_minima:
            velocidade_desejada = velocidade_minima

        # Segurança
        if velocidade_desejada > velocidade_max:
            velocidade_desejada = velocidade_max

        elif velocidade_desejada < -velocidade_max:
            velocidade_desejada = -velocidade_max

    # TERMINOU STEPUP
    else:
        velocidade_desejada = velocidade_max
        stepup_inicializado = False
        limpar_pid()
        pid_run_inicializado = False
        velocidade_nova = False
        estado = RUN

def executar_run():
    global estado
    global velocidade_desejada
    global pwm

    if deslocamento_total >= distancia_total:
        velocidade_desejada = 0
        pwm = 0
        limpar_pid()
        m1.pwm(0)
        estado = FINALIZADO
        return

    # RUN
    velocidade_desejada = velocidade_max


# ============================================================
# DEBUG
# ============================================================
def debug_controle():
    global ultimo_debug_us
    global estado_anterior_debug
    global debug_impresso
    
    if debug_impresso:
        return

    agora = ticks_us()

    if estado != FINALIZADO:

        mudou_estado = (estado != estado_anterior_debug)
        passou_tempo = (ticks_diff(agora, ultimo_debug_us) >= intervalo_debug_us)

        if (not mudou_estado and not passou_tempo):
            return

        ultimo_debug_us = agora
        estado_anterior_debug = estado

        if len(log_debug) < max_log_debug:
            log_debug.append((estado, deslocamento_total, distancia_restante, velocidade_atual,
                              velocidade_desejada, vel_normalizada_atual,vel_normalizada_desejada,
                              amostras_atuais, velocidade_nova, P, I, D, pwm))
        return

    debug_impresso = True

    # HISTORICO
    for dados in log_debug:
        (estado_log, desloc_log, rest_log, v_log, vd_log,
         vn_log,vnd_log, amostras_log, nova_v_log, p_log,
         i_log, d_log, pwm_log) = dados

        print(nomes[estado_log],
#             "| Pos:",desloc_log,
#             "| Rest:", rest_log,
            "| V:", v_log,
            "| VD:", vd_log,
            "| Vn:", vn_log,
            "| VnD:", vnd_log,
            "| Amostras:", amostras_log,
#             "| NovaV:", nova_v_log,
            "| P:", p_log,
            "| I:", i_log,
            "| D:", d_log,
            "| PWM:", pwm_log
        )
        
    print()
    print("========== FIM DEBUG ==========")

# ============================================================
# LOOP PRINCIPAL
# ============================================================
while True:

    atualizar_encoder()

    if estado == STEPUP:
        executar_stepup()

    elif estado == RUN:
        executar_run()

    elif estado == FINALIZADO:
        pwm = 0
        velocidade_desejada = 0
        m1.pwm(0)

    # REGULADOR
    if estado in (STEPUP, RUN):
        regular_velocidade()

    # DEBUG
    debug_controle()

    # LOOP DE 2 ms
    restante = ticks_diff(proximo_ciclo, ticks_us())

    if restante > 0:
        sleep_us(restante)

    proximo_ciclo = ticks_add(proximo_ciclo, periodo_controle_us)