from lib.mihuHCSR04 import hcsr04
from time import sleep_ms


hcsr04.begin(
    echo=18,
    trigger=44
)


while True:

    print(
        hcsr04.readMM(),
        "mm"
    )

    sleep_ms(
        100
    )
