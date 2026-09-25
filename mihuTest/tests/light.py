from time import (
    ticks_ms,
    ticks_diff,
    sleep_ms,
)

from ._base import PeripheralTest
from ..config import (
    LIGHT_LEFT_SOURCE,
    LIGHT_RIGHT_SOURCE,
    LIGHT_LEFT_ADDRESS,
    LIGHT_RIGHT_ADDRESS,
    LIGHT_BASE_SAMPLES,
    LIGHT_SAMPLE_INTERVAL_MS,
    LIGHT_MIN_DELTA_LUX,
    LIGHT_DELTA_PERCENT,
    LIGHT_CONFIRM_READS,
)
from ..result import TestResult
from ..i18n import t
from ..ui.display import show_lines


def _import_light_library():
    """
    Aceita as organizações mais prováveis da biblioteca.
    """

    try:
        from lib.lightSensor import (
            lux1,
            lux2,
            light,
        )
        return lux1, lux2, light

    except ImportError:
        pass

    try:
        from lightSensor import (
            lux1,
            lux2,
            light,
        )
        return lux1, lux2, light

    except ImportError:
        pass

    try:
        from lib.mihuLight.lightSensor import (
            lux1,
            lux2,
            light,
        )
        return lux1, lux2, light

    except ImportError:
        pass

    return None, None, None


class _LightSensorTest(PeripheralTest):
    SENSOR_SOURCE = None
    EXPECTED_ADDRESS = None
    SIDE_KEY = None

    def _sensor_objects(self):
        lux1, lux2, light = (
            _import_light_library()
        )

        if light is None:
            return None, None

        if self.SENSOR_SOURCE == "lux1":
            return lux1, light

        if self.SENSOR_SOURCE == "lux2":
            return lux2, light

        return None, light

    def _average(self, sensor, count):
        values = []

        for _ in range(
            max(1, int(count))
        ):
            value = int(
                sensor.read()
            )

            values.append(
                value
            )

            sleep_ms(
                LIGHT_SAMPLE_INTERVAL_MS
            )

        if not values:
            return 0

        return int(
            (
                sum(values)
                / len(values)
            )
            + 0.5
        )

    def _required_delta(self, baseline):
        relative = int(
            (
                abs(int(baseline))
                * LIGHT_DELTA_PERCENT
            )
            / 100
        )

        return max(
            int(LIGHT_MIN_DELTA_LUX),
            relative,
        )

    def run(self, context=None):
        sensor, light = (
            self._sensor_objects()
        )

        if sensor is None or light is None:
            return TestResult.failed_result(
                self.NAME,
                "lightSensor library not found.",
            )

        # ----------------------------------------------------
        # 1) Verifica presença física no barramento I2C
        # ----------------------------------------------------

        try:
            addresses = light.scan()
        except Exception as error:
            return TestResult.failed_result(
                self.NAME,
                "Light I2C scan error.",
                {
                    "error": str(error),
                },
            )

        if self.EXPECTED_ADDRESS not in addresses:
            return TestResult.failed_result(
                self.NAME,
                "Light sensor not found.",
                {
                    "expected_address": (
                        "0x{:02X}".format(
                            self.EXPECTED_ADDRESS
                        )
                    ),
                    "i2c_addresses": [
                        "0x{:02X}".format(addr)
                        for addr in addresses
                    ],
                },
            )

        # ----------------------------------------------------
        # 2) Verifica se o BH1750 aceita inicialização
        # ----------------------------------------------------

        try:
            if not sensor.available():
                return TestResult.failed_result(
                    self.NAME,
                    "Light sensor unavailable.",
                    {
                        "address": (
                            "0x{:02X}".format(
                                self.EXPECTED_ADDRESS
                            )
                        ),
                        "error": str(
                            sensor.lastError()
                        ),
                    },
                )

            # Garante modo contínuo de alta resolução.
            sensor.set("high")

        except Exception as error:
            return TestResult.failed_result(
                self.NAME,
                "Light sensor initialization error.",
                {
                    "error": str(error),
                },
            )

        # ----------------------------------------------------
        # 3) Mede referência inicial
        # ----------------------------------------------------

        side = t(
            self.SIDE_KEY
        )

        show_lines([
            t("light_test"),
            side,
            "",
            t("waiting"),
        ])

        try:
            baseline = self._average(
                sensor,
                LIGHT_BASE_SAMPLES,
            )

        except Exception as error:
            return TestResult.failed_result(
                self.NAME,
                "Light sensor read error.",
                {
                    "error": str(error),
                },
            )

        required_delta = (
            self._required_delta(
                baseline
            )
        )

        # ----------------------------------------------------
        # 4) Exige mudança REAL da luminosidade
        # ----------------------------------------------------
        #
        # O operador pode cobrir OU iluminar o sensor.
        # Na futura jiga automática, basta colocar um LED diante
        # do sensor e alterar o estado do LED nesta etapa.
        #
        # Não exigimos que a leitura suba ou desça:
        # apenas que haja uma mudança suficientemente grande.

        show_lines([
            t("light_test"),
            side,
            t("cover_or_light"),
            "",
            t("baseline")
            + ": "
            + str(baseline),
        ])

        started = ticks_ms()
        confirmations = 0

        last_value = baseline
        max_delta = 0

        while not self.timed_out(
            started
        ):
            try:
                current = int(
                    sensor.read()
                )

            except Exception as error:
                return TestResult.failed_result(
                    self.NAME,
                    "Light sensor read error.",
                    {
                        "error": str(error),
                    },
                )

            delta = abs(
                current
                - baseline
            )

            last_value = current

            if delta > max_delta:
                max_delta = delta

            if delta >= required_delta:
                confirmations += 1
            else:
                confirmations = 0

            remaining_ms = (
                self.timeout_ms()
                - ticks_diff(
                    ticks_ms(),
                    started,
                )
            )

            if remaining_ms < 0:
                remaining_ms = 0

            show_lines([
                t("light_test"),
                side,
                t("baseline")
                + ": "
                + str(baseline),
                t("current")
                + ": "
                + str(current),
                t("delta")
                + ": "
                + str(delta),
                str(
                    remaining_ms // 1000
                )
                + "s",
            ])

            if (
                confirmations
                >= LIGHT_CONFIRM_READS
            ):
                return TestResult.passed_result(
                    self.NAME,
                    "Light change detected.",
                    {
                        "sensor": (
                            self.SENSOR_SOURCE
                        ),
                        "address": (
                            "0x{:02X}".format(
                                self.EXPECTED_ADDRESS
                            )
                        ),
                        "baseline_lux": baseline,
                        "current_lux": current,
                        "delta_lux": delta,
                        "required_delta_lux": (
                            required_delta
                        ),
                    },
                )

            sleep_ms(
                LIGHT_SAMPLE_INTERVAL_MS
            )

        # ----------------------------------------------------
        # 5) Timeout sem resposta de luz
        # ----------------------------------------------------

        return TestResult.failed_result(
            self.NAME,
            "No light change detected.",
            {
                "sensor": self.SENSOR_SOURCE,
                "address": (
                    "0x{:02X}".format(
                        self.EXPECTED_ADDRESS
                    )
                ),
                "baseline_lux": baseline,
                "last_lux": last_value,
                "max_delta_lux": max_delta,
                "required_delta_lux": (
                    required_delta
                ),
            },
        )


class LightLeftTest(_LightSensorTest):
    NAME = "LIGHT_LEFT"
    LABEL = "LIGHT_LEFT"

    SENSOR_SOURCE = (
        LIGHT_LEFT_SOURCE
    )

    EXPECTED_ADDRESS = (
        LIGHT_LEFT_ADDRESS
    )

    SIDE_KEY = "left_sensor"


class LightRightTest(_LightSensorTest):
    NAME = "LIGHT_RIGHT"
    LABEL = "LIGHT_RIGHT"

    SENSOR_SOURCE = (
        LIGHT_RIGHT_SOURCE
    )

    EXPECTED_ADDRESS = (
        LIGHT_RIGHT_ADDRESS
    )

    SIDE_KEY = "right_sensor"
