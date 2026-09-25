try:
    from mihuPinMap import MOTOR_CHANNELS
except ImportError:
    from lib.mihuPinMap import MOTOR_CHANNELS

from .mihuPCA import pca
from .mihuEncoder import (
    getEncoder,
    setEncoder,
    clearEncoder,
    encoderInfo,
)
from machine import Timer
from time import ticks_ms, ticks_diff

# ============================================================
# PORTAS PÚBLICAS
# ============================================================
# O aluno pode usar M1, M2, M3 e M4 nas funções antigas.
# Para uso orientado a objetos, utilize m1, m2, m3 e m4.

M1, M2, M3, M4 = 1, 2, 3, 4

# Cache das instâncias para que cada porta possua um único objeto.
_motors = {}

# GERENCIADOR GLOBAL DO HOLD
hold_timer = None

def hold_timer_callback(timer):
    for motor in _motors.values():
        if motor.hold_enabled:
            motor.hold_update()

def _clamp(value, minimum, maximum):
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _norm_motor_id(motor_id):
    """Normaliza a porta usando a mesma numeração de MOTOR_CHANNELS
    Nesta controladora:
        M1 = 1
        M2 = 2
        M3 = 3
        M4 = 4

    Aceita:
        M1, M2, M3, M4
        "M1", "M2", "M3", "M4"
        1, 2, 3, 4

    Retorna:
        1, 2, 3 ou 4
    """

    if isinstance(motor_id, str):
        text = motor_id.strip().upper()

        if (
            len(text) == 2
            and text[0] == "M"
            and text[1] in "1234"
        ):
            return int(text[1])

        raise ValueError(
            "motor_id invalido: {}".format(motor_id)
        )

    motor_id = int(motor_id)

    if 1 <= motor_id <= 4:
        return motor_id

    raise ValueError(
        "Motor invalido. Use M1, M2, M3, M4 ou 1..4."
    )


class mihuMotor:
    """
    Controle simples de motor para alunos.

    Exemplos:
        motor = mihuMotor(M1)
        motor.speed(100)
        motor.speed(-50)
        motor.stop()
        motor.brake()
        motor.hold()

    A função speed() utiliza porcentagem de potência:
        -100 = potência máxima no sentido contrário
           0 = motor livre/desligado
         100 = potência máxima no sentido principal
    """        
    
    def __init__(self, motor_id):
        internal_id = _norm_motor_id(motor_id)

        if internal_id not in MOTOR_CHANNELS:
            raise ValueError(
                "Motor nao encontrado no mapa: {}".format(internal_id))

        self.motor_id = internal_id
        self.port = internal_id
        self.chA, self.chB = MOTOR_CHANNELS[internal_id]

        self._speed = 0
        self._pwm = 0
        self._state = "coast"
        
        " -------- HOLD POR PID -------- "
        self.hold_enabled = False
        self.hold_position = 0
        self.hold_error = None
        self.hold_print_count = 0
        
        # Ganhos
        self.hold_kp = 17.0
        self.hold_ki = 20.0
        self.hold_kd = 0.7
        
        # Regiões
        self.hold_tolerance = 2
        self.hold_integral_zone = 120
        
        # PWM
        self.hold_pwm_min_move = 250
        self.hold_pwm_start = 600
        self.hold_pwm_max = 4095
        
        # Integral
        self.hold_integral_max = 300
        self.hold_vel_integral_max = 30
        
        # Máquina de estados
        self.hold_vel_start = 15
        self.hold_vel_run = 35
        self.hold_moving = False
        self.hold_stop_count = 0        
        
        # Filtro
        self.hold_alpha = 0.25
        self.hold_velocity = 0.0
        
        # Estados do PID
        self.hold_integral = 0.0
        self.hold_last_position = 0
        self.hold_last_error = 0
        self.hold_last_time = 0
        
    # ========================================================
    # VELOCIDADE / POTÊNCIA
    # ========================================================
    def pwm(self, value=None):
        if value is None:
            return self._pwm

        value = int(value)

        if value > 4095:
            value = 4095
        elif value < -4095:
            value = -4095

        if value > 0:
            pca.duty_raw(self.chA, value)
            pca.duty_raw(self.chB, 0)

        elif value < 0:
            pca.duty_raw(self.chA, 0)
            pca.duty_raw(self.chB, -value)

        else:
            self.stop()
            return 0

        self._pwm = value
        self._state = "running"

        return value
    
    def speed(self, value=None):
        if value is None:
            return self._speed

        value = int(_clamp(float(value), -100, 100))

        if value > 0:
            pca.percent(self.chA, value)
            pca.percent(self.chB, 0)

        elif value < 0:
            pca.percent(self.chA, 0)
            pca.percent(self.chB, -value)

        else:
            self.stop()
            return 0

        self._speed = value
        self._state = "running"

        return value

    def set(self, value):
        """
        Define a potência do motor entre -100 e 100.

        Exemplo:
            m1.set(50)
            m1.set(-50)
        """

        return self.speed(value)

    def setSpeed(self, value):
        """Compatibilidade com a biblioteca antiga."""
        return self.speed(value)

    def dc(self, duty):
        """Apelido compatível para controle de potência -100..100."""
        return self.speed(duty)

    # Apelido tolerante ao erro de digitação mostrado no exemplo.
    def speet(self, value=None):
        return self.speed(value)

    # ========================================================
    # ENCODER
    # ========================================================

    def read(self):
        """
        Retorna a contagem atual do encoder.

        A contagem começa na primeira chamada a read() ou clear().
        """

        return getEncoder(
            self.motor_id
        )

    def clear(self):
        """
        Zera somente a contagem do encoder.

        O motor não é desligado por esta função.
        """

        clearEncoder(
            self.motor_id
        )

        return 0

    def setPosition(self, value):
        """
        Define manualmente a contagem do encoder.
        """

        return setEncoder(
            self.motor_id,
            value,
        )

    def encoder(self):
        return self.read()

    def position(self):
        return self.read()

    # ========================================================
    # PARADAS
    # ========================================================

    def stop(self):
        """
        Para de alimentar o motor e permite que ele gire livremente.
        """

        pca.percent(self.chA, 0)
        pca.percent(self.chB, 0)

        self._speed = 0
        self._pwm = 0
        self.hold_enabled = False
        self._state = "coast"

        return True

    def coast(self):
        """Apelido de stop()."""
        return self.stop()

    def brake(self):
        """
        Aplica frenagem elétrica passiva na ponte H.
        """

        pca.percent(self.chA, 100)
        pca.percent(self.chB, 100)

        self._speed = 0
        self.hold_enabled = False
        self._state = "brake"

        return True

    # Apelido tolerante ao erro de digitação mostrado no exemplo.
    def bkark(self):
        return self.brake()

#     def hold(self, power=20):
#         """
#         Aplica frenagem elétrica contínua.
# 
#         Sem realimentação por encoder, esta função não controla um
#         ângulo exato; ela mantém a ponte H em frenagem.
# 
#         power:
#             Intensidade de 0 a 100. O padrão é 20.
#         """
# 
#         power = int(_clamp(float(power), 0, 100))
# 
#         pca.percent(self.chA, power)
#         pca.percent(self.chB, power)
# 
#         self._speed = 0
#         self._state = "hold"
#         self._hold_power = power
# 
#         return True

    def hold(self, position=None):
        global hold_timer

        if position is None:
            position = self.read()

        self.hold_position = int(position)

        # Reseta controlador
        posicao_atual = self.read()

        self.hold_integral = 0.0
        self.hold_velocity = 0.0
        self.hold_last_position = posicao_atual

        self.hold_last_error = (self.hold_position - posicao_atual)

        self.hold_moving = False
        self.hold_stop_count = 0
        self.hold_last_time = ticks_ms()
        self.hold_error = None

        # Ativa PID
        self.hold_enabled = True
        self._state = "hold"

        # Inicia o serviço somente na primeira vez
        if hold_timer is None:
            hold_timer = Timer(1)
            hold_timer.init(period=10, mode=Timer.PERIODIC, callback=hold_timer_callback)

        return True
        
        
    def hold_update(self, debug=False):
        if not self.hold_enabled:
            return

        # ----- tempo ----- #
        agora = ticks_ms()
        dt_ms = ticks_diff(agora, self.hold_last_time)
        self.hold_last_time = agora

        if dt_ms <= 0:
            dt_ms = 1

        dt = dt_ms / 1000.0

        # ----- tempo ----- #
        posicao_atual = self.read()
        erro = (self.hold_position - posicao_atual)

        # ----- velocidade ----- #
        velocidade = (posicao_atual - self.hold_last_position) / dt
        self.hold_last_position = posicao_atual

        # ----- filtro passa-baixa ----- #
        self.hold_velocity += (self.hold_alpha * (velocidade - self.hold_velocity))
        
        # ========================================================
        # DETECÇÃO DO ESTADO MECÂNICO
        # ========================================================
        if self.hold_moving:
            if (abs(self.hold_velocity) <= self.hold_vel_start):
                self.hold_stop_count += 1
                
                if self.hold_stop_count >= 10:
                    self.hold_moving = False
                    self.hold_stop_count = 0
            else:
                self.hold_stop_count = 0
        else:
            if abs(self.hold_velocity) >= self.hold_vel_run:
                self.hold_moving = True
                self.hold_stop_count = 0
                
        motor_parado = not self.hold_moving
          
        # ----- PROPORCIONAL ------ #
        termo_p = self.hold_kp * erro

        # ----- DERIVATIVO ----- #
        termo_d = (-self.hold_kd * self.hold_velocity)
        
        # ----- PASSAGEM PELO ZERO ----- #
        cruzou_zero = (erro * self.hold_last_error < 0)
        if cruzou_zero:
            self.hold_integral = 0.0
        
        # ----- INTEGRAL ------ #
        dentro_zona_integral = (abs(erro) > self.hold_tolerance and abs(erro) <= self.hold_integral_zone)
        eixo_quase_parado = (abs(self.hold_velocity) <= self.hold_vel_integral_max)
        
        # So integra quando o motor praticamente nao esta andando e o erro persiste 
        if (dentro_zona_integral and eixo_quase_parado):
            self.hold_integral += (self.hold_ki * erro * dt)

            # Anti-windup
            if (self.hold_integral > self.hold_integral_max):
                self.hold_integral = (self.hold_integral_max)
                
            elif (self.hold_integral < -self.hold_integral_max):
                self.hold_integral = (-self.hold_integral_max)

        else:
            self.hold_integral *= 0.95

        # ----- CONTROLE ----- #
        controle_bruto = (termo_p + self.hold_integral + termo_d)

        # ----- HOLD ----- #
        if abs(erro) <= self.hold_tolerance:  
            self.hold_integral = 0.0
           
            pca.percent(self.chA, 100)
            pca.percent(self.chB, 100)
            
            self._pwm = 0
            self._state = "hold"
            self.hold_last_error = erro

            return

        else:
            controle = controle_bruto
            
            if motor_parado:
                pwm_min_atual = self.hold_pwm_start
            else:
                pwm_min_atual = self.hold_pwm_min_move
                
            if controle * erro > 0:
                if (controle > 0 and controle < pwm_min_atual):
                    controle = pwm_min_atual

                elif (controle < 0 and controle > -pwm_min_atual):
                    controle = -pwm_min_atual

            # ----- LIMITE MÁXIMO ----- #
            if controle > self.hold_pwm_max:
                controle = self.hold_pwm_max

            elif controle < -self.hold_pwm_max:
                controle = -self.hold_pwm_max

            controle = int(controle)
            
            # ----- APLICANDO PWM ----- #
            if controle > 0:
                pca.duty_raw(self.chA, controle)
                pca.duty_raw(self.chB, 0)

            elif controle < 0:
                pca.duty_raw(self.chA, 0)
                pca.duty_raw(self.chB, -controle)
            
            else:
                pca.duty_raw(self.chA, 0)
                pca.duty_raw(self.chB, 0)

        self._pwm = controle
        self._state = "hold"
        self.hold_last_error = erro

        # DEBUG
        if debug:
            self.hold_print_count += 1
            if self.hold_print_count >= 10:
                print(
                    "Pos:", posicao_atual,
                    "Erro:", erro,
                    "Vel:", round(self.hold_velocity, 1),
                    "P:", round(termo_p, 1),
                    "I:", round(self.hold_integral, 1),
                    "D:", round(termo_d, 1),
                    "RAW:", round(controle_bruto, 1),
                    "PWM:", round(controle, 1)
                )
                self.hold_print_count = 0

            
    def drop(self):
        "Desativa o controle de posição e deixa o motor girar livremente "
        self.hold_enabled = False

        # LIMPA O PID
        self.hold_integral = 0.0
        self.hold_velocity = 0.0
        self.hold_moving = False
        self.hold_stop_count = 0
        self.hold_error = None

        # MOTOR LIVRE
        pca.percent(self.chA, 0)
        pca.percent(self.chB, 0)

        self._speed = 0
        self._pwm = 0
        self._state = "coast"

        return True
    # ========================================================
    # INFORMAÇÕES
    # ========================================================

    def state(self):
        """
        Retorna: running, coast, brake ou hold.
        """
        return self._state

    def is_running(self):
        return self._state == "running" and self._speed != 0

    def isRunning(self):
        return self.is_running()

    def info(self):
        """
        Retorna motor, potência, estado e encoder.
        """

        encoder_data = encoderInfo(
            self.motor_id
        )

        return {
            "port": self.port,
            "speed": self._speed,
            "state": self._state,
            "encoder": encoder_data["count"],
            "encoder_pin_a": encoder_data["pin_a"],
            "encoder_pin_b": encoder_data["pin_b"],
            "channels": (
                self.chA,
                self.chB,
            ),
        }

    def reset(self):
        """
        Para o motor e zera o encoder.
        """

        self.stop()
        self.clear()
        return True

    def __repr__(self):
        return "mihuMotor(M{}, speed={}, state='{}')".format(
            self.port,
            self._speed,
            self._state,
        )


def getMotor(motor_id):
    """
    Retorna sempre a mesma instância para a porta solicitada.
    """

    internal_id = _norm_motor_id(motor_id)
    motor = _motors.get(internal_id)

    if motor is None:
        motor = mihuMotor(internal_id)
        _motors[internal_id] = motor

    return motor


# ============================================================
# OBJETOS PRONTOS PARA O ALUNO
# ============================================================

m1 = getMotor(M1)
m2 = getMotor(M2)
m3 = getMotor(M3)
m4 = getMotor(M4)

# Nomes alternativos descritivos.
motor1 = m1
motor2 = m2
motor3 = m3
motor4 = m4


# ============================================================
# FUNÇÕES ANTIGAS
# ============================================================

def setMotorPin(motor_id, speed):
    return getMotor(motor_id).speed(speed)


def setMotor(motor_id, speed):
    return getMotor(motor_id).speed(speed)


def stopAll():
    m1.stop()
    m2.stop()
    m3.stop()
    m4.stop()


def brakeAll():
    m1.brake()
    m2.brake()
    m3.brake()
    m4.brake()


# Nome de classe alternativo em padrão CamelCase.
MihuMotor = mihuMotor

