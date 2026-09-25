from time import sleep_ms

try:
    from lib.mihuOled import mihuOled as oled
except Exception:
    oled = None


def run():
    if oled is not None:
        try:
            oled.init()
            oled.clear()
            oled.text(
                "APPLICATION MODE",
                0,
                0,
                scale=1,
                color=1,
                sync=True
            )
        except Exception:
            pass

    print("APPLICATION MODE")

    # Substitua este loop pelo main real da aplicação.
    while True:
        sleep_ms(1000)
