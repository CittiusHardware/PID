from time import (
    ticks_ms,
    sleep_ms,
)

from ._base import PeripheralTest
from ..result import TestResult
from ..i18n import t
from ..ui.display import show_lines
from ..ui.buttons import (
    read as read_button,
)
from ..ui.feedback import click


class SoundTest(PeripheralTest):
    NAME = "SOUND"
    LABEL = "SOUND"

    def run(self, context=None):
        try:
            from lib.mihuSound import som
        except ImportError:
            return (
                TestResult
                .failed_result(
                    self.NAME,
                    "mihuSound library not found.",
                )
            )

        try:
            show_lines([
                t("sound_test"),
                "",
                t("listen"),
            ])

            # This is the sound under test, not the result sound.
            som.system_ok(
                100
            )

        except Exception as error:
            return (
                TestResult
                .failed_result(
                    self.NAME,
                    "Sound output error.",
                    {
                        "error": str(error),
                    },
                )
            )

        timeout_ms = (
            self.timeout_ms()
        )

        source = (
            context or {}
        ).get(
            "source",
            "LOCAL",
        )

        if source == "SOFTWARE":
            return TestResult.running(
                self.NAME,
                "Waiting software validation.",
                {
                    "timeout_ms": timeout_ms,
                },
            )

        sleep_ms(200)

        show_lines([
            t("sound_test"),
            "",
            t("heard_sound"),
            "",
            t("ok_pass"),
            t("back_fail"),
        ])

        started = ticks_ms()

        while True:
            key = read_button()

            if key == "OK":
                click()

                return (
                    TestResult
                    .passed_result(
                        self.NAME,
                        "Sound validated.",
                    )
                )

            if key == "BACK":
                return (
                    TestResult
                    .failed_result(
                        self.NAME,
                        "Sound rejected.",
                    )
                )

            if self.timed_out(
                started,
                timeout_ms,
            ):
                return (
                    TestResult
                    .failed_result(
                        self.NAME,
                        "Sound test timeout.",
                    )
                )

            sleep_ms(20)
