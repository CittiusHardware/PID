from .config import FULL_TEST_ORDER
from .result import TestResult


class TestState:
    def __init__(self):
        self.results = {}

        for name in FULL_TEST_ORDER:
            self.results[name] = TestResult(name)

    def set(self, result):
        self.results[result.name] = result
        return result

    def get(self, name):
        return self.results.get(
            str(name).upper()
        )

    def clear(self):
        self.__init__()

    def summary(self):
        passed = 0
        failed = 0
        pending = 0
        not_implemented = 0

        for result in self.results.values():
            status = result.status

            if status == "PASS":
                passed += 1
            elif status == "FAIL":
                failed += 1
            elif status == "NOT_IMPLEMENTED":
                not_implemented += 1
            else:
                pending += 1

        return {
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "not_implemented": not_implemented,
            "total": len(self.results),
        }

    def to_dict(self):
        return {
            "summary": self.summary(),
            "results": [
                result.to_dict()
                for result in self.results.values()
            ],
        }
