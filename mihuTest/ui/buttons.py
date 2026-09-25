try:
    from lib.mihuButton import readFlag
except ImportError:
    try:
        from lib.mihuButton.mihuButton import readFlag
    except ImportError:
        readFlag = None


def read():
    if readFlag is None:
        return None

    try:
        return readFlag()
    except Exception:
        return None
