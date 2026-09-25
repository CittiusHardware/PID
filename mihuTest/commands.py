from .boards import BOARD_TESTS


def handle(command, runner):
    if command is None:
        return False

    if isinstance(command, dict):
        action = str(
            command.get("cmd", "")
        ).upper()

        if action == "RUN_TEST":
            runner.run_peripheral(
                command.get("test"),
                source="SOFTWARE",
            )
            return True

        if action == "RUN_BOARD":
            runner.run_board(
                command.get("board"),
                source="SOFTWARE",
            )
            return True

        if action == "RUN_FULL":
            runner.run_full(
                source="SOFTWARE",
            )
            return True

        if action == "REPORT":
            runner.report()
            return True

        if action == "CLEAR":
            runner.clear()
            return True

        if action == "VALIDATE":
            runner.approve(
                command.get("test"),
                bool(command.get("passed")),
            )
            return True

        return False

    text = str(command).strip().upper()

    if text == "PING":
        print('{"type":"PONG"}')
        return True

    if text == "RUN_FULL":
        runner.run_full(
            source="SOFTWARE",
        )
        return True

    if text == "REPORT_FULL":
        runner.report()
        return True

    if text == "CLEAR_REPORT":
        runner.clear()
        return True

    if text.startswith("RUN_TEST:"):
        runner.run_peripheral(
            text.split(":", 1)[1],
            source="SOFTWARE",
        )
        return True

    if text.startswith("RUN_BOARD:"):
        runner.run_board(
            text.split(":", 1)[1],
            source="SOFTWARE",
        )
        return True

    if text.startswith("TEST_OK:"):
        runner.approve(
            text.split(":", 1)[1],
            True,
        )
        return True

    if text.startswith("TEST_FAIL:"):
        runner.approve(
            text.split(":", 1)[1],
            False,
        )
        return True

    return False
