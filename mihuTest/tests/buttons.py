from time import (
    ticks_ms,
    ticks_diff,
    sleep_ms,
)

from ._base import PeripheralTest
from ..config import (
    BUTTON_SEQUENCE,
    BUTTON_STEP_TIMEOUT_MS,
)
from ..result import TestResult
from ..i18n import t
from ..ui.display import show_lines
from ..ui.buttons import (
    read as read_button,
)
from ..ui.feedback import click


class ButtonsTest(PeripheralTest):
    NAME = "BUTTONS"
    LABEL = "BUTTONS"

    def run(self, context=None):
        detected = []

        test_started = ticks_ms()
        total_timeout_ms = (
            self.timeout_ms()
        )

        for index, expected in enumerate(
            BUTTON_SEQUENCE
        ):
            show_lines([
                t("button_test"),
                "",
                t("press"),
                expected,
                "",
                str(index + 1)
                + "/"
                + str(len(BUTTON_SEQUENCE)),
            ])

            step_started = (
                ticks_ms()
            )

            while True:
                key = read_button()

                if key == expected:
                    if key == "OK":
                        click()

                    detected.append(
                        expected
                    )
                    break

                if ticks_diff(
                    ticks_ms(),
                    step_started,
                ) >= BUTTON_STEP_TIMEOUT_MS:
                    return (
                        TestResult
                        .failed_result(
                            self.NAME,
                            "Timeout on "
                            + expected,
                            {
                                "detected": detected,
                                "expected": expected,
                            },
                        )
                    )

                if ticks_diff(
                    ticks_ms(),
                    test_started,
                ) >= total_timeout_ms:
                    return (
                        TestResult
                        .failed_result(
                            self.NAME,
                            "Button test timeout.",
                            {
                                "detected": detected,
                            },
                        )
                    )

                sleep_ms(20)

        return TestResult.passed_result(
            self.NAME,
            "All buttons detected.",
            {
                "buttons": detected,
            },
        )
