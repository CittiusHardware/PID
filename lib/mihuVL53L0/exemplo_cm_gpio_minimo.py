from lib.mihuVL53L0 import vl53l0

vl53l0.begin(
    tipo="I2C",
    i2c_id=0,
    sda=39,
    scl=40,
    freq=400000
)

# GPIO1 do VL53L0X fica LOW abaixo de 20 cm
vl53l0.set(20,unit="cm")

while True:
    distancia = vl53l0.readCM()

    if distancia is not None:
        print(distancia, "cm")
