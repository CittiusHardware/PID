from lib.mihuVL53L0 import vl53l0

vl53l0.begin(
    tipo="I2C",
    i2c_id=0,
    sda=39,
    scl=40,
    freq=400000
)

print(vl53l0.info())

while True:
    distancia = vl53l0.read()
    if distancia is not None:
        print(distancia, "mm")
