from .config import (
    STATUS_PENDING,
    STATUS_RUNNING,
    STATUS_PASS,
    STATUS_FAIL,
    STATUS_NOT_IMPLEMENTED,
)


class TestResult:
    def __init__(
        self,
        name,
        status=STATUS_PENDING,
        message="",
        data=None,
    ):
        self.name = str(name).upper()
        self.status = status
        self.message = message
        self.data = data

    @property
    def passed(self):
        return self.status == STATUS_PASS

    def to_dict(self):
        return {
            "name": self.name,
            "status": self.status,
            "message": self.message,
            "data": self.data,
        }

    @classmethod
    def running(cls, name, message=""):
        return cls(
            name,
            STATUS_RUNNING,
            message,
        )

    @classmethod
    def passed_result(cls, name, message="", data=None):
        return cls(
            name,
            STATUS_PASS,
            message,
            data,
        )

    @classmethod
    def failed_result(cls, name, message="", data=None):
        return cls(
            name,
            STATUS_FAIL,
            message,
            data,
        )

    @classmethod
    def not_implemented(cls, name):
        return cls(
            name,
            STATUS_NOT_IMPLEMENTED,
            "Test not implemented.",
        )
