# sound.py
# Leitura bruta do sensor analógico de som.

from .constants import SOM


def getSound(porta):

    porta.wait_connection(SOM)

    porta.detector.atualizar(
        forcar=True
    )

    return porta.get_adc()
