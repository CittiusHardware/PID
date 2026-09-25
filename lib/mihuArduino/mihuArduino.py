"""
mihuArduino.py

Funções educacionais inspiradas no Arduino para MicroPython.

Importação:
    from mihuArduino import *

Exemplo:
    pinMode(2, OUTPUT)
    digitalWrite(2, HIGH)

Nenhum GPIO, ADC, PWM ou interrupção é iniciado durante a
importação. Cada recurso é criado somente quando é usado.

Recursos principais:
    GPIO digital
    ADC interno e ADS1115
    PWM
    tons
    touch
    interrupções
    leitura de pulsos
    deslocamento de bits
    tempo
    operações com bits
    execução setup/loop
"""

from machine import Pin, ADC, PWM
from time import (
    sleep_ms,
    sleep_us,
    ticks_ms,
    ticks_us,
    ticks_diff,
)

try:
    from machine import TouchPad
except ImportError:
    TouchPad = None

try:
    from machine import time_pulse_us as _machine_time_pulse_us
except ImportError:
    _machine_time_pulse_us = None

try:
    from machine import disable_irq as _disable_irq
    from machine import enable_irq as _enable_irq
except ImportError:
    _disable_irq = None
    _enable_irq = None

try:
    import random as _random_module
except ImportError:
    _random_module = None

try:
    import sys
except ImportError:
    sys = None

try:
    import select as _serial_select
except ImportError:
    _serial_select = None


VERSION = "1.4.0"


# ============================================================
# CONSTANTES ARDUINO
# ============================================================

INPUT = 0
OUTPUT = 1
INPUT_PULLUP = 2
INPUT_PULLDOWN = 3

LOW = 0
HIGH = 1

CHANGE = 0
RISING = 1
FALLING = 2

LSBFIRST = 0
MSBFIRST = 1


# ============================================================
# ENTRADAS EXTERNAS RJ — ADS1115
# ============================================================

RJ_M1 = 20
RJ_M2 = 21
RJ_M3 = 22
RJ_M4 = 23

_ADS_ID_MAP = {
    RJ_M1: 0,
    RJ_M2: 1,
    RJ_M3: 2,
    RJ_M4: 3,
}

try:
    from builtins import adc_ads as _boot_adc_ads
except Exception:
    _boot_adc_ads = None

_external_adc = _boot_adc_ads


# ============================================================
# ESTADO INTERNO
# ============================================================

_pins = {}
_pin_modes = {}
_adcs = {}
_pwms = {}
_pwm_frequencies = {}
_touchpads = {}
_interrupts = {}
_irq_states = []

_PWM_DEFAULT_FREQUENCY = 1000
_PWM_HARDWARE_MAX = 65535

_analog_read_bits = 12
_analog_write_bits = 8

_yield_callback = None
_internal_yield_callbacks = []
_internal_yield_checked = False


# ============================================================
# CONTROLE DO PROGRAMA
# ============================================================

class StopProgram(Exception):
    """Finaliza run() sem gerar erro para o aluno."""


def setYieldCallback(callback=None):
    """
    Define uma função chamada durante delay() e run().

    O aluno normalmente não precisa usar esta função.
    """

    global _yield_callback

    if callback is not None and not callable(callback):
        raise TypeError(
            "O callback deve ser uma funcao."
        )

    _yield_callback = callback
    return True


def _set_yield_callback(callback):
    """Compatibilidade com o sistema anterior."""

    return setYieldCallback(callback)


def yieldNow():
    """Entrega tempo de execução ao sistema MIHU."""

    global _internal_yield_callbacks
    global _internal_yield_checked

    if _yield_callback is not None:
        _yield_callback()

    # A IMU é opcional. A procura acontece somente no primeiro
    # delay(), evitando dependência obrigatória na importação.
    if not _internal_yield_checked:
        _internal_yield_checked = True

        try:
            from mihuIMU import imu
            _internal_yield_callbacks.append(imu.update)
        except (ImportError, AttributeError):
            pass

        try:
            from mihuButton import button
            _internal_yield_callbacks.append(button.tick)
        except (ImportError, AttributeError):
            pass

    for callback in _internal_yield_callbacks:
        callback()


def stop():
    """Finaliza um programa executado por run()."""

    raise StopProgram()


# ============================================================
# GPIO DIGITAL
# ============================================================

def _normalize_gpio(gpio):
    return int(gpio)


def _release_pwm(gpio):
    gpio = _normalize_gpio(gpio)
    pwm = _pwms.pop(gpio, None)

    if pwm is not None:
        try:
            pwm.duty_u16(0)
        except Exception:
            pass

        try:
            pwm.deinit()
        except Exception:
            pass


def _create_pin(gpio, mode=None):
    gpio = _normalize_gpio(gpio)

    if mode is None:
        return Pin(gpio)

    if mode == OUTPUT:
        return Pin(gpio, Pin.OUT)

    if mode == INPUT:
        return Pin(gpio, Pin.IN)

    if mode == INPUT_PULLUP:
        return Pin(gpio, Pin.IN, Pin.PULL_UP)

    if mode == INPUT_PULLDOWN:
        return Pin(gpio, Pin.IN, Pin.PULL_DOWN)

    raise ValueError(
        "Modo invalido. Use INPUT, OUTPUT, "
        "INPUT_PULLUP ou INPUT_PULLDOWN."
    )


def pinMode(gpio, mode):
    """
    Configura o modo de um GPIO.

    Exemplo:
        pinMode(2, OUTPUT)
        pinMode(3, INPUT_PULLUP)
    """

    gpio = _normalize_gpio(gpio)
    _release_pwm(gpio)

    pin = _create_pin(gpio, mode)
    _pins[gpio] = pin
    _pin_modes[gpio] = mode
    return True


def _digital_pin(gpio, preferred_mode):
    gpio = _normalize_gpio(gpio)
    pin = _pins.get(gpio)
    current_mode = _pin_modes.get(gpio)

    if pin is None:
        pin = _create_pin(
            gpio,
            preferred_mode,
        )
        _pins[gpio] = pin
        _pin_modes[gpio] = preferred_mode

    elif preferred_mode == OUTPUT and current_mode != OUTPUT:
        pinMode(gpio, OUTPUT)
        pin = _pins[gpio]

    return pin


def digitalWrite(gpio, value):
    """
    Escreve HIGH ou LOW.

    Se pinMode() não tiver sido chamado, o GPIO é configurado
    automaticamente como saída.
    """

    gpio = _normalize_gpio(gpio)
    _release_pwm(gpio)

    pin = _digital_pin(gpio, OUTPUT)
    pin.value(HIGH if value else LOW)
    return True


def digitalRead(gpio):
    """
    Retorna HIGH ou LOW.

    Se pinMode() não tiver sido chamado, o GPIO é configurado
    automaticamente como entrada.
    """

    pin = _digital_pin(
        gpio,
        INPUT,
    )

    return HIGH if pin.value() else LOW


def toggle(gpio):
    """Inverte o estado de uma saída digital."""

    gpio = _normalize_gpio(gpio)
    pin = _digital_pin(gpio, OUTPUT)
    value = LOW if pin.value() else HIGH
    pin.value(value)
    return value


# ============================================================
# LEITURA ANALÓGICA
# ============================================================

def useExternalADC(adc):
    """
    Define o objeto ADS1115 usado por RJ_M1 até RJ_M4.

    Não é necessário quando adc_ads já foi criado no boot.
    """

    global _external_adc

    _external_adc = adc
    return True


def analogReadResolution(bits=None):
    """
    Consulta ou define a resolução da leitura do ADC interno.

    Padrão:
        12 bits -> 0 até 4095
    """

    global _analog_read_bits

    if bits is None:
        return _analog_read_bits

    bits = int(bits)

    if bits < 1 or bits > 16:
        raise ValueError(
            "A resolucao deve estar entre 1 e 16 bits."
        )

    _analog_read_bits = bits
    return bits


def _scale_adc_12bit(value):
    bits = _analog_read_bits

    if bits == 12:
        return int(value)

    source_max = 4095
    target_max = (1 << bits) - 1

    return (
        int(value) * target_max
    ) // source_max


def analogRead(pin_or_id):
    """
    Lê uma entrada analógica.

    RJ_M1 até RJ_M4:
        ADS1115 externo, valor bruto assinado.

    Demais números:
        ADC interno do ESP32.
    """

    if (
        isinstance(pin_or_id, int)
        and pin_or_id in _ADS_ID_MAP
        and _external_adc is not None
    ):
        channel = _ADS_ID_MAP[pin_or_id]
        return _external_adc.read(
            channel1=channel
        )

    gpio = _normalize_gpio(pin_or_id)
    adc = _adcs.get(gpio)

    if adc is None:
        adc = ADC(Pin(gpio))

        try:
            adc.atten(ADC.ATTN_11DB)
        except Exception:
            pass

        try:
            adc.width(ADC.WIDTH_12BIT)
        except Exception:
            pass

        _adcs[gpio] = adc

    try:
        raw = adc.read()
    except AttributeError:
        raw = adc.read_u16() >> 4

    return _scale_adc_12bit(raw)


# ============================================================
# PWM / ANALOG WRITE
# ============================================================

def analogWriteResolution(bits=None):
    """
    Consulta ou define a resolução usada por analogWrite().

    Padrão:
        8 bits -> valores de 0 até 255
    """

    global _analog_write_bits

    if bits is None:
        return _analog_write_bits

    bits = int(bits)

    if bits < 1 or bits > 16:
        raise ValueError(
            "A resolucao deve estar entre 1 e 16 bits."
        )

    _analog_write_bits = bits
    return bits


def analogWriteFrequency(gpio, frequency=None):
    """
    Consulta ou define a frequência PWM de um GPIO.
    """

    gpio = _normalize_gpio(gpio)

    if frequency is None:
        return _pwm_frequencies.get(
            gpio,
            _PWM_DEFAULT_FREQUENCY,
        )

    frequency = int(frequency)

    if frequency <= 0:
        raise ValueError(
            "A frequencia deve ser maior que zero."
        )

    _pwm_frequencies[gpio] = frequency
    pwm = _pwms.get(gpio)

    if pwm is not None:
        pwm.freq(frequency)

    return frequency


def analogWrite(gpio, value, freq=None):
    """
    Gera PWM.

    Com resolução padrão de 8 bits:
        analogWrite(2, 0)
        analogWrite(2, 128)
        analogWrite(2, 255)
    """

    gpio = _normalize_gpio(gpio)
    input_max = (1 << _analog_write_bits) - 1

    value = constrain(
        int(value),
        0,
        input_max,
    )

    if freq is None:
        frequency = _pwm_frequencies.get(
            gpio,
            _PWM_DEFAULT_FREQUENCY,
        )
    else:
        frequency = int(freq)
        analogWriteFrequency(
            gpio,
            frequency,
        )

    pwm = _pwms.get(gpio)

    if pwm is None:
        pwm = PWM(
            Pin(gpio),
            freq=frequency,
            duty_u16=0,
        )
        _pwms[gpio] = pwm
        _pin_modes[gpio] = OUTPUT
    else:
        try:
            pwm.freq(frequency)
        except Exception:
            pass

    duty = (
        value * _PWM_HARDWARE_MAX
    ) // input_max

    pwm.duty_u16(duty)
    return value


def analogWriteStop(gpio):
    """
    Desliga e libera o PWM de um GPIO.
    """

    _release_pwm(gpio)
    return True


# ============================================================
# TONS
# ============================================================

def tone(
    gpio,
    frequency,
    duration_ms=0,
    duty=None,
):
    """
    Gera um tom.

    Exemplo:
        tone(5, 440, 500)
    """

    frequency = int(frequency)

    if frequency <= 0:
        noTone(gpio)
        return False

    if duty is None:
        duty = (
            (1 << _analog_write_bits) - 1
        ) // 2

    analogWrite(
        gpio,
        duty,
        freq=frequency,
    )

    if int(duration_ms) > 0:
        delay(duration_ms)
        noTone(gpio)

    return True


def noTone(gpio):
    """Interrompe o tom e libera o PWM."""

    return analogWriteStop(gpio)


# ============================================================
# TOUCH
# ============================================================

def touchRead(gpio):
    """Lê um pino touch compatível."""

    if TouchPad is None:
        raise ImportError(
            "TouchPad nao esta disponivel neste firmware."
        )

    gpio = _normalize_gpio(gpio)
    touch = _touchpads.get(gpio)

    if touch is None:
        touch = TouchPad(Pin(gpio))
        _touchpads[gpio] = touch

    return touch.read()


# ============================================================
# INTERRUPÇÕES
# ============================================================

def _interrupt_trigger(mode):
    if mode == RISING:
        return Pin.IRQ_RISING

    if mode == FALLING:
        return Pin.IRQ_FALLING

    if mode == CHANGE:
        return (
            Pin.IRQ_RISING
            | Pin.IRQ_FALLING
        )

    raise ValueError(
        "Modo invalido. Use RISING, FALLING ou CHANGE."
    )


def attachInterrupt(
    gpio,
    callback,
    mode=CHANGE,
    pull=None,
    debounce_ms=0,
    pass_pin=False,
):
    """
    Liga uma interrupção a um GPIO.

    callback:
        função chamada quando o evento acontece.

    mode:
        RISING
        FALLING
        CHANGE

    pull:
        INPUT
        INPUT_PULLUP
        INPUT_PULLDOWN

    debounce_ms:
        filtro opcional para botões.

    Exemplo:
        def pressionou():
            print("Botao pressionado")

        attachInterrupt(
            3,
            pressionou,
            FALLING,
            pull=INPUT_PULLUP,
            debounce_ms=50
        )
    """

    if not callable(callback):
        raise TypeError(
            "O callback deve ser uma funcao."
        )

    gpio = _normalize_gpio(gpio)
    detachInterrupt(gpio)

    if pull is None:
        pull = INPUT

    if pull not in (
        INPUT,
        INPUT_PULLUP,
        INPUT_PULLDOWN,
    ):
        raise ValueError(
            "pull deve ser INPUT, INPUT_PULLUP "
            "ou INPUT_PULLDOWN."
        )

    pin = _create_pin(gpio, pull)
    _pins[gpio] = pin
    _pin_modes[gpio] = pull

    state = {
        "last_ms": -abs(
            int(debounce_ms)
        ),
    }
    debounce_ms = max(
        0,
        int(debounce_ms),
    )

    def handler(pin_object):
        now = ticks_ms()

        if debounce_ms > 0:
            elapsed = ticks_diff(
                now,
                state["last_ms"],
            )

            if elapsed < debounce_ms:
                return

        state["last_ms"] = now

        if pass_pin:
            callback(gpio)
        else:
            callback()

    trigger = _interrupt_trigger(mode)

    try:
        pin.irq(
            handler=handler,
            trigger=trigger,
            hard=False,
        )
    except TypeError:
        pin.irq(
            handler=handler,
            trigger=trigger,
        )

    _interrupts[gpio] = {
        "pin": pin,
        "handler": handler,
        "callback": callback,
        "mode": mode,
        "pull": pull,
        "debounce_ms": debounce_ms,
    }

    return True


def detachInterrupt(gpio):
    """Remove a interrupção de um GPIO."""

    gpio = _normalize_gpio(gpio)
    info = _interrupts.pop(
        gpio,
        None,
    )

    if info is not None:
        try:
            info["pin"].irq(
                handler=None
            )
        except Exception:
            pass

    return True


def interruptAttached(gpio):
    """Retorna True quando o GPIO possui interrupção."""

    return (
        _normalize_gpio(gpio)
        in _interrupts
    )


def noInterrupts():
    """
    Desativa temporariamente as interrupções globais.

    Retorna um estado que também pode ser passado para
    interrupts(estado).
    """

    if _disable_irq is None:
        return None

    state = _disable_irq()
    _irq_states.append(state)
    return state


def interrupts(state=None):
    """
    Restaura as interrupções desativadas por noInterrupts().
    """

    if _enable_irq is None:
        return False

    if state is None:
        if not _irq_states:
            return False

        state = _irq_states.pop()
    else:
        if _irq_states:
            _irq_states.pop()

    _enable_irq(state)
    return True


# ============================================================
# LEITURA DE PULSO
# ============================================================

def _manual_pulse_in(pin, state, timeout_us):
    start_timeout = ticks_us()

    # Aguarda o final de um pulso já existente.
    while pin.value() == state:
        if (
            ticks_diff(
                ticks_us(),
                start_timeout,
            )
            >= timeout_us
        ):
            return 0

    # Aguarda o início do próximo pulso.
    while pin.value() != state:
        if (
            ticks_diff(
                ticks_us(),
                start_timeout,
            )
            >= timeout_us
        ):
            return 0

    pulse_start = ticks_us()

    # Mede até o pulso terminar.
    while pin.value() == state:
        if (
            ticks_diff(
                ticks_us(),
                start_timeout,
            )
            >= timeout_us
        ):
            return 0

    return ticks_diff(
        ticks_us(),
        pulse_start,
    )


def pulseIn(
    gpio,
    state=HIGH,
    timeout_us=1000000,
):
    """
    Mede a duração de um pulso em microssegundos.

    Retorna 0 quando ocorre timeout.
    """

    gpio = _normalize_gpio(gpio)
    state = HIGH if state else LOW
    timeout_us = max(
        1,
        int(timeout_us),
    )

    pin = _digital_pin(
        gpio,
        INPUT,
    )

    if _machine_time_pulse_us is not None:
        try:
            result = _machine_time_pulse_us(
                pin,
                state,
                timeout_us,
            )

            return result if result > 0 else 0

        except OSError:
            return 0

    return _manual_pulse_in(
        pin,
        state,
        timeout_us,
    )


# ============================================================
# DESLOCAMENTO DE BITS
# ============================================================

def shiftOut(
    data_pin,
    clock_pin,
    bit_order,
    value,
):
    """
    Envia 8 bits por dois GPIOs.

    bit_order:
        LSBFIRST
        MSBFIRST
    """

    if bit_order not in (
        LSBFIRST,
        MSBFIRST,
    ):
        raise ValueError(
            "Use LSBFIRST ou MSBFIRST."
        )

    value = int(value) & 0xFF

    pinMode(data_pin, OUTPUT)
    pinMode(clock_pin, OUTPUT)

    for index in range(8):
        if bit_order == LSBFIRST:
            current_bit = (
                value >> index
            ) & 1
        else:
            current_bit = (
                value >> (7 - index)
            ) & 1

        digitalWrite(
            data_pin,
            current_bit,
        )
        digitalWrite(
            clock_pin,
            HIGH,
        )
        delayMicroseconds(1)
        digitalWrite(
            clock_pin,
            LOW,
        )

    return True


def shiftIn(
    data_pin,
    clock_pin,
    bit_order,
):
    """
    Recebe 8 bits por dois GPIOs.
    """

    if bit_order not in (
        LSBFIRST,
        MSBFIRST,
    ):
        raise ValueError(
            "Use LSBFIRST ou MSBFIRST."
        )

    pinMode(data_pin, INPUT)
    pinMode(clock_pin, OUTPUT)

    value = 0

    for index in range(8):
        digitalWrite(
            clock_pin,
            HIGH,
        )
        delayMicroseconds(1)

        current_bit = digitalRead(
            data_pin
        )

        digitalWrite(
            clock_pin,
            LOW,
        )

        if bit_order == LSBFIRST:
            value |= (
                current_bit << index
            )
        else:
            value |= (
                current_bit << (7 - index)
            )

    return value


# ============================================================
# TEMPO
# ============================================================

def delay(milliseconds):
    """
    Aguarda em milissegundos e mantém o sistema cooperativo.

    Durante a espera, os serviços internos são executados a
    cada 10 ms. Assim, motores continuam no último comando e
    sensores como a IMU não perdem a amostragem.
    """

    milliseconds = max(
        0,
        int(milliseconds),
    )
    start = ticks_ms()

    while True:
        elapsed = ticks_diff(
            ticks_ms(),
            start,
        )

        if elapsed >= milliseconds:
            break

        yieldNow()

        remaining = (
            milliseconds - elapsed
        )
        sleep_ms(
            10 if remaining > 10
            else remaining
        )


def delayMicroseconds(microseconds):
    sleep_us(
        max(
            0,
            int(microseconds),
        )
    )


def millis():
    return ticks_ms()


def micros():
    return ticks_us()


def elapsedMillis(start):
    """
    Retorna quantos milissegundos passaram desde start.
    """

    return ticks_diff(
        ticks_ms(),
        int(start),
    )


def elapsedMicros(start):
    """
    Retorna quantos microssegundos passaram desde start.
    """

    return ticks_diff(
        ticks_us(),
        int(start),
    )


# ============================================================
# MATEMÁTICA E CONVERSÃO
# ============================================================

def mapValue(
    value,
    from_low,
    from_high,
    to_low,
    to_high,
):
    """
    Converte uma faixa numérica em outra.
    """

    if from_high == from_low:
        return to_low

    return (
        (value - from_low)
        * (to_high - to_low)
        // (from_high - from_low)
        + to_low
    )


def map(
    value,
    from_low,
    from_high,
    to_low,
    to_high,
):
    """Nome Arduino para mapValue()."""

    return mapValue(
        value,
        from_low,
        from_high,
        to_low,
        to_high,
    )


def constrain(value, minimum, maximum):
    """Limita um valor entre mínimo e máximo."""

    if minimum > maximum:
        minimum, maximum = (
            maximum,
            minimum,
        )

    return max(
        minimum,
        min(
            maximum,
            value,
        ),
    )


# ============================================================
# OPERAÇÕES COM BITS
# ============================================================

def bit(position):
    return 1 << int(position)


def bitRead(value, position):
    return (
        int(value)
        >> int(position)
    ) & 1


def bitSet(value, position):
    return (
        int(value)
        | bit(position)
    )


def bitClear(value, position):
    return (
        int(value)
        & ~bit(position)
    )


def bitWrite(
    value,
    position,
    bit_value,
):
    if bit_value:
        return bitSet(
            value,
            position,
        )

    return bitClear(
        value,
        position,
    )


def lowByte(value):
    return int(value) & 0xFF


def highByte(value):
    return (
        int(value) >> 8
    ) & 0xFF


def makeWord(high, low=None):
    """
    Cria uma palavra de 16 bits.

    makeWord(valor)
    makeWord(byte_alto, byte_baixo)
    """

    if low is None:
        return int(high) & 0xFFFF

    return (
        (int(high) & 0xFF) << 8
    ) | (
        int(low) & 0xFF
    )


# ============================================================
# NÚMEROS ALEATÓRIOS
# ============================================================

def randomSeed(seed):
    if _random_module is None:
        return False

    try:
        _random_module.seed(
            int(seed)
        )
        return True
    except Exception:
        return False


def random(
    minimum_or_maximum,
    maximum=None,
):
    """
    random(maximo)
    random(minimo, maximo)

    O valor máximo não é incluído.
    """

    if maximum is None:
        minimum = 0
        maximum = int(
            minimum_or_maximum
        )
    else:
        minimum = int(
            minimum_or_maximum
        )
        maximum = int(maximum)

    if maximum <= minimum:
        return minimum

    if _random_module is not None:
        try:
            return _random_module.randrange(
                minimum,
                maximum,
            )
        except Exception:
            pass

    # Fallback simples usando micros().
    span = maximum - minimum

    return minimum + (
        abs(micros()) % span
    )


# ============================================================
# CONSOLE SERIAL SIMPLIFICADO
# ============================================================

class _SerialConsole:
    """
    Console USB/REPL sem necessidade de begin().
    """

    def __init__(self):
        self._rx_buffer = ""
        self._commands = []
        self._poll = None

        if sys is not None and _serial_select is not None:
            try:
                self._poll = _serial_select.poll()
                self._poll.register(sys.stdin, _serial_select.POLLIN)
            except Exception:
                self._poll = None

        # O delay() cooperativo continua esvaziando a USB para
        # evitar perda de caracteres durante movimentos longos.
        if self._update_rx not in _internal_yield_callbacks:
            _internal_yield_callbacks.append(self._update_rx)

    def _update_rx(self):
        if self._poll is None or sys is None:
            return

        try:
            while self._poll.poll(0):
                character = sys.stdin.read(1)
                if not character:
                    break
                self._rx_buffer += character
        except Exception:
            pass

    def available(self):
        self._update_rx()
        return len(self._rx_buffer)

    def readStringUntil(self, terminator="\n", timeout=0):
        """Lê texto até o terminador, como Serial.readStringUntil do Arduino."""
        terminator = str(terminator or "\n")
        timeout = max(0, int(timeout or 0))
        started = ticks_ms()

        while True:
            self._update_rx()
            position = self._rx_buffer.find(terminator)

            if position >= 0:
                value = self._rx_buffer[:position]
                self._rx_buffer = self._rx_buffer[position + len(terminator):]
                return value

            if timeout == 0 or ticks_diff(ticks_ms(), started) >= timeout:
                return ""

            yieldNow()
            sleep_ms(1)

    def _collect_commands(self):
        self._update_rx()
        start = 0

        for index, character in enumerate(self._rx_buffer):
            if character != "\n" and character != "\r":
                continue

            command = self._rx_buffer[start:index].strip()
            if command:
                self._commands.append(command)
                if len(self._commands) > 12:
                    self._commands.pop(0)
            start = index + 1

        if start:
            self._rx_buffer = self._rx_buffer[start:]

    def commandReceived(self, command):
        """Retorna True uma vez quando chega o comando terminado por CR/LF."""
        self._collect_commands()
        expected = str(command).strip()

        for index, received in enumerate(self._commands):
            if received == expected:
                self._commands.pop(index)
                return True

        return False

    def readCommand(self):
        """Retira da fila o próximo comando completo ou retorna None."""
        self._collect_commands()
        if self._commands:
            return self._commands.pop(0)
        return None

    def readCommandValue(self, separator=":"):
        """Lê comando:valor e retorna (comando, valor)."""
        received = self.readCommand()
        if received is None:
            return None

        separator = str(separator or ":")
        if separator not in received:
            return (received.strip(), None)

        command, raw_value = received.split(separator, 1)
        command = command.strip()
        raw_value = raw_value.strip()
        value = raw_value

        try:
            numeric = float(raw_value)
            value = int(numeric) if numeric == int(numeric) else numeric
        except (ValueError, TypeError):
            pass

        return (command, value)

    def print(
        self,
        *values,
        sep=" ",
        end="",
    ):
        print(
            *values,
            sep=sep,
            end=end,
        )

    def println(
        self,
        *values,
        sep=" ",
    ):
        print(
            *values,
            sep=sep,
        )

    def write(self, value):
        if sys is None:
            print(
                value,
                end="",
            )
            return

        sys.stdout.write(
            str(value)
        )

    def begin(self, baudrate=115200):
        """
        Compatibilidade Arduino.

        O console USB já está disponível, então nada precisa
        ser inicializado.
        """

        return int(baudrate)


Serial = _SerialConsole()
serial = Serial


# ============================================================
# EXECUÇÃO SETUP / LOOP
# ============================================================

def run(
    setup_function=None,
    loop_function=None,
):
    """
    Executa setup() uma vez e loop() continuamente.

    Formas de uso:

        run(setup, loop)

    Ou, quando setup e loop estão no main.py:

        run()
    """

    if (
        setup_function is None
        or loop_function is None
    ):
        try:
            import __main__

            if setup_function is None:
                setup_function = getattr(
                    __main__,
                    "setup",
                    None,
                )

            if loop_function is None:
                loop_function = getattr(
                    __main__,
                    "loop",
                    None,
                )

        except Exception:
            pass

    if loop_function is None:
        raise RuntimeError(
            "A funcao loop() nao foi definida."
        )

    try:
        if setup_function is not None:
            setup_function()

        while True:
            loop_function()
            yieldNow()

    except StopProgram:
        return True


# ============================================================
# LIMPEZA
# ============================================================

def releasePin(gpio):
    """
    Remove PWM, interrupção e caches associados ao GPIO.
    """

    gpio = _normalize_gpio(gpio)

    detachInterrupt(gpio)
    _release_pwm(gpio)

    adc = _adcs.pop(gpio, None)

    if adc is not None:
        try:
            adc.deinit()
        except Exception:
            pass

    _touchpads.pop(gpio, None)
    _pins.pop(gpio, None)
    _pin_modes.pop(gpio, None)
    _pwm_frequencies.pop(gpio, None)

    return True


def resetPins():
    """
    Libera os recursos criados por esta biblioteca.
    """

    gpios = set(_pins)
    gpios.update(_adcs)
    gpios.update(_pwms)
    gpios.update(_interrupts)

    for gpio in tuple(gpios):
        releasePin(gpio)

    return True


def info():
    """Retorna informações de diagnóstico da biblioteca."""

    return {
        "library_version": VERSION,
        "pins": tuple(_pins.keys()),
        "adc_pins": tuple(_adcs.keys()),
        "pwm_pins": tuple(_pwms.keys()),
        "interrupt_pins": tuple(
            _interrupts.keys()
        ),
        "analog_read_bits": (
            _analog_read_bits
        ),
        "analog_write_bits": (
            _analog_write_bits
        ),
        "external_adc": (
            _external_adc is not None
        ),
    }
