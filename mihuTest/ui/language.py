from time import sleep_ms

from ..i18n import (
    LANGUAGES,
    set_language,
)
from .display import show_menu
from .buttons import read as read_button
from .feedback import (
    navigation,
    click,
)


def select_language():
    """
    Language is selected every time TEST mode starts.

    Order:
        Chinese
        English
        Spanish
        Portuguese
    """
    index = 0

    labels = tuple(
        label
        for code, label
        in LANGUAGES
    )

    while True:
        show_menu(
            "LANGUAGE",
            labels,
            index,
        )

        key = read_button()

        if key == "UP":
            navigation()

            index = (
                index - 1
            ) % len(LANGUAGES)

        elif key == "DOWN":
            navigation()

            index = (
                index + 1
            ) % len(LANGUAGES)

        elif key == "OK":
            click()

            code = LANGUAGES[
                index
            ][0]

            set_language(
                code
            )

            return code

        sleep_ms(20)
