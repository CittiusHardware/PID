# ============================================================
# lib/mihuVL53L0/mihuVL53L0.py
# Driver MicroPython para VL53L0X
# ============================================================

from machine import I2C, SoftI2C, Pin
import time

VERSION = "1.1.0"
DEFAULT_ADDRESS = 0x29
DEFAULT_FREQ = 400000
DEFAULT_TIMEOUT_MS = 500

_SYSRANGE_START = 0x00
_SYSTEM_SEQUENCE_CONFIG = 0x01
_SYSTEM_INTERMEASUREMENT_PERIOD = 0x04
_SYSTEM_INTERRUPT_CONFIG_GPIO = 0x0A
_SYSTEM_INTERRUPT_CLEAR = 0x0B
_SYSTEM_THRESH_HIGH = 0x0C
_SYSTEM_THRESH_LOW = 0x0E
_RESULT_INTERRUPT_STATUS = 0x13
_RESULT_RANGE_STATUS = 0x14
_GPIO_HV_MUX_ACTIVE_HIGH = 0x84
_I2C_SLAVE_DEVICE_ADDRESS = 0x8A
_MSRC_CONFIG_CONTROL = 0x60
_MSRC_CONFIG_TIMEOUT_MACROP = 0x46
_PRE_RANGE_CONFIG_VCSEL_PERIOD = 0x50
_PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI = 0x51
_FINAL_RANGE_CONFIG_MIN_COUNT_RATE_RTN_LIMIT = 0x44
_FINAL_RANGE_CONFIG_VCSEL_PERIOD = 0x70
_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI = 0x71
_GLOBAL_CONFIG_SPAD_ENABLES_REF_0 = 0xB0
_GLOBAL_CONFIG_REF_EN_START_SELECT = 0xB6
_DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD = 0x4E
_DYNAMIC_SPAD_REF_EN_START_OFFSET = 0x4F
_OSC_CALIBRATE_VAL = 0xF8
_VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV = 0x89

_TUNING = (
    (0xFF,0x01),(0x00,0x00),(0xFF,0x00),(0x09,0x00),(0x10,0x00),(0x11,0x00),
    (0x24,0x01),(0x25,0xFF),(0x75,0x00),(0xFF,0x01),(0x4E,0x2C),(0x48,0x00),
    (0x30,0x20),(0xFF,0x00),(0x30,0x09),(0x54,0x00),(0x31,0x04),(0x32,0x03),
    (0x40,0x83),(0x46,0x25),(0x60,0x00),(0x27,0x00),(0x50,0x06),(0x51,0x00),
    (0x52,0x96),(0x56,0x08),(0x57,0x30),(0x61,0x00),(0x62,0x00),(0x64,0x00),
    (0x65,0x00),(0x66,0xA0),(0xFF,0x01),(0x22,0x32),(0x47,0x14),(0x49,0xFF),
    (0x4A,0x00),(0xFF,0x00),(0x7A,0x0A),(0x7B,0x00),(0x78,0x21),(0xFF,0x01),
    (0x23,0x34),(0x42,0x00),(0x44,0xFF),(0x45,0x26),(0x46,0x05),(0x40,0x40),
    (0x0E,0x06),(0x20,0x1A),(0x43,0x40),(0xFF,0x00),(0x34,0x03),(0x35,0x44),
    (0xFF,0x01),(0x31,0x04),(0x4B,0x09),(0x4C,0x05),(0x4D,0x04),(0xFF,0x00),
    (0x44,0x00),(0x45,0x20),(0x47,0x08),(0x48,0x28),(0x67,0x00),(0x70,0x04),
    (0x71,0x01),(0x72,0xFE),(0x76,0x00),(0x77,0x00),(0xFF,0x01),(0x0D,0x01),
    (0xFF,0x00),(0x80,0x01),(0x01,0xF8),(0xFF,0x01),(0x8E,0x01),(0x00,0x01),
    (0xFF,0x00),(0x80,0x00),
)

def _decode_timeout(value):
    return ((value & 0xFF) << ((value >> 8) & 0xFF)) + 1

def _encode_timeout(value):
    value = int(value)
    if value <= 0:
        return 0
    value -= 1
    exponent = 0
    while value > 255:
        value >>= 1
        exponent += 1
    return ((exponent & 0xFF) << 8) | (value & 0xFF)

def _vcsel_macro_period_ns(vcsel_period_pclks):
    return ((2304 * int(vcsel_period_pclks) * 1655) + 500) // 1000

def _timeout_mclks_to_us(timeout_mclks, vcsel_period_pclks):
    macro_ns = _vcsel_macro_period_ns(vcsel_period_pclks)
    return ((int(timeout_mclks) * macro_ns) + (macro_ns // 2)) // 1000

def _timeout_us_to_mclks(timeout_us, vcsel_period_pclks):
    macro_ns = _vcsel_macro_period_ns(vcsel_period_pclks)
    return ((int(timeout_us) * 1000) + (macro_ns // 2)) // macro_ns

class MihuVL53L0:
    def __init__(self):
        self.i2c = None
        self.address = DEFAULT_ADDRESS
        self.freq = DEFAULT_FREQ
        self.tipo = None
        self.initialized = False
        self.continuous = False
        self.timeout_ms = DEFAULT_TIMEOUT_MS
        self.stop_variable = 0
        self.last_value = None
        self.last_error = None
        self._timing_budget_us = 33000
        self.gpio_mode = "NEW_SAMPLE"
        self.gpio_threshold_mm = None
        self.gpio_active_low = True

    def _write8(self, reg, value):
        self.i2c.writeto_mem(self.address, reg & 0xFF, bytes((value & 0xFF,)))

    def _read8(self, reg):
        return self.i2c.readfrom_mem(self.address, reg & 0xFF, 1)[0]

    def _write16(self, reg, value):
        value = int(value) & 0xFFFF
        self.i2c.writeto_mem(self.address, reg & 0xFF, bytes(((value >> 8) & 0xFF, value & 0xFF)))

    def _read16(self, reg):
        data = self.i2c.readfrom_mem(self.address, reg & 0xFF, 2)
        return (data[0] << 8) | data[1]

    def _write32(self, reg, value):
        value = int(value) & 0xFFFFFFFF
        self.i2c.writeto_mem(self.address, reg & 0xFF, bytes(((value >> 24) & 0xFF,(value >> 16) & 0xFF,(value >> 8) & 0xFF,value & 0xFF)))

    def _read_block(self, reg, length):
        return bytearray(self.i2c.readfrom_mem(self.address, reg & 0xFF, int(length)))

    def _write_block(self, reg, data):
        self.i2c.writeto_mem(self.address, reg & 0xFF, bytes(data))

    def _timeout(self, start_ms):
        return self.timeout_ms > 0 and time.ticks_diff(time.ticks_ms(), start_ms) >= self.timeout_ms

    def _wait_nonzero(self, reg, mask=0xFF):
        start = time.ticks_ms()
        while (self._read8(reg) & mask) == 0:
            if self._timeout(start):
                raise OSError("VL53L0X: timeout no registrador 0x{:02X}".format(reg))
            time.sleep_ms(1)

    def scan(self):
        if self.i2c is None:
            return ()
        try:
            return tuple(self.i2c.scan())
        except Exception:
            return ()

    def _check_sensor(self):
        devices = self.scan()
        if self.address not in devices:
            raise OSError("VL53L0X nao encontrado em 0x{:02X}. I2C={}".format(self.address, devices))
        model = self._read8(0xC0)
        module = self._read8(0xC1)
        revision = self._read8(0xC2)
        if model != 0xEE:
            raise OSError("Dispositivo em 0x{:02X} nao parece VL53L0X (MODEL_ID=0x{:02X})".format(self.address, model))
        return model, module, revision

    def _get_spad_info(self):
        for reg, value in ((0x80,0x01),(0xFF,0x01),(0x00,0x00),(0xFF,0x06)):
            self._write8(reg, value)
        self._write8(0x83, self._read8(0x83) | 0x04)
        for reg, value in ((0xFF,0x07),(0x81,0x01),(0x80,0x01),(0x94,0x6B),(0x83,0x00)):
            self._write8(reg, value)
        self._wait_nonzero(0x83)
        self._write8(0x83, 0x01)
        value = self._read8(0x92)
        count = value & 0x7F
        aperture = bool(value & 0x80)
        self._write8(0x81, 0x00)
        self._write8(0xFF, 0x06)
        self._write8(0x83, self._read8(0x83) & 0xFB)
        for reg, value in ((0xFF,0x01),(0x00,0x01),(0xFF,0x00),(0x80,0x00)):
            self._write8(reg, value)
        return count, aperture

    def _configure_spads(self):
        count, aperture = self._get_spad_info()
        spad_map = self._read_block(_GLOBAL_CONFIG_SPAD_ENABLES_REF_0, 6)
        for reg, value in ((0xFF,0x01),(_DYNAMIC_SPAD_REF_EN_START_OFFSET,0x00),(_DYNAMIC_SPAD_NUM_REQUESTED_REF_SPAD,0x2C),(0xFF,0x00),(_GLOBAL_CONFIG_REF_EN_START_SELECT,0xB4)):
            self._write8(reg, value)
        first = 12 if aperture else 0
        enabled = 0
        for index in range(48):
            byte_index = index // 8
            bit = 1 << (index % 8)
            if index < first or enabled >= count:
                spad_map[byte_index] &= (~bit & 0xFF)
            elif spad_map[byte_index] & bit:
                enabled += 1
        self._write_block(_GLOBAL_CONFIG_SPAD_ENABLES_REF_0, spad_map)

    def _vcsel_period(self, final=False):
        reg = _FINAL_RANGE_CONFIG_VCSEL_PERIOD if final else _PRE_RANGE_CONFIG_VCSEL_PERIOD
        return (self._read8(reg) + 1) << 1

    def _sequence_enables(self):
        value = self._read8(_SYSTEM_SEQUENCE_CONFIG)
        return {"tcc":bool(value & 0x10),"dss":bool(value & 0x08),"msrc":bool(value & 0x04),"pre":bool(value & 0x40),"final":bool(value & 0x80)}

    def _sequence_timeouts(self):
        pre_period = self._vcsel_period(False)
        msrc_mclks = self._read8(_MSRC_CONFIG_TIMEOUT_MACROP) + 1
        msrc_us = _timeout_mclks_to_us(msrc_mclks, pre_period)
        pre_mclks = _decode_timeout(self._read16(_PRE_RANGE_CONFIG_TIMEOUT_MACROP_HI))
        pre_us = _timeout_mclks_to_us(pre_mclks, pre_period)
        final_period = self._vcsel_period(True)
        final_mclks = _decode_timeout(self._read16(_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI))
        if self._sequence_enables()["pre"]:
            final_mclks -= pre_mclks
        final_us = _timeout_mclks_to_us(final_mclks, final_period)
        return {"msrc_us":msrc_us,"pre_us":pre_us,"pre_mclks":pre_mclks,"final_us":final_us,"final_period":final_period}

    def _get_timing_budget(self):
        enables = self._sequence_enables()
        t = self._sequence_timeouts()
        budget = 1910 + 960
        if enables["tcc"]: budget += t["msrc_us"] + 590
        if enables["dss"]: budget += 2 * (t["msrc_us"] + 690)
        elif enables["msrc"]: budget += t["msrc_us"] + 660
        if enables["pre"]: budget += t["pre_us"] + 660
        if enables["final"]: budget += t["final_us"] + 550
        return int(budget)

    def _set_timing_budget(self, budget_us):
        budget_us = max(20000, int(budget_us))
        enables = self._sequence_enables()
        t = self._sequence_timeouts()
        used = 1320 + 960
        if enables["tcc"]: used += t["msrc_us"] + 590
        if enables["dss"]: used += 2 * (t["msrc_us"] + 690)
        elif enables["msrc"]: used += t["msrc_us"] + 660
        if enables["pre"]: used += t["pre_us"] + 660
        if enables["final"]:
            used += 550
            if used > budget_us:
                return False
            final_us = budget_us - used
            final_mclks = _timeout_us_to_mclks(final_us, t["final_period"])
            if enables["pre"]:
                final_mclks += t["pre_mclks"]
            self._write16(_FINAL_RANGE_CONFIG_TIMEOUT_MACROP_HI, _encode_timeout(final_mclks))
        self._timing_budget_us = budget_us
        return True

    def _reference_calibration(self, vhv_byte):
        self._write8(_SYSRANGE_START, 0x01 | (vhv_byte & 0xFF))
        start = time.ticks_ms()
        while (self._read8(_RESULT_INTERRUPT_STATUS) & 0x07) == 0:
            if self._timeout(start):
                raise OSError("VL53L0X: timeout na calibracao")
            time.sleep_ms(1)
        self._write8(_SYSTEM_INTERRUPT_CLEAR, 0x01)
        self._write8(_SYSRANGE_START, 0x00)

    def _init_sensor(self, io_2v8=True):
        self._check_sensor()
        if io_2v8:
            self._write8(_VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV, self._read8(_VHV_CONFIG_PAD_SCL_SDA_EXTSUP_HV) | 0x01)
        for reg, value in ((0x88,0x00),(0x80,0x01),(0xFF,0x01),(0x00,0x00)):
            self._write8(reg, value)
        self.stop_variable = self._read8(0x91)
        for reg, value in ((0x00,0x01),(0xFF,0x00),(0x80,0x00)):
            self._write8(reg, value)
        self._write8(_MSRC_CONFIG_CONTROL, self._read8(_MSRC_CONFIG_CONTROL) | 0x12)
        self._write16(_FINAL_RANGE_CONFIG_MIN_COUNT_RATE_RTN_LIMIT, int(0.25 * 128))
        self._write8(_SYSTEM_SEQUENCE_CONFIG, 0xFF)
        self._configure_spads()
        for reg, value in _TUNING:
            self._write8(reg, value)
        self._write8(_SYSTEM_INTERRUPT_CONFIG_GPIO, 0x04)
        self._write8(_GPIO_HV_MUX_ACTIVE_HIGH, self._read8(_GPIO_HV_MUX_ACTIVE_HIGH) & 0xEF)
        self._write8(_SYSTEM_INTERRUPT_CLEAR, 0x01)
        try:
            budget = self._get_timing_budget()
        except Exception:
            budget = 33000
        self._write8(_SYSTEM_SEQUENCE_CONFIG, 0xE8)
        self._set_timing_budget(budget)
        self._write8(_SYSTEM_SEQUENCE_CONFIG, 0x01)
        self._reference_calibration(0x40)
        self._write8(_SYSTEM_SEQUENCE_CONFIG, 0x02)
        self._reference_calibration(0x00)
        self._write8(_SYSTEM_SEQUENCE_CONFIG, 0xE8)
        self._timing_budget_us = budget

    def begin(self, tipo="I2C", i2c_id=0, sda=None, scl=None, freq=DEFAULT_FREQ,
              address=DEFAULT_ADDRESS, timeout_ms=DEFAULT_TIMEOUT_MS,
              continuous=True, period_ms=0, io_2v8=True):
        """Inicializa o barramento e o VL53L0X uma única vez."""
        tipo_normalizado = str(tipo).strip().upper()
        self.address = int(address) & 0x7F
        self.freq = int(freq)
        self.timeout_ms = int(timeout_ms)
        self.last_value = None
        self.last_error = None
        self.initialized = False
        self.continuous = False
        self.gpio_mode = "NEW_SAMPLE"
        self.gpio_threshold_mm = None
        self.gpio_active_low = True

        if tipo_normalizado in ("I2C","NATIVO","NATIVE","HW","HARDWARE"):
            self.tipo = "I2C"
            if sda is None or scl is None:
                self.i2c = I2C(int(i2c_id), freq=self.freq)
            else:
                self.i2c = I2C(int(i2c_id), sda=Pin(int(sda)), scl=Pin(int(scl)), freq=self.freq)
        elif tipo_normalizado in ("SOFTI2C","SOFT","SOFTWARE"):
            if sda is None or scl is None:
                raise ValueError("SoftI2C exige sda e scl")
            self.tipo = "SOFTI2C"
            self.i2c = SoftI2C(sda=Pin(int(sda)), scl=Pin(int(scl)), freq=self.freq)
        else:
            raise ValueError("tipo deve ser 'I2C' ou 'SOFTI2C'")

        try:
            self._init_sensor(io_2v8=bool(io_2v8))
            self.initialized = True
            if continuous:
                self.startContinuous(period_ms=period_ms)
            return True
        except Exception as error:
            self.last_error = error
            self.initialized = False
            self.continuous = False
            raise

    def startContinuous(self, period_ms=0):
        if not self.initialized:
            raise RuntimeError("VL53L0X nao iniciado. Use begin().")
        for reg, value in ((0x80,0x01),(0xFF,0x01),(0x00,0x00),(0x91,self.stop_variable),(0x00,0x01),(0xFF,0x00),(0x80,0x00)):
            self._write8(reg, value)
        period_ms = int(period_ms)
        if period_ms > 0:
            osc = self._read16(_OSC_CALIBRATE_VAL)
            self._write32(_SYSTEM_INTERMEASUREMENT_PERIOD, period_ms * osc if osc else period_ms)
            self._write8(_SYSRANGE_START, 0x04)
        else:
            self._write8(_SYSRANGE_START, 0x02)
        self.continuous = True
        return True

    def stop(self):
        if not self.initialized:
            return False
        self._write8(_SYSRANGE_START, 0x01)
        for reg, value in ((0xFF,0x01),(0x00,0x00),(0x91,0x00),(0x00,0x01),(0xFF,0x00)):
            self._write8(reg, value)
        self.continuous = False
        return True

    def available(self):
        """
        Informa se o evento configurado no GPIO1 está ativo.

        No modo padrão NEW_SAMPLE:
            True quando existe nova medida.

        Depois de vl53l0.set(distance):
            True quando a distância está abaixo do limite configurado.
        """
        if not self.initialized:
            return False

        try:
            return bool(
                self._read8(
                    _RESULT_INTERRUPT_STATUS
                ) & 0x07
            )
        except Exception as error:
            self.last_error = error
            return False


    @staticmethod
    def _convert_distance(value_mm, unit):
        if value_mm is None:
            return None

        unit = str(unit).strip().lower()

        if unit in ("mm", "milimetro", "milimetros"):
            return int(value_mm)

        if unit in ("cm", "centimetro", "centimetros"):
            return round(float(value_mm) / 10.0, 1)

        raise ValueError("Unidade deve ser 'mm' ou 'cm'")


    def read(self, unit="mm"):
        """
        Leitura contínua e não bloqueante.

        vl53l0.read()       -> milímetros
        vl53l0.read("cm")   -> centímetros
        """

        if not self.initialized:
            raise RuntimeError(
                "VL53L0X nao iniciado. Use vl53l0.begin()."
            )

        try:
            if self.gpio_mode == "NEW_SAMPLE":
                if not self.available():
                    return self._convert_distance(
                        self.last_value,
                        unit
                    )

                value = self._read16(
                    _RESULT_RANGE_STATUS + 10
                )

                self._write8(
                    _SYSTEM_INTERRUPT_CLEAR,
                    0x01
                )

            else:
                # Em modo threshold, o interrupt status representa
                # o limite de distância, não "nova amostra".
                value = self._read16(
                    _RESULT_RANGE_STATUS + 10
                )

            if value > 0:
                self.last_value = int(value)

            self.last_error = None

            return self._convert_distance(
                self.last_value,
                unit
            )

        except Exception as error:
            self.last_error = error

            return self._convert_distance(
                self.last_value,
                unit
            )


    def readCM(self):
        """Retorna a distância em centímetros."""
        return self.read("cm")


    def readMM(self):
        """Retorna a distância em milímetros."""
        return self.read("mm")


    def readBlocking(self, timeout_ms=None, unit="mm"):
        if timeout_ms is None:
            timeout_ms = self.timeout_ms

        start = time.ticks_ms()

        while not self.available():
            if (
                timeout_ms > 0
                and time.ticks_diff(
                    time.ticks_ms(),
                    start
                ) >= timeout_ms
            ):
                raise OSError(
                    "VL53L0X: timeout de leitura"
                )

            time.sleep_ms(1)

        return self.read(unit)


    def set(self, distance, unit="cm", active_low=True):
        """
        Configura o GPIO1 físico do VL53L0X como limiar mínimo.

        Exemplo:
            vl53l0.set(20)

        Como o padrão é unit="cm":
            GPIO1 fica ativo quando distância < 20 cm.

        O padrão é active_low=True:
            abaixo do limite -> GPIO1 = LOW

        Em milímetros:
            vl53l0.set(200, unit="mm")
        """

        if not self.initialized:
            raise RuntimeError(
                "VL53L0X nao iniciado. Use vl53l0.begin()."
            )

        unit_normalized = str(unit).strip().lower()

        if unit_normalized in (
            "cm",
            "centimetro",
            "centimetros"
        ):
            distance_mm = int(
                round(float(distance) * 10.0)
            )

        elif unit_normalized in (
            "mm",
            "milimetro",
            "milimetros"
        ):
            distance_mm = int(
                round(float(distance))
            )

        else:
            raise ValueError(
                "Unidade deve ser 'cm' ou 'mm'"
            )

        if distance_mm < 2:
            raise ValueError(
                "Distancia minima: 2 mm"
            )

        # A ST API converte o valor 16.16 para o registrador
        # dividindo por 2. O registrador trabalha em passos de 2 mm.
        threshold_reg = (
            distance_mm // 2
        ) & 0x0FFF

        self._write16(
            _SYSTEM_THRESH_LOW,
            threshold_reg
        )

        self._write16(
            _SYSTEM_THRESH_HIGH,
            0
        )

        # 0x01 = evento quando a distância cruza o limite inferior.
        self._write8(
            _SYSTEM_INTERRUPT_CONFIG_GPIO,
            0x01
        )

        mux = self._read8(
            _GPIO_HV_MUX_ACTIVE_HIGH
        )

        if active_low:
            mux &= 0xEF
        else:
            mux |= 0x10

        self._write8(
            _GPIO_HV_MUX_ACTIVE_HIGH,
            mux
        )

        self._write8(
            _SYSTEM_INTERRUPT_CLEAR,
            0x01
        )

        self.gpio_mode = "MIN"
        self.gpio_threshold_mm = threshold_reg * 2
        self.gpio_active_low = bool(active_low)

        if unit_normalized.startswith("cm"):
            return round(
                self.gpio_threshold_mm / 10.0,
                1
            )

        return self.gpio_threshold_mm


    def clear(self):
        """Limpa o latch de interrupção do GPIO1."""
        if not self.initialized:
            return False

        self._write8(
            _SYSTEM_INTERRUPT_CLEAR,
            0x01
        )

        return True


    def setNewMeasureGPIO(self, active_low=True):
        """Restaura GPIO1 para indicar nova medida pronta."""

        if not self.initialized:
            raise RuntimeError(
                "VL53L0X nao iniciado. Use vl53l0.begin()."
            )

        self._write8(
            _SYSTEM_INTERRUPT_CONFIG_GPIO,
            0x04
        )

        mux = self._read8(
            _GPIO_HV_MUX_ACTIVE_HIGH
        )

        if active_low:
            mux &= 0xEF
        else:
            mux |= 0x10

        self._write8(
            _GPIO_HV_MUX_ACTIVE_HIGH,
            mux
        )

        self._write8(
            _SYSTEM_INTERRUPT_CLEAR,
            0x01
        )

        self.gpio_mode = "NEW_SAMPLE"
        self.gpio_threshold_mm = None
        self.gpio_active_low = bool(active_low)

        return True


    def setAddress(self, new_address):
        new_address = int(new_address) & 0x7F
        if new_address <= 0 or new_address >= 0x78:
            raise ValueError("Endereco I2C invalido")
        self._write8(_I2C_SLAVE_DEVICE_ADDRESS, new_address)
        self.address = new_address
        return True

    def info(self):
        return {
            "version": VERSION,
            "initialized": self.initialized,
            "interface": self.tipo,
            "address": self.address,
            "frequency": self.freq,
            "continuous": self.continuous,
            "last_value_mm": self.last_value,
            "last_value_cm": (
                None
                if self.last_value is None
                else round(self.last_value / 10.0, 1)
            ),
            "gpio_mode": self.gpio_mode,
            "gpio_threshold_mm": self.gpio_threshold_mm,
            "gpio_active_low": self.gpio_active_low,
            "last_error": self.last_error,
            "i2c_scan": self.scan(),
        }

vl53l0 = MihuVL53L0()
