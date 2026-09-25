from time import (
    ticks_ms,
    ticks_diff,
    sleep_ms,
)

from ._base import PeripheralTest
from ..result import TestResult
from ..i18n import t
from ..ui.display import (
    show_lines,
    fill_white,
)
from ..ui.buttons import (
    read as read_button,
)
from ..ui.feedback import click


class DisplayTest(PeripheralTest):
    NAME = "DISPLAY"
    LABEL = "DISPLAY"

    def run(self, context=None):
        source = (
            context or {}
        ).get(
            "source",
            "LOCAL",
        )

        timeout_ms = (
            self.timeout_ms()
        )

        show_lines([
            t("display_test"),
            "",
            t("full_white"),
            t("check_dead_pixels"),
            "",
            t("starting"),
        ])

        sleep_ms(
            800
        )

        # Every pixel ON.
        fill_white()

        if source == "SOFTWARE":
            return TestResult.running(
                self.NAME,
                "Waiting software validation.",
                {
                    "timeout_ms": timeout_ms,
                },
            )

        started = ticks_ms()

        while True:
            key = read_button()

            if key == "OK":
                click()

                return TestResult.passed_result(
                    self.NAME,
                    "No dead pixels detected.",
                )

            if key == "BACK":
                return TestResult.failed_result(
                    self.NAME,
                    "Display pixel failure.",
                )

            if ticks_diff(
                ticks_ms(),
                started,
            ) >= timeout_ms:
                return TestResult.failed_result(
                    self.NAME,
                    "Display test timeout.",
                )

            sleep_ms(20)
