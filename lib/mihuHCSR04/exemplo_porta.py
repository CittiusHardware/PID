from lib.mihuHCSR04 import hcsr04
from time import sleep_ms


# P1:
# ECHO    = GPIO18
# TRIGGER = GPIO44

hcsr04.begin(
    porta="P2"
)


while True:

    distancia = hcsr04.readCM()

    print(
        distancia,
        "cm"
    )

    sleep_ms(
        100
    )
