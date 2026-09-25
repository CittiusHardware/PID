from time import sleep_ms

from .config import VERSION
from .runner import runner
from .protocol import ready
from .serial import SerialCommands
from .commands import (
    handle as handle_command,
)
from .i18n import t

from .ui.display import (
    init as display_init,
    show_lines,
)
from .ui.buttons import (
    read as read_button,
)
from .ui.language import (
    select_language,
)
from .ui.menu import TestMenu


def run():
    display_init()

    # ========================================================
    # LANGUAGE SELECTION
    # ========================================================

    language = (
        select_language()
    )

    # Protocol remains English but announces selected UI language.
    ready(
        VERSION
    )

    show_lines([
        t("test_title"),
        "",
        t("factory_service"),
        "",
        t("starting"),
    ])

    sleep_ms(
        500
    )

    serial = SerialCommands()

    menu = TestMenu(
        runner
    )

    while True:

        # ====================================================
        # SOFTWARE PC
        # ====================================================

        command = (
            serial.read()
        )

        if command is not None:
            handled = (
                handle_command(
                    command,
                    runner,
                )
            )

            if handled:
                menu.draw()

        # ====================================================
        # DISPLAY + BUTTONS
        # ====================================================

        key = read_button()

        if key is not None:
            menu.tick(
                key
            )

        # ====================================================
        # TIMEOUTS / BACKGROUND STATE
        # ====================================================

        runner.tick()

        sleep_ms(
            5
        )
