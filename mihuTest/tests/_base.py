from time import (
    ticks_ms,
    ticks_diff,
)

from ..config import timeout_for
from ..result import TestResult


class PeripheralTest:
    NAME = "UNKNOWN"
    LABEL = "UNKNOWN"

    def timeout_ms(self):
        return timeout_for(
            self.NAME
        )

    def deadline_start(self):
        return ticks_ms()

    def timed_out(
        self,
        started_ms,
        timeout_ms=None,
    ):
        if timeout_ms is None:
            timeout_ms = self.timeout_ms()

        return ticks_diff(
            ticks_ms(),
            started_ms,
        ) >= int(timeout_ms)

    def run(self, context=None):
        return TestResult.not_implemented(
            self.NAME
        )
