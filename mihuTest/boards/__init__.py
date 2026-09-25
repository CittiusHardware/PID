from .ihm import TESTS as IHM_TESTS
from .led import TESTS as LED_TESTS
from .base import TESTS as BASE_TESTS
from .core import TESTS as CORE_TESTS


BOARD_TESTS = {
    "IHM": IHM_TESTS,
    "LED": LED_TESTS,
    "BASE": BASE_TESTS,
    "CORE": CORE_TESTS,
}


BOARD_NAMES = (
    ("IHM", "IHM BOARD"),
    ("LED", "LED BOARD"),
    ("BASE", "BASE BOARD"),
    ("CORE", "CORE BOARD"),
)


def get_tests(board):
    return BOARD_TESTS.get(
        str(board).upper(),
        (),
    )
