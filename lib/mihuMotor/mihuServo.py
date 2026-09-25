try:
    from mihuPinMap import SERVO_CHANNELS
except ImportError:
    from lib.mihuPinMap import SERVO_CHANNELS

from .mihuPCA import pca
import time as utime


# ============================================================
# PORTAS PÚBLICAS
# ============================================================

S1, S2, S3, S4 = 1, 2, 3, 4
S5, S6, S7, S8 = 5, 6, 7, 8

_servos = {}


# ============================================================
# PERFIS PRÉ-DEFINIDOS DE SERVOMOTOR
# ============================================================

# Os nomes são strings para ocupar pouca memória e permitir:
#     s1.config(GEEK_SERVO)
#     s1.config("geekServo")

GEEK_SERVO = "geekservo"
SG90 = "sg90"
SG90_180 = "sg90_180"
SG90_150 = SG90
MG995 = "mg995"

# Apelidos em escrita mais amigável.
geekServo = GEEK_SERVO
sg90Servo = SG90
mg995Servo = MG995

# Formato:
# nome: (min_us, max_us, min_angle, max_angle, frequency)
SERVO_PRESETS = {
    GEEK_SERVO: (1000, 3040, 0.0, 360.0, 50),
    SG90:       (1000, 2000, 0.0, 150.0, 50),
    SG90_180:   (500, 2400, 0.0, 180.0, 50),
    MG995:      (500, 2500, 0.0, 180.0, 50),
}


def _normalize_preset_name(name):
    """Normaliza nomes como geekServo, GEEK_SERVO e mg-995."""

    text = str(name).strip().lower()

    for character in (" ", "_", "-"):
        text = text.replace(character, "")

    aliases = {
        "geekservo": GEEK_SERVO,
        "geek": GEEK_SERVO,
        "gs360": GEEK_SERVO,

        "sg90": SG90,
        "sg90150": SG90,
        "sg90safe": SG90,

        "sg90180": SG90_180,
        "sg90extended": SG90_180,

        "mg995": MG995,
        "towerpromg995": MG995,
    }

    if text not in aliases:
        raise ValueError(
            "Perfil de servo desconhecido: {}".format(name)
        )

    return aliases[text]


def getServoPreset(name):
    """Retorna uma cópia da configuração de um perfil."""

    preset_name = _normalize_preset_name(name)
    values = SERVO_PRESETS[preset_name]

    return {
        "name": preset_name,
        "min_us": values[0],
        "max_us": values[1],
        "min_angle": values[2],
        "max_angle": values[3],
        "frequency": values[4],
    }


def servoPresets():
    """Retorna os nomes dos perfis disponíveis."""

    return tuple(SERVO_PRESETS.keys())


# ============================================================
# HELPERS
# ============================================================

def _clamp(value, minimum, maximum):
    if value < minimum:
        return minimum
    if value > maximum:
        return maximum
    return value


def _norm_servo_id(servo_id):
    """
    Aceita S1..S8, "S1".."S8" ou 1..8.
    """

    if isinstance(servo_id, str):
        text = servo_id.strip().upper()

        if (
            len(text) == 2
            and text[0] == "S"
            and text[1] in "12345678"
        ):
            return int(text[1])

        raise ValueError(
            "servo_id invalido: {}".format(servo_id)
        )

    servo_id = int(servo_id)

    if 1 <= servo_id <= 8:
        return servo_id

    raise ValueError(
        "Servo invalido. Use S1..S8 ou 1..8."
    )


def _resolve_servo_channel(public_id):
    """
    Compatível com mapas indexados em 1..8 ou 0..7.

    A presença da chave 8 indica mapa 1-based.
    A presença da chave 0, sem a chave 8, indica mapa 0-based.
    """

    if 8 in SERVO_CHANNELS:
        map_id = public_id
    elif 0 in SERVO_CHANNELS:
        map_id = public_id - 1
    else:
        map_id = public_id

    if map_id in SERVO_CHANNELS:
        return SERVO_CHANNELS[map_id]

    raise ValueError(
        "Servo nao encontrado no mapa: {}".format(public_id)
    )


# ============================================================
# CLASSE
# ============================================================

class mihuServo:
    """
    Servo simples para alunos.

    Exemplos:
        s1.on()
        s1.off()
        s1.pwm(2048)
        s1.percentual(50)
        s1.angle(90)
        s1.angle(180, time=1000)
        s1.config(min_us=500, max_us=2500)
    """

    def __init__(
        self,
        servo_id,
        min_us=500,
        max_us=2500,
        min_angle=0,
        max_angle=180,
        frequency=50,
        initial_angle=90,
    ):
        self.servo_id = _norm_servo_id(servo_id)
        self.port = self.servo_id
        self.channel = _resolve_servo_channel(self.servo_id)

        self._min_us = int(min_us)
        self._max_us = int(max_us)
        self._min_angle = float(min_angle)
        self._max_angle = float(max_angle)
        self._frequency = int(frequency)
        self._angle = float(initial_angle)
        self._enabled = False
        self._preset = None

        self._validate_config()

    # ========================================================
    # CONFIGURAÇÃO / CALIBRAÇÃO
    # ========================================================

    def _validate_config(self):
        if self._min_us < 0:
            raise ValueError("min_us nao pode ser negativo.")

        if self._max_us <= self._min_us:
            raise ValueError("max_us deve ser maior que min_us.")

        if self._max_angle <= self._min_angle:
            raise ValueError(
                "max_angle deve ser maior que min_angle."
            )

        if self._frequency < 24 or self._frequency > 1526:
            raise ValueError("Frequencia do servo invalida.")

    def config(
        self,
        min_us=None,
        max_us=None,
        min_angle=None,
        max_angle=None,
        frequency=None,
        preset=None,
    ):
        """
        Consulta ou altera a calibração do servo.

        Perfil pronto:
            s1.config(GEEK_SERVO)
            s1.config(SG90)
            s1.config(MG995)

        Também aceita o nome:
            s1.config("geekServo")
            s1.config("sg90")
            s1.config("mg995")

        Configuração manual:
            s1.config(
                min_us=500,
                max_us=2500,
                min_angle=0,
                max_angle=180,
                frequency=50
            )

        Consulta:
            print(s1.config())
        """

        # Permite passar o perfil como primeiro argumento:
        #     s1.config(SG90)
        if preset is None and isinstance(min_us, str):
            preset = min_us
            min_us = None

        if preset is not None:
            profile = getServoPreset(preset)

            min_us = profile["min_us"]
            max_us = profile["max_us"]
            min_angle = profile["min_angle"]
            max_angle = profile["max_angle"]
            frequency = profile["frequency"]
            selected_preset = profile["name"]
        else:
            selected_preset = None

        if (
            min_us is None
            and max_us is None
            and min_angle is None
            and max_angle is None
            and frequency is None
        ):
            return {
                "preset": self._preset,
                "min_us": self._min_us,
                "max_us": self._max_us,
                "min_angle": self._min_angle,
                "max_angle": self._max_angle,
                "frequency": self._frequency,
            }

        old_values = (
            self._min_us,
            self._max_us,
            self._min_angle,
            self._max_angle,
            self._frequency,
            self._preset,
        )

        try:
            if min_us is not None:
                self._min_us = int(min_us)

            if max_us is not None:
                self._max_us = int(max_us)

            if min_angle is not None:
                self._min_angle = float(min_angle)

            if max_angle is not None:
                self._max_angle = float(max_angle)

            if frequency is not None:
                self._frequency = int(frequency)

            self._validate_config()

            # Uma alteração manual deixa de representar exatamente
            # um perfil conhecido.
            self._preset = selected_preset

        except Exception:
            (
                self._min_us,
                self._max_us,
                self._min_angle,
                self._max_angle,
                self._frequency,
                self._preset,
            ) = old_values
            raise

        pca.freq(self._frequency)
        return self.config()

    def configure(self, *args, **kwargs):
        return self.config(*args, **kwargs)

    def geekServo(self):
        """Seleciona o perfil GeekServo posicional de 360 graus."""
        return self.config(GEEK_SERVO)

    def sg90(self, extended=False):
        """
        Seleciona o perfil SG90.

        extended=False:
            faixa conservadora 1000-2000 us, 0-150 graus.

        extended=True:
            500-2400 us, 0-180 graus.
        """
        return self.config(SG90_180 if extended else SG90)

    def mg995(self):
        """Seleciona o perfil inicial do MG995 posicional."""
        return self.config(MG995)

    def preset(self, name=None):
        """Consulta ou seleciona um perfil de servo."""

        if name is None:
            return self._preset

        return self.config(name)

    def pulse(self, min_us=None, max_us=None):
        """Atalho para consultar ou definir os pulsos mínimo/máximo."""

        if min_us is None and max_us is None:
            return self._min_us, self._max_us

        return self.config(
            min_us=min_us,
            max_us=max_us,
        )

    # ========================================================
    # POSIÇÃO
    # ========================================================

    def _angle_to_us(self, angle):
        angle = _clamp(
            float(angle),
            self._min_angle,
            self._max_angle,
        )

        ratio = (
            (angle - self._min_angle)
            / (self._max_angle - self._min_angle)
        )

        usec = self._min_us + ratio * (
            self._max_us - self._min_us
        )

        return angle, int(usec)

    def _write_angle(self, angle):
        angle, usec = self._angle_to_us(angle)

        if pca.freq() != self._frequency:
            pca.freq(self._frequency)

        pca.servo_us(self.channel, usec)

        self._angle = angle
        self._enabled = True

        return self._clean_angle(angle)

    @staticmethod
    def _clean_angle(value):
        if value == int(value):
            return int(value)
        return value

    def angle(
        self,
        value=None,
        time=0,
        wait=True,
        step_ms=20,
    ):
        """
        Define ou consulta o ângulo.

        Movimento imediato:
            s1.angle(90)

        Movimento suave em 1 segundo:
            s1.angle(180, time=1000)

        time é informado em milissegundos.
        """

        if value is None:
            return self._clean_angle(self._angle)

        target = _clamp(
            float(value),
            self._min_angle,
            self._max_angle,
        )

        duration_ms = max(0, int(time))
        step_ms = max(5, int(step_ms))

        if duration_ms == 0:
            return self._write_angle(target)

        if not wait:
            # Sem uma tarefa de atualização em segundo plano, o modo
            # não bloqueante posiciona imediatamente no alvo.
            return self._write_angle(target)

        start = self._angle
        delta = target - start

        if delta == 0:
            return self._write_angle(target)

        steps = max(1, duration_ms // step_ms)
        actual_step_ms = max(1, duration_ms // steps)

        for index in range(1, steps + 1):
            position = start + (delta * index / steps)
            self._write_angle(position)
            utime.sleep_ms(actual_step_ms)

        return self._write_angle(target)

    def set(
        self,
        value,
        time=0,
    ):
        """
        Define o ângulo do servo.

        Exemplo:
            s1.set(90)
            s1.set(180, time=1000)
        """

        return self.angle(
            value,
            time=time,
        )

    def read(self):
        """
        Retorna o último ângulo comandado.
        """

        return self.angle()

    def clear(self):
        """
        Desliga o pulso do servo.
        """

        self.off()
        return True

    def write(self, value):
        """Compatibilidade: write() é igual a angle()."""
        return self.angle(value)

    def us(self, usec=None):
        """
        Define ou consulta o pulso atual em microssegundos.
        """

        if usec is None:
            _, current_us = self._angle_to_us(self._angle)
            return current_us

        usec = int(_clamp(
            int(usec),
            self._min_us,
            self._max_us,
        ))

        if pca.freq() != self._frequency:
            pca.freq(self._frequency)

        pca.servo_us(self.channel, usec)

        ratio = (
            (usec - self._min_us)
            / (self._max_us - self._min_us)
        )

        self._angle = self._min_angle + ratio * (
            self._max_angle - self._min_angle
        )

        self._enabled = True
        return usec

    def center(self, time=0):
        center_angle = (
            self._min_angle + self._max_angle
        ) / 2.0
        return self.angle(center_angle, time=time)

    # ========================================================
    # CONTROLE DIRETO DO CANAL PCA9685
    # ========================================================

    def pwm(self, value=None):
        """
        Define ou consulta o PWM bruto do canal, de 0 a 4095.

        Exemplos:
            s1.pwm(2048)
            print(s1.pwm())
        """

        if value is None:
            return pca.duty_raw(self.channel)

        value = int(value)

        if value < 0:
            value = 0
        elif value > 4095:
            value = 4095

        pca.duty_raw(self.channel, value)
        self._enabled = value > 0
        return value

    def percentual(self, value=None):
        """
        Define ou consulta a potência do canal entre 0 e 100%.

        Exemplos:
            s1.percentual(50)
            print(s1.percentual())
        """

        if value is None:
            return pca.duty(self.channel)

        value = float(value)

        if value < 0:
            value = 0.0
        elif value > 100:
            value = 100.0

        result = pca.duty(self.channel, value)
        self._enabled = value > 0
        return result

    # Nomes alternativos para compatibilidade.
    percent = percentual
    percentage = percentual
    duty = percentual

    def on(self):
        """Liga continuamente o canal em 100%."""
        pca.on(self.channel)
        self._enabled = True
        return True

    def off(self):
        """Desliga totalmente o canal."""
        pca.off(self.channel)
        self._enabled = False
        return True

    def resume(self):
        """Religa o servo na última posição comandada."""
        return self._write_angle(self._angle)

    def enabled(self):
        return self._enabled

    def __repr__(self):
        return (
            "mihuServo(S{}, angle={}, channel={}, enabled={})"
        ).format(
            self.port,
            self._clean_angle(self._angle),
            self.channel,
            self._enabled,
        )


# ============================================================
# CACHE / OBJETOS PRONTOS
# ============================================================

def getServo(servo_id):
    public_id = _norm_servo_id(servo_id)
    servo = _servos.get(public_id)

    if servo is None:
        servo = mihuServo(public_id)
        _servos[public_id] = servo

    return servo


s1 = getServo(S1)
s2 = getServo(S2)
s3 = getServo(S3)
s4 = getServo(S4)
s5 = getServo(S5)
s6 = getServo(S6)
s7 = getServo(S7)
s8 = getServo(S8)

servo1 = s1
servo2 = s2
servo3 = s3
servo4 = s4
servo5 = s5
servo6 = s6
servo7 = s7
servo8 = s8


# ============================================================
# FUNÇÕES ANTIGAS
# ============================================================

def setServoAngle(servo_id, angle):
    return getServo(servo_id).angle(angle)


def setServo(servo_id, angle):
    return getServo(servo_id).angle(angle)


def setServoUs(servo_id, usec):
    return getServo(servo_id).us(usec)


def servoOff(servo_id):
    return getServo(servo_id).off()


def servoConfig(servo_id, *args, **kwargs):
    return getServo(servo_id).config(*args, **kwargs)


# Nome de classe alternativo em padrão CamelCase.
MihuServo = mihuServo
