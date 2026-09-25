from time import (
    ticks_ms,
    ticks_add,
    ticks_diff,
    sleep_ms,
)

from .config import (
    FULL_TEST_ORDER,
    STATUS_RUNNING,
    timeout_for,
)
from .state import TestState
from .result import TestResult
from .registry import create_test
from .boards import get_tests
from . import protocol
from .ui.display import result_screen
from .ui.feedback import (
    success as success_sound,
    fail as fail_sound,
)


class TestRunner:
    def __init__(self):
        self.state = TestState()
        self.active = None

        # Testes iniciados pelo software que dependem
        # de validação posterior do operador.
        self.pending = {}

    def _feedback_result(
        self,
        result,
    ):
        if result.passed:
            success_sound()
        elif result.status == "FAIL":
            fail_sound()

    def _finish(self, result):
        self.active = None

        if result.status == STATUS_RUNNING:
            self.state.set(
                result
            )

            timeout_ms = timeout_for(
                result.name
            )

            if (
                isinstance(
                    result.data,
                    dict,
                )
                and result.data.get(
                    "timeout_ms"
                ) is not None
            ):
                timeout_ms = int(
                    result.data[
                        "timeout_ms"
                    ]
                )

            self.pending[
                result.name
            ] = ticks_add(
                ticks_ms(),
                timeout_ms,
            )

            protocol.result(
                result
            )

            return result

        self.pending.pop(
            result.name,
            None,
        )

        self.state.set(
            result
        )

        self._feedback_result(
            result
        )

        protocol.result(
            result
        )

        result_screen(
            result.name,
            result.passed,
            result.message,
        )

        sleep_ms(600)

        return result

    def run_peripheral(
        self,
        name,
        source="LOCAL",
    ):
        name = str(
            name
        ).upper()

        if name in self.pending:
            return TestResult.running(
                name,
                "Validation already pending.",
            )

        test = create_test(
            name
        )

        if test is None:
            result = (
                TestResult
                .failed_result(
                    name,
                    "Unknown test.",
                )
            )
            return self._finish(
                result
            )

        self.active = name

        protocol.running(
            name
        )

        try:
            result = test.run({
                "source": source,
                "runner": self,
            })
        except Exception as error:
            result = (
                TestResult
                .failed_result(
                    name,
                    "Unhandled test error.",
                    {
                        "error": str(error),
                    },
                )
            )

        return self._finish(
            result
        )

    def run_board(
        self,
        board,
        source="LOCAL",
    ):
        board = str(
            board
        ).upper()

        results = []

        protocol.message(
            "BOARD START: "
            + board
        )

        for name in get_tests(
            board
        ):
            results.append(
                self.run_peripheral(
                    name,
                    source=source,
                )
            )

        protocol.message(
            "BOARD END: "
            + board
        )

        protocol.report(
            self.state
        )

        return results

    def run_full(
        self,
        source="LOCAL",
    ):
        results = []

        protocol.message(
            "FULL TEST START"
        )

        for name in FULL_TEST_ORDER:
            results.append(
                self.run_peripheral(
                    name,
                    source=source,
                )
            )

        protocol.message(
            "FULL TEST END"
        )

        protocol.report(
            self.state
        )

        return results

    def approve(
        self,
        name,
        passed,
        message="Software validation.",
    ):
        name = str(
            name
        ).upper()

        self.pending.pop(
            name,
            None,
        )

        result = (
            TestResult
            .passed_result(
                name,
                message,
            )
            if passed
            else TestResult
            .failed_result(
                name,
                message,
            )
        )

        self.state.set(
            result
        )

        self._feedback_result(
            result
        )

        protocol.result(
            result
        )

        return result

    def tick(self):
        """
        Aplica timeout aos testes RUNNING que aguardam
        confirmação do software.
        """
        if not self.pending:
            return

        now = ticks_ms()

        expired = []

        for name, deadline in (
            self.pending.items()
        ):
            if ticks_diff(
                now,
                deadline,
            ) >= 0:
                expired.append(
                    name
                )

        for name in expired:
            self.pending.pop(
                name,
                None,
            )

            result = (
                TestResult
                .failed_result(
                    name,
                    "Test timeout.",
                )
            )

            self.state.set(
                result
            )

            fail_sound()

            protocol.result(
                result
            )

            result_screen(
                name,
                False,
                "Test timeout.",
            )

    def report(self):
        protocol.report(
            self.state
        )

        return self.state.to_dict()

    def clear(self):
        self.pending = {}
        self.state.clear()

        protocol.message(
            "REPORT CLEARED"
        )


runner = TestRunner()
