"""
Driver educacional do PCA9685 com inicialização sob demanda.

A importação não cria I2C nem acessa o PCA9685.
"""

import ustruct
import time
from machine import I2C, Pin


VERSION = "1.0.0"


class PCA9685:
    CHANNEL_MIN = 0
    CHANNEL_MAX = 15
    PWM_MIN = 0
    PWM_MAX = 4095

    def __init__(
        self,
        i2c=None,
        address=0x40,
        freq=50,
        i2c_id=0,
        sda=39,
        scl=40,
        bus_freq=400000,
    ):
        self._external_i2c = i2c
        self.i2c = None

        self.address = int(address)
        self._frequency = int(freq)

        self._i2c_id = int(i2c_id)
        self._sda = int(sda)
        self._scl = int(scl)
        self._bus_freq = int(bus_freq)

        self._started = False
        self._last_error = None

    # ========================================================
    # INICIALIZAÇÃO SOB DEMANDA
    # ========================================================

    def _make_i2c(self):
        if self._external_i2c is not None:
            self.i2c = self._external_i2c
            return

        self.i2c = I2C(
            self._i2c_id,
            sda=Pin(self._sda),
            scl=Pin(self._scl),
            freq=self._bus_freq,
        )

    def _write_direct(self, register, value):
        self.i2c.writeto_mem(
            self.address,
            int(register),
            bytes((int(value) & 0xFF,)),
        )

    def _read_direct(self, register):
        return self.i2c.readfrom_mem(
            self.address,
            int(register),
            1,
        )[0]

    def _set_frequency_direct(self, value):
        value = int(value)

        if value < 24 or value > 1526:
            raise ValueError(
                "Frequencia PCA fora do intervalo suportado."
            )

        prescale = int(
            25000000.0
            / 4096.0
            / value
            - 1.0
            + 0.5
        )

        prescale = self._clamp(
            prescale,
            3,
            255,
        )

        old_mode = self._read_direct(0x00)
        sleep_mode = (old_mode & 0x7F) | 0x10

        self._write_direct(
            0x00,
            sleep_mode,
        )
        self._write_direct(
            0xFE,
            prescale,
        )
        self._write_direct(
            0x00,
            old_mode,
        )

        time.sleep_us(500)

        self._write_direct(
            0x00,
            old_mode | 0xA1,
        )

        self._frequency = value
        return value

    def _start(self):
        if self._started:
            return True

        try:
            self._make_i2c()

            # Reinicia o modo do chip e aplica a frequência
            # configurada, somente na primeira utilização.
            self._write_direct(
                0x00,
                0x00,
            )

            self._set_frequency_direct(
                self._frequency
            )

            self._started = True
            self._last_error = None
            return True

        except Exception as error:
            self._started = False
            self._last_error = error
            return False

    def _ensure_started(self):
        if self._started:
            return True

        if not self._start():
            raise OSError(
                "PCA9685 indisponivel: {}".format(
                    self._last_error
                )
            )

        return True

    # ========================================================
    # HELPERS
    # ========================================================

    @staticmethod
    def _clamp(value, minimum, maximum):
        if value < minimum:
            return minimum

        if value > maximum:
            return maximum

        return value

    def _channel(self, channel):
        channel = int(channel)

        if (
            channel < self.CHANNEL_MIN
            or channel > self.CHANNEL_MAX
        ):
            raise ValueError(
                "Canal PCA deve estar entre 0 e 15."
            )

        return channel

    def _write(self, register, value):
        self._ensure_started()
        self._write_direct(
            register,
            value,
        )

    def _read(self, register):
        self._ensure_started()
        return self._read_direct(register)

    # ========================================================
    # CONTROLE DO PCA
    # ========================================================

    def reset(self):
        self._ensure_started()
        self._write_direct(
            0x00,
            0x00,
        )
        self._set_frequency_direct(
            self._frequency
        )
        return True

    def freq(self, value=None):
        if value is None:
            # Consultar a configuração não inicia o hardware.
            if not self._started:
                return self._frequency

            try:
                prescale = self._read_direct(
                    0xFE
                )

                return int(
                    25000000.0
                    / 4096
                    / (prescale + 1)
                )

            except Exception:
                return self._frequency

        self._ensure_started()
        return self._set_frequency_direct(
            value
        )

    frequency = freq

    # ========================================================
    # PWM
    # ========================================================

    def _write_pwm_raw(
        self,
        channel,
        on,
        off,
    ):
        self._ensure_started()

        channel = self._channel(channel)
        on = int(on)
        off = int(off)

        if not 0 <= on <= 4096:
            raise ValueError(
                "PWM ON deve estar entre 0 e 4096."
            )

        if not 0 <= off <= 4096:
            raise ValueError(
                "PWM OFF deve estar entre 0 e 4096."
            )

        data = ustruct.pack(
            "<HH",
            on,
            off,
        )

        self.i2c.writeto_mem(
            self.address,
            0x06 + 4 * channel,
            data,
        )

    def pwm(
        self,
        channel,
        value=None,
        off=None,
    ):
        channel = self._channel(channel)

        if value is None and off is None:
            self._ensure_started()

            data = self.i2c.readfrom_mem(
                self.address,
                0x06 + 4 * channel,
                4,
            )

            return ustruct.unpack(
                "<HH",
                data,
            )

        if off is not None:
            self._write_pwm_raw(
                channel,
                value,
                off,
            )

            return int(value), int(off)

        value = int(value)

        if value < 0 or value > self.PWM_MAX:
            raise ValueError(
                "PWM deve estar entre 0 e 4095."
            )

        self.duty_raw(
            channel,
            value,
        )

        return value

    def duty_raw(
        self,
        channel,
        value=None,
        invert=False,
    ):
        channel = self._channel(channel)

        if value is None:
            on, off = self.pwm(channel)

            if on == 4096:
                return 4095

            if off == 4096:
                return 0

            return int(off)

        value = int(value)

        if value < 0 or value > self.PWM_MAX:
            raise ValueError(
                "Duty bruto deve estar entre 0 e 4095."
            )

        if invert:
            value = self.PWM_MAX - value

        if value == 0:
            self._write_pwm_raw(
                channel,
                0,
                4096,
            )

        elif value == self.PWM_MAX:
            self._write_pwm_raw(
                channel,
                4096,
                0,
            )

        else:
            self._write_pwm_raw(
                channel,
                0,
                value,
            )

        return value

    raw_duty = duty_raw

    def duty(self, channel, value=None):
        channel = self._channel(channel)

        if value is None:
            raw = self.duty_raw(channel)

            return int(
                (raw * 100 + 2047)
                // 4095
            )

        value = float(value)
        value = self._clamp(
            value,
            0.0,
            100.0,
        )

        raw = int(
            value
            * self.PWM_MAX
            / 100.0
        )

        self.duty_raw(
            channel,
            raw,
        )

        if value == int(value):
            return int(value)

        return value

    percent = duty

    def on(self, channel):
        self.duty_raw(
            channel,
            self.PWM_MAX,
        )
        return True

    def off(self, channel):
        self.duty_raw(
            channel,
            0,
        )
        return True

    high = on
    low = off

    def toggle(self, channel):
        if self.duty(channel) > 0:
            self.off(channel)
            return False

        self.on(channel)
        return True

    def all_off(self):
        for channel in range(16):
            self.off(channel)

        return True

    # ========================================================
    # SERVO
    # ========================================================

    def servo_us(self, channel, usec):
        channel = self._channel(channel)
        usec = float(usec)

        frequency = self.freq()
        period_us = 1000000.0 / frequency

        raw = int(
            usec
            / period_us
            * 4096.0
        )

        raw = self._clamp(
            raw,
            0,
            self.PWM_MAX,
        )

        self.duty_raw(
            channel,
            raw,
        )

        return int(usec)

    def servo_angle(
        self,
        channel,
        angle,
        min_us=500,
        max_us=2500,
        min_angle=0,
        max_angle=180,
    ):
        angle = float(angle)
        min_angle = float(min_angle)
        max_angle = float(max_angle)

        if max_angle <= min_angle:
            raise ValueError(
                "max_angle deve ser maior que min_angle."
            )

        if max_us <= min_us:
            raise ValueError(
                "max_us deve ser maior que min_us."
            )

        angle = self._clamp(
            angle,
            min_angle,
            max_angle,
        )

        ratio = (
            angle - min_angle
        ) / (
            max_angle - min_angle
        )

        usec = min_us + ratio * (
            max_us - min_us
        )

        self.servo_us(
            channel,
            usec,
        )

        return angle

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    def available(self):
        return self._start()

    def lastError(self):
        return self._last_error

    def info(self):
        return {
            "library_version": VERSION,
            "started": self._started,
            "available": (
                self._started
                or self.available()
            ),
            "address": self.address,
            "frequency": self._frequency,
            "i2c_id": self._i2c_id,
            "sda": self._sda,
            "scl": self._scl,
            "bus_frequency": self._bus_freq,
            "last_error": self._last_error,
        }

    def end(self):
        if self._started:
            try:
                self.all_off()
            except Exception:
                pass

        if (
            self._external_i2c is None
            and self.i2c is not None
        ):
            try:
                self.i2c.deinit()
            except Exception:
                pass

        self.i2c = None
        self._started = False
        return True

    deinit = end


# Objeto global sem inicialização do I2C.
pca = PCA9685(
    address=0x40,
    freq=50,
    i2c_id=0,
    sda=39,
    scl=40,
    bus_freq=400000,
)
