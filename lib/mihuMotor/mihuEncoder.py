"""
Leitura dos quatro encoders quadratura da MIHU-S3.

Os oito GPIOs são configurados com PULL_UP somente na primeira
leitura ou limpeza de encoder.
"""

from machine import Pin
import machine


try:
    from mihuPinMap import ENCODER_PINS
except ImportError:
    from lib.mihuPinMap import ENCODER_PINS


M1, M2, M3, M4 = 1, 2, 3, 4


_encoder_count = {
    M1: 0,
    M2: 0,
    M3: 0,
    M4: 0,
}

_encoder_last_state = {
    M1: 0,
    M2: 0,
    M3: 0,
    M4: 0,
}

_encoder_pins = {}
_encoder_handlers = {}
_encoder_inited = False
_encoder_last_error = None


# Índice:
#     estado_anterior << 2 | estado_atual
#
# O valor representa uma transição quadratura válida.
_TRANSITIONS = (
     0,  1, -1,  0,
    -1,  0,  0,  1,
     1,  0,  0, -1,
     0, -1,  1,  0,
)


def _norm_motor_id(motor_id):
    if isinstance(motor_id, str):
        text = motor_id.strip().upper()

        if (
            len(text) == 2
            and text[0] == "M"
            and text[1] in "1234"
        ):
            return int(text[1])

        raise ValueError(
            "Motor invalido: {}".format(
                motor_id
            )
        )

    motor_id = int(motor_id)

    if 1 <= motor_id <= 4:
        return motor_id

    raise ValueError(
        "Use M1, M2, M3, M4 ou 1..4."
    )


def _normalized_pin_map():
    result = {}

    for motor_id, pins in ENCODER_PINS.items():
        result[_norm_motor_id(motor_id)] = (
            int(pins[0]),
            int(pins[1]),
        )

    return result


def _read_state(pin_a, pin_b):
    return (
        (pin_a.value() << 1)
        | pin_b.value()
    )


def _make_irq_handler(motor_id):
    def _irq(_pin):
        pin_a, pin_b = _encoder_pins[
            motor_id
        ]

        current_state = _read_state(
            pin_a,
            pin_b,
        )

        last_state = _encoder_last_state[
            motor_id
        ]

        transition = (
            last_state << 2
        ) | current_state

        _encoder_count[motor_id] += (
            _TRANSITIONS[transition]
        )

        _encoder_last_state[
            motor_id
        ] = current_state

    return _irq


def initEncoder():
    global _encoder_inited
    global _encoder_last_error

    if _encoder_inited:
        return True

    try:
        pin_map = _normalized_pin_map()

        for motor_id in (
            M1,
            M2,
            M3,
            M4,
        ):
            if motor_id not in pin_map:
                raise ValueError(
                    "Encoder M{} ausente no mihuPinMap.".format(
                        motor_id
                    )
                )

            pin_a_number, pin_b_number = (
                pin_map[motor_id]
            )

            pin_a = Pin(
                pin_a_number,
                Pin.IN,
                Pin.PULL_UP,
            )

            pin_b = Pin(
                pin_b_number,
                Pin.IN,
                Pin.PULL_UP,
            )

            _encoder_pins[motor_id] = (
                pin_a,
                pin_b,
            )

            _encoder_last_state[
                motor_id
            ] = _read_state(
                pin_a,
                pin_b,
            )

        for motor_id in (
            M1,
            M2,
            M3,
            M4,
        ):
            pin_a, pin_b = _encoder_pins[
                motor_id
            ]

            handler = _make_irq_handler(
                motor_id
            )

            _encoder_handlers[
                motor_id
            ] = handler

            trigger = (
                Pin.IRQ_RISING
                | Pin.IRQ_FALLING
            )

            pin_a.irq(
                trigger=trigger,
                handler=handler,
            )

            pin_b.irq(
                trigger=trigger,
                handler=handler,
            )

        _encoder_inited = True
        _encoder_last_error = None
        return True

    except Exception as error:
        _encoder_last_error = error
        _encoder_inited = False
        return False


def _ensure_encoder():
    if _encoder_inited:
        return True

    if not initEncoder():
        raise OSError(
            "Encoders indisponiveis: {}".format(
                _encoder_last_error
            )
        )

    return True


def getEncoder(motor_id):
    motor_id = _norm_motor_id(
        motor_id
    )

    _ensure_encoder()

    irq_state = machine.disable_irq()

    try:
        return int(
            _encoder_count[motor_id]
        )

    finally:
        machine.enable_irq(
            irq_state
        )


def setEncoder(motor_id, value):
    motor_id = _norm_motor_id(
        motor_id
    )

    _ensure_encoder()

    irq_state = machine.disable_irq()

    try:
        _encoder_count[motor_id] = int(
            value
        )

    finally:
        machine.enable_irq(
            irq_state
        )

    return int(value)


def clearEncoder(motor_id):
    return setEncoder(
        motor_id,
        0,
    )


def getAllEncoders():
    _ensure_encoder()

    irq_state = machine.disable_irq()

    try:
        return (
            int(_encoder_count[M1]),
            int(_encoder_count[M2]),
            int(_encoder_count[M3]),
            int(_encoder_count[M4]),
        )

    finally:
        machine.enable_irq(
            irq_state
        )


def clearAllEncoders():
    _ensure_encoder()

    irq_state = machine.disable_irq()

    try:
        for motor_id in (
            M1,
            M2,
            M3,
            M4,
        ):
            _encoder_count[motor_id] = 0

    finally:
        machine.enable_irq(
            irq_state
        )

    return True


def encoderAvailable():
    return initEncoder()


def encoderInfo(motor_id=None):
    if motor_id is None:
        counts = getAllEncoders()

        return {
            "available": _encoder_inited,
            "counts": counts,
            "pull": "PULL_UP",
            "last_error": _encoder_last_error,
        }

    motor_id = _norm_motor_id(
        motor_id
    )

    _ensure_encoder()

    pin_a, pin_b = _normalized_pin_map()[
        motor_id
    ]

    return {
        "available": _encoder_inited,
        "motor": motor_id,
        "count": getEncoder(motor_id),
        "pin_a": pin_a,
        "pin_b": pin_b,
        "pull": "PULL_UP",
        "last_error": _encoder_last_error,
    }


def endEncoder():
    global _encoder_inited

    for pin_a, pin_b in _encoder_pins.values():
        try:
            pin_a.irq(
                handler=None
            )
        except Exception:
            pass

        try:
            pin_b.irq(
                handler=None
            )
        except Exception:
            pass

    _encoder_pins.clear()
    _encoder_handlers.clear()
    _encoder_inited = False
    return True
