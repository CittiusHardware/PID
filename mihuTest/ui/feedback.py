try:
    from lib.mihuSound import som
except Exception:
    som = None


def navigation():
    """
    UP / DOWN / BACK navigation.
    """
    if som is None:
        return

    try:
        som.press(100)
    except Exception:
        pass


def click():
    """
    OK button / selection click.
    This is deliberately NOT the PASS sound.
    """
    if som is None:
        return

    try:
        som.click(100)
    except Exception:
        pass


def success():
    """
    Test result PASS.
    """
    if som is None:
        return

    try:
        som.system_ok(100)
    except Exception:
        pass


def fail():
    """
    Test result FAIL / timeout.
    """
    if som is None:
        return

    try:
        som.error(100)
    except Exception:
        pass


# Compatibility aliases.
ok = success
error = fail
