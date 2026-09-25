from lib.mihuVL53L0 import vl53l0

vl53l0.begin(
    tipo="SOFTI2C",
    sda=8,
    scl=9,
    freq=100000
)

print(vl53l0.info())

while True:
    distancia = vl53l0.read()
    if distancia is not None:
        print(distancia, "mm")
