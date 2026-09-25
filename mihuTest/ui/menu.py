from .display import (
    show_lines,
    show_menu,
)
from .feedback import (
    navigation,
    click,
)
from ..i18n import (
    t,
    board_label,
    test_label,
)
from ..boards import BOARD_NAMES
from ..registry import PERIPHERAL_NAMES


class TestMenu:
    MAIN_ITEMS = (
        ("full_test", "FULL"),
        ("board_test", "BOARD"),
        ("peripheral_test", "PERIPHERAL"),
        ("report", "REPORT"),
    )

    def __init__(self, runner):
        self.runner = runner

        self.level = "MAIN"
        self.index = 0

        self.draw()

    def _items(self):
        if self.level == "MAIN":
            return tuple(
                (
                    t(label_key),
                    value,
                )
                for label_key, value
                in self.MAIN_ITEMS
            )

        if self.level == "BOARD":
            return tuple(
                (
                    board_label(name),
                    name,
                )
                for name, old_label
                in BOARD_NAMES
            )

        if self.level == "PERIPHERAL":
            return tuple(
                (
                    test_label(name),
                    name,
                )
                for name
                in PERIPHERAL_NAMES
            )

        return ()

    def _title(self):
        if self.level == "MAIN":
            return t("test_title")

        if self.level == "BOARD":
            return t("board_test")

        if self.level == "PERIPHERAL":
            return t("peripheral_test")

        if self.level == "REPORT":
            return t("test_report")

        return t("test_title")

    def draw(self):
        if self.level == "REPORT":
            summary = (
                self.runner
                .state
                .summary()
            )

            show_lines([
                t("test_report"),
                "",
                t("pass")
                + ": "
                + str(summary["passed"]),
                t("fail")
                + ": "
                + str(summary["failed"]),
                t("pending")
                + ": "
                + str(summary["pending"]),
                t("back_return"),
            ])
            return

        items = self._items()

        if not items:
            return

        if self.index >= len(items):
            self.index = 0

        labels = tuple(
            item[0]
            for item in items
        )

        show_menu(
            self._title(),
            labels,
            self.index,
        )

    def _go_main(self):
        self.level = "MAIN"
        self.index = 0
        self.draw()

    def tick(self, key):
        if key is None:
            return

        # ====================================================
        # REPORT
        # ====================================================

        if self.level == "REPORT":
            if key == "BACK":
                navigation()
                self._go_main()

            return

        items = self._items()

        if not items:
            self._go_main()
            return

        # ====================================================
        # NAVIGATION
        # ====================================================

        if key == "UP":
            navigation()

            self.index = (
                self.index - 1
            ) % len(items)

            self.draw()
            return

        if key == "DOWN":
            navigation()

            self.index = (
                self.index + 1
            ) % len(items)

            self.draw()
            return

        if key == "BACK":
            navigation()

            if self.level != "MAIN":
                self._go_main()

            return

        if key != "OK":
            return

        # OK is only a click.
        # PASS sound belongs exclusively to a successful test.
        click()

        label, selected = (
            items[self.index]
        )

        # ====================================================
        # MAIN
        # ====================================================

        if self.level == "MAIN":

            if selected == "FULL":
                self.runner.run_full(
                    source="LOCAL",
                )
                self.draw()
                return

            if selected == "BOARD":
                self.level = "BOARD"
                self.index = 0
                self.draw()
                return

            if selected == "PERIPHERAL":
                self.level = (
                    "PERIPHERAL"
                )
                self.index = 0
                self.draw()
                return

            if selected == "REPORT":
                self.level = "REPORT"
                self.index = 0
                self.draw()
                return

        # ====================================================
        # BOARD
        # ====================================================

        if self.level == "BOARD":
            self.runner.run_board(
                selected,
                source="LOCAL",
            )

            self.draw()
            return

        # ====================================================
        # PERIPHERAL
        # ====================================================

        if self.level == "PERIPHERAL":
            self.runner.run_peripheral(
                selected,
                source="LOCAL",
            )

            self.draw()
