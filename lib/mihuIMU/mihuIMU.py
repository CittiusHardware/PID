"""
mihuIMU.py

Biblioteca educacional para IMUs da família ST LSM6DS.

Objeto global:
    imu

Uso simples:
    from mihuIMU import imu

    imu.calibration()

    while True:
        print(imu.angle())

Modelos reconhecidos pelo WHO_AM_I:
    0x6C -> LSM6DSOX / LSM6DSO
    0x6A -> LSM6DSL / LSM6DSM
    0x69 -> LSM6DS3 / LSM6DS3TR-C

Configuração padrão:
    I2C: 0
    SDA: GPIO 39
    SCL: GPIO 40
    Endereço: detecta 0x6A ou 0x6B
    Acelerômetro: +-2 g, 104 Hz
    Giroscópio: +-250 dps, 104 Hz

A importação não inicializa I2C nem o sensor.
"""

import math
import time


VERSION = "1.4.0"


class MihuIMU:
    # --------------------------------------------------------
    # Registradores comuns da família LSM6DS
    # --------------------------------------------------------

    REG_WHO_AM_I = 0x0F
    REG_CTRL1_XL = 0x10
    REG_CTRL2_G = 0x11
    REG_CTRL3_C = 0x12
    REG_STATUS = 0x1E

    REG_OUT_TEMP_L = 0x20
    REG_OUTX_L_G = 0x22
    REG_OUTX_L_XL = 0x28

    # Configuração comum:
    # ODR = 104 Hz
    # XL  = +-2 g
    # G   = +-250 dps
    CTRL1_XL_104HZ_2G = 0x40
    CTRL2_G_104HZ_250DPS = 0x40

    # CTRL3_C:
    # BDU = 1
    # IF_INC = 1
    CTRL3_C_BDU_IF_INC = 0x44

    # Sensibilidades para as escalas configuradas.
    ACCEL_G_PER_LSB = 0.000061
    GYRO_DPS_PER_LSB = 0.00875

    _MODELS = {
        0x6C: "LSM6DSOX/LSM6DSO",
        0x6A: "LSM6DSL/LSM6DSM",
        0x69: "LSM6DS3/LSM6DS3TR-C",
    }

    def __init__(
        self,
        i2c=None,
        i2c_id=0,
        sda=39,
        scl=40,
        freq=400000,
        address=None,
        default_axis="z",
        invert=False,
        deadband=0.8,
    ):
        self._external_i2c = i2c
        self._i2c = None

        self._i2c_id = int(i2c_id)
        self._sda = int(sda)
        self._scl = int(scl)
        self._freq = int(freq)

        self._requested_address = address
        self._address = None
        self._who = None
        self._model = None

        self._started = False
        self._calibrated = False
        self._last_error = None

        self._default_axis = self._normalize_axis(
            default_axis
        )
        self._axis_sign = -1.0 if invert else 1.0
        self._deadband = abs(float(deadband))

        self._gyro_bias = [
            0.0,
            0.0,
            0.0,
        ]

        self._gyro = [
            0.0,
            0.0,
            0.0,
        ]

        self._accel = [
            0.0,
            0.0,
            0.0,
        ]

        self._angles = [
            0.0,
            0.0,
            0.0,
        ]

        self._tilt_x = 0.0
        self._tilt_y = 0.0

        self._last_update_us = None

    # ========================================================
    # UTILITÁRIOS
    # ========================================================

    def _normalize_axis(self, axis):
        axis = str(axis).lower()

        if axis not in ("x", "y", "z"):
            raise ValueError(
                "O eixo deve ser 'x', 'y' ou 'z'."
            )

        return axis

    def _axis_index(self, axis=None):
        if axis is None:
            axis = self._default_axis

        axis = self._normalize_axis(axis)

        if axis == "x":
            return 0

        if axis == "y":
            return 1

        return 2

    def _angle_axis(self, axis=None):
        """Mapeia os eixos físicos para a orientação da MIHU-S3."""

        use_default = axis is None

        if use_default:
            axis = self._default_axis

        axis = self._normalize_axis(axis)

        if axis == "x":
            index = 1
            sign = 1.0
        elif axis == "y":
            index = 0
            sign = 1.0
        else:
            index = 2
            sign = -1.0

        if use_default:
            sign *= self._axis_sign

        return index, sign

    def _logical_vector(self, values):
        """Converte um vetor físico para os eixos da MIHU-S3."""

        return (
            values[1],
            values[0],
            -values[2],
        )

    def _int16(self, low, high):
        value = int(low) | (int(high) << 8)

        if value & 0x8000:
            value -= 65536

        return value

    def _read(self, register, length=1):
        return self._i2c.readfrom_mem(
            self._address,
            register,
            length,
        )

    def _write(self, register, value):
        self._i2c.writeto_mem(
            self._address,
            register,
            bytes((int(value) & 0xFF,)),
        )

    def _make_i2c(self):
        if self._external_i2c is not None:
            self._i2c = self._external_i2c
            return

        from machine import Pin, I2C

        self._i2c = I2C(
            self._i2c_id,
            sda=Pin(self._sda),
            scl=Pin(self._scl),
            freq=self._freq,
        )

    def _candidate_addresses(self):
        if self._requested_address is not None:
            return (int(self._requested_address),)

        return (0x6A, 0x6B)

    def _detect(self):
        found_unknown = None

        for address in self._candidate_addresses():
            try:
                who = self._i2c.readfrom_mem(
                    address,
                    self.REG_WHO_AM_I,
                    1,
                )[0]

            except Exception:
                continue

            if who in self._MODELS:
                self._address = address
                self._who = who
                self._model = self._MODELS[who]
                return True

            found_unknown = (
                address,
                who,
            )

        if found_unknown is not None:
            address, who = found_unknown

            raise OSError(
                "IMU desconhecida em {}: WHO_AM_I={}".format(
                    hex(address),
                    hex(who),
                )
            )

        raise OSError(
            "Nenhuma IMU LSM6DS encontrada em 0x6A ou 0x6B."
        )

    def _soft_reset(self):
        self._write(
            self.REG_CTRL3_C,
            0x01,
        )

        start = time.ticks_ms()

        while True:
            value = self._read(
                self.REG_CTRL3_C,
                1,
            )[0]

            if (value & 0x01) == 0:
                return True

            if time.ticks_diff(
                time.ticks_ms(),
                start,
            ) > 200:
                raise OSError(
                    "Timeout no reset da IMU."
                )

            time.sleep_ms(2)

    def _ensure_started(self, calibrate=False):
        if self._started:
            return True

        return self.begin(
            calibrate=calibrate
        )

    # ========================================================
    # INICIALIZAÇÃO
    # ========================================================

    def begin(
        self,
        calibrate=False,
        calibration_samples=120,
    ):
        """
        Inicializa e identifica a IMU.

        Retorna:
            True  -> sensor iniciado
            False -> falha

        A calibração é opcional para manter a primeira chamada
        mais rápida. `reset()` calibra automaticamente quando
        necessário.
        """

        if self._started:
            if calibrate and not self._calibrated:
                return self.calibrate(
                    calibration_samples
                )

            return True

        self._last_error = None

        try:
            self._make_i2c()
            self._detect()
            self._soft_reset()

            self._write(
                self.REG_CTRL3_C,
                self.CTRL3_C_BDU_IF_INC,
            )

            self._write(
                self.REG_CTRL1_XL,
                self.CTRL1_XL_104HZ_2G,
            )

            self._write(
                self.REG_CTRL2_G,
                self.CTRL2_G_104HZ_250DPS,
            )

            time.sleep_ms(30)

            self._started = True
            self._last_update_us = time.ticks_us()

            self.update()

            if calibrate:
                return self.calibrate(
                    calibration_samples
                )

            return True

        except Exception as error:
            self._last_error = error
            self._started = False
            return False

    def end(self):
        """
        Coloca acelerômetro e giroscópio em power-down.
        """

        if self._started:
            try:
                self._write(
                    self.REG_CTRL1_XL,
                    0x00,
                )
                self._write(
                    self.REG_CTRL2_G,
                    0x00,
                )
            except Exception as error:
                self._last_error = error

        self._started = False
        self._last_update_us = None
        return True

    deinit = end

    # ========================================================
    # CONFIGURAÇÃO PARA O ALUNO
    # ========================================================

    def setAxis(
        self,
        axis="z",
        invert=False,
    ):
        """
        Define o eixo usado por angle() e speed().

        Exemplo:
            imu.setAxis("z")
            imu.setAxis("z", invert=True)
        """

        self._default_axis = self._normalize_axis(
            axis
        )
        self._axis_sign = (
            -1.0
            if invert
            else 1.0
        )

        return self._default_axis

    def deadband(self, value=None):
        """
        Consulta ou altera a zona morta do giroscópio em dps.
        """

        if value is None:
            return self._deadband

        self._deadband = abs(float(value))
        return self._deadband

    def set(
        self,
        axis=None,
        invert=None,
        deadband=None,
    ):
        """
        Configura a leitura principal da IMU.

        Exemplos:
            imu.set(axis="z")
            imu.set(axis="x", invert=True)
            imu.set(deadband=1.0)

        Nenhuma inicialização manual é necessária.
        """

        if axis is not None:
            self._default_axis = self._normalize_axis(
                axis
            )

        if invert is not None:
            self._axis_sign = (
                -1.0
                if bool(invert)
                else 1.0
            )

        if deadband is not None:
            self._deadband = abs(
                float(deadband)
            )

        return {
            "axis": self._default_axis,
            "invert": self._axis_sign < 0,
            "deadband": self._deadband,
        }

    # ========================================================
    # LEITURA E INTEGRAÇÃO
    # ========================================================

    def update(self):
        """
        Atualiza aceleração, giroscópio, inclinação e ângulos.

        Deve ser chamada frequentemente. As funções angle(),
        speed(), gyro(), accel() e get() chamam update()
        automaticamente.
        """

        if not self._ensure_started(
            calibrate=False
        ):
            return False

        try:
            now = time.ticks_us()

            if self._last_update_us is None:
                dt = 0.0
            else:
                dt_us = time.ticks_diff(
                    now,
                    self._last_update_us,
                )

                dt = dt_us / 1000000.0

                # Evita saltos após pausas longas.
                if dt < 0.0 or dt > 0.1:
                    dt = 0.0

            self._last_update_us = now

            data = self._read(
                self.REG_OUTX_L_G,
                12,
            )

            raw_gx = self._int16(
                data[0],
                data[1],
            )
            raw_gy = self._int16(
                data[2],
                data[3],
            )
            raw_gz = self._int16(
                data[4],
                data[5],
            )

            raw_ax = self._int16(
                data[6],
                data[7],
            )
            raw_ay = self._int16(
                data[8],
                data[9],
            )
            raw_az = self._int16(
                data[10],
                data[11],
            )

            gyro_values = (
                raw_gx * self.GYRO_DPS_PER_LSB,
                raw_gy * self.GYRO_DPS_PER_LSB,
                raw_gz * self.GYRO_DPS_PER_LSB,
            )

            accel_values = (
                raw_ax * self.ACCEL_G_PER_LSB,
                raw_ay * self.ACCEL_G_PER_LSB,
                raw_az * self.ACCEL_G_PER_LSB,
            )

            for index in range(3):
                value = (
                    gyro_values[index]
                    - self._gyro_bias[index]
                )

                if abs(value) < self._deadband:
                    value = 0.0

                self._gyro[index] = value
                self._accel[index] = (
                    accel_values[index]
                )

                if dt > 0.0:
                    self._angles[index] += (
                        value * dt
                    )

            ax, ay, az = self._accel

            self._tilt_x = math.atan2(
                ay,
                math.sqrt(
                    ax * ax + az * az
                ),
            ) * 180.0 / math.pi

            self._tilt_y = math.atan2(
                -ax,
                math.sqrt(
                    ay * ay + az * az
                ),
            ) * 180.0 / math.pi

            self._last_error = None
            return True

        except Exception as error:
            self._last_error = error
            return False

    def wait_ms(self, duration_ms, sample_ms=10):
        """
        Aguarda sem interromper as leituras da IMU.

        Use esta função no lugar de sleep() quando o ângulo
        precisa continuar sendo acompanhado durante a espera.

        Exemplos:
            imu.wait_ms(1000)
            imu.wait_ms(5000, sample_ms=10)
        """

        duration_ms = max(0, int(duration_ms))
        sample_ms = max(1, int(sample_ms))
        start = time.ticks_ms()

        while time.ticks_diff(time.ticks_ms(), start) < duration_ms:
            self.update()

            remaining = duration_ms - time.ticks_diff(
                time.ticks_ms(),
                start,
            )

            if remaining > 0:
                time.sleep_ms(min(sample_ms, remaining))

        return True

    # ========================================================
    # CALIBRAÇÃO
    # ========================================================

    def calibrate(
        self,
        samples=120,
        interval_ms=5,
    ):
        """
        Mede o desvio do giroscópio.

        Mantenha o robô completamente parado durante a
        calibração.
        """

        if not self._ensure_started(
            calibrate=False
        ):
            return False

        samples = max(
            20,
            int(samples),
        )
        interval_ms = max(
            1,
            int(interval_ms),
        )

        sums = [
            0.0,
            0.0,
            0.0,
        ]

        try:
            # Descarta as primeiras amostras.
            for _ in range(10):
                self._read(
                    self.REG_OUTX_L_G,
                    6,
                )
                time.sleep_ms(interval_ms)

            for _ in range(samples):
                data = self._read(
                    self.REG_OUTX_L_G,
                    6,
                )

                sums[0] += (
                    self._int16(
                        data[0],
                        data[1],
                    )
                    * self.GYRO_DPS_PER_LSB
                )

                sums[1] += (
                    self._int16(
                        data[2],
                        data[3],
                    )
                    * self.GYRO_DPS_PER_LSB
                )

                sums[2] += (
                    self._int16(
                        data[4],
                        data[5],
                    )
                    * self.GYRO_DPS_PER_LSB
                )

                time.sleep_ms(interval_ms)

            for index in range(3):
                self._gyro_bias[index] = (
                    sums[index] / samples
                )

            self._calibrated = True
            self._last_update_us = time.ticks_us()
            self._last_error = None
            return True

        except Exception as error:
            self._last_error = error
            self._calibrated = False
            return False

    def reset(
        self,
        axis=None,
        calibrate=True,
    ):
        """
        Zera o ângulo relativo.

        Na primeira chamada, calibra automaticamente o
        giroscópio. Mantenha o robô parado.

        Exemplos:
            imu.reset()
            imu.reset("z")
        """

        if not self._ensure_started(
            calibrate=False
        ):
            return False

        if calibrate and not self._calibrated:
            if not self.calibrate():
                return False

        if axis is None:
            self._angles = [
                0.0,
                0.0,
                0.0,
            ]
        else:
            index, unused_sign = self._angle_axis(axis)
            del unused_sign
            self._angles[index] = 0.0

        self._last_update_us = time.ticks_us()
        return True

    def calibration(
        self,
        axis=None,
        calibrate=True,
    ):
        """
        Zera o ângulo relativo.

        Na primeira chamada, calibra o giroscópio por padrão.
        Mantenha a IMU parada durante a calibração.

        Exemplos:
            imu.calibration()
            imu.calibration("z")
            imu.calibration(calibrate=False)
        """

        return self.reset(
            axis=axis,
            calibrate=calibrate,
        )

    # ========================================================
    # FUNÇÕES SIMPLES PARA O ALUNO
    # ========================================================

    def angle(self, axis=None):
        """
        Retorna o ângulo relativo integrado, em graus.

        Na orientação da MIHU-S3, X usa o eixo físico Y,
        Y usa o eixo físico X e Z tem o sinal invertido.

        Sem parâmetro, usa o eixo definido por setAxis().
        O padrão é Z.
        """

        if not self.update():
            return 0.0

        index, sign = self._angle_axis(axis)
        value = self._angles[index] * sign

        return round(value, 2)

    def speed(self, axis=None):
        """
        Retorna a velocidade angular em graus por segundo.

        Usa o mesmo sentido lógico de angle().
        """

        if not self.update():
            return 0.0

        index = self._axis_index(axis)
        value = self._logical_vector(self._gyro)[index]

        if axis is None:
            value *= self._axis_sign

        return round(value, 2)

    def gyro(self):
        """
        Retorna (gx, gy, gz) em graus por segundo.

        Os eixos seguem a orientação lógica da MIHU-S3.
        """

        if not self.update():
            return (
                0.0,
                0.0,
                0.0,
            )

        return tuple(
            round(value, 2)
            for value in self._logical_vector(self._gyro)
        )

    def accel(self):
        """
        Retorna (ax, ay, az) em g.

        Os eixos seguem a mesma orientação de angle().
        """

        if not self.update():
            return (
                0.0,
                0.0,
                0.0,
            )

        return tuple(
            round(value, 3)
            for value in self._logical_vector(self._accel)
        )

    acceleration = accel

    def x(self):
        return self.speed("x")

    def y(self):
        return self.speed("y")

    def z(self):
        return self.speed("z")

    def angleX(self):
        return self.angle("x")

    def angleY(self):
        return self.angle("y")

    def angleZ(self):
        return self.angle("z")

    def _student_tilts(self):
        """
        Converte os eixos internos para a orientação física
        utilizada pelo aluno na MIHU-S3.

        X do aluno = inclinação interna Y
        Y do aluno = inclinação interna X
        """

        return self.roll(), self.pitch()

    def roll(self):
        """Retorna a inclinação ao redor do eixo X lógico."""

        if not self.update():
            return 0.0

        unused_ax, ay, az = self._logical_vector(self._accel)
        del unused_ax

        value = math.atan2(ay, -az) * 180.0 / math.pi
        return round(value, 2)

    def pitch(self):
        """Retorna a inclinação ao redor do eixo Y lógico."""

        if not self.update():
            return 0.0

        ax, ay, az = self._logical_vector(self._accel)
        value = math.atan2(
            -ax,
            math.sqrt(ay * ay + az * az),
        ) * 180.0 / math.pi

        return round(value, 2)

    def tiltX(self):
        """
        Inclinação no eixo X da MIHU-S3.
        """

        if not self.update():
            return 0.0

        return self.roll()

    def tiltY(self):
        """
        Inclinação no eixo Y da MIHU-S3.
        """

        if not self.update():
            return 0.0

        return self.pitch()

    def direction(self, threshold=10.0):
        """
        Retorna:
            "DIREITA"
            "ESQUERDA"
            "PARADO"
        """

        value = self.speed()
        threshold = abs(float(threshold))

        if value > threshold:
            return "DIREITA"

        if value < -threshold:
            return "ESQUERDA"

        return "PARADO"

    def read(self):
        """
        Faz uma única atualização e retorna os dados principais.

        Retorno:
            {
                "angle": ...,
                "speed": ...,
                "gyro": (...),
                "accel": (...),
                "tilt_x": ...,
                "tilt_y": ...
            }
        """

        return self.get()

    def get(self):
        """
        Retorna todas as informações principais com uma única
        leitura do sensor.
        """

        if not self.update():
            return {
                "angle": 0.0,
                "speed": 0.0,
                "gyro": (0.0, 0.0, 0.0),
                "accel": (0.0, 0.0, 0.0),
                "tilt_x": 0.0,
                "tilt_y": 0.0,
                "roll": 0.0,
                "pitch": 0.0,
            }

        index, angle_sign = self._angle_axis()
        angle_value = (
            self._angles[index]
            * angle_sign
        )
        logical_gyro = self._logical_vector(self._gyro)
        logical_accel = self._logical_vector(self._accel)
        speed_index = self._axis_index()
        speed_value = logical_gyro[speed_index] * self._axis_sign

        unused_ax, roll_ay, roll_az = logical_accel
        del unused_ax
        roll_value = math.atan2(roll_ay, -roll_az) * 180.0 / math.pi
        pitch_ax, pitch_ay, pitch_az = logical_accel
        pitch_value = math.atan2(
            -pitch_ax,
            math.sqrt(pitch_ay * pitch_ay + pitch_az * pitch_az),
        ) * 180.0 / math.pi

        return {
            "angle": round(angle_value, 2),
            "speed": round(speed_value, 2),
            "gyro": tuple(
                round(value, 2)
                for value in logical_gyro
            ),
            "accel": tuple(
                round(value, 3)
                for value in logical_accel
            ),
            "tilt_x": round(
                roll_value,
                2,
            ),
            "tilt_y": round(
                pitch_value,
                2,
            ),
            "roll": round(roll_value, 2),
            "pitch": round(pitch_value, 2),
        }

    def orientation(self):
        """
        Retorna apenas as inclinações X e Y em uma leitura.

        Exemplo:
            x, y = imu.orientation()
        """

        data = self.read()

        return (
            data["tilt_x"],
            data["tilt_y"],
        )

    def rotation(self):
        """
        Retorna ângulo e velocidade do eixo principal.

        Exemplo:
            angle, speed = imu.rotation()
        """

        data = self.read()

        return (
            data["angle"],
            data["speed"],
        )

    # ========================================================
    # DIAGNÓSTICO
    # ========================================================

    def available(self):
        return self._ensure_started(
            calibrate=False
        )

    def whoAmI(self):
        if not self._ensure_started(
            calibrate=False
        ):
            return None

        return self._who

    def model(self):
        if not self._ensure_started(
            calibrate=False
        ):
            return None

        return self._model

    def address(self):
        if not self._ensure_started(
            calibrate=False
        ):
            return None

        return self._address

    def lastError(self):
        return self._last_error

    def info(self):
        self._ensure_started(
            calibrate=False
        )

        return {
            "library_version": VERSION,
            "available": self._started,
            "model": self._model,
            "who_am_i": self._who,
            "address": self._address,
            "i2c_id": self._i2c_id,
            "sda": self._sda,
            "scl": self._scl,
            "frequency": self._freq,
            "default_axis": self._default_axis,
            "tilt_axis_mapping": "x<-internal_y,y<-internal_x",
            "inverted": self._axis_sign < 0,
            "deadband": self._deadband,
            "calibrated": self._calibrated,
            "gyro_bias": tuple(
                round(value, 4)
                for value in self._gyro_bias
            ),
            "last_error": self._last_error,
        }


# Objeto global usado pelo aluno.
imu = MihuIMU()
