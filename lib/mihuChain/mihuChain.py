from machine import I2C, Pin
import struct


# ============================================================
# PROTOCOLO MIHU CHAIN
# ============================================================

CMD_MOTOR_SET  = 0x10
CMD_MOTOR_STOP = 0x11


# ============================================================
# PORTAS DOS MOTORES
# ============================================================

M1 = 0
M2 = 1
M3 = 2
M4 = 3


# ============================================================
# ENDEREÇOS DAS EXPANSÕES
# ============================================================

ADDR_L1 = 0x20
ADDR_L2 = 0x21
ADDR_L3 = 0x22


# ============================================================
# BARRAMENTO I2C 6 VIAS
#
# SDA = GPIO39
# SCL = GPIO40
# ============================================================

_i2c = I2C(
    0,
    sda=Pin(39),
    scl=Pin(40),
    freq=100000
)


# ============================================================
# MOTOR REMOTO
# ============================================================

class RemoteMotor:

    def __init__(self, address, port):
        self.address = address
        self.port = port

    def set(self, speed):

        speed = int(speed)

        if speed > 100:
            speed = 100

        if speed < -100:
            speed = -100

        pacote = struct.pack(
            "<BBb",
            CMD_MOTOR_SET,
            self.port,
            speed
        )

        try:
            _i2c.writeto(
                self.address,
                pacote
            )

        except OSError as erro:
            print(
                "MIHU CHAIN:",
                hex(self.address),
                "nao respondeu:",
                erro
            )


    def stop(self):

        pacote = bytes([
            CMD_MOTOR_STOP,
            self.port
        ])

        try:
            _i2c.writeto(
                self.address,
                pacote
            )

        except OSError as erro:
            print(
                "MIHU CHAIN:",
                hex(self.address),
                "nao respondeu:",
                erro
            )


# ============================================================
# LAYER
# ============================================================

class Layer:

    def __init__(self, address, numero):

        self.address = address
        self.numero = numero

        self.m1 = RemoteMotor(address, M1)
        self.m2 = RemoteMotor(address, M2)
        self.m3 = RemoteMotor(address, M3)
        self.m4 = RemoteMotor(address, M4)


    def connected(self):

        try:
            return self.address in _i2c.scan()

        except:
            return False


# ============================================================
# CONTROLADORAS REMOTAS
# ============================================================

L1 = Layer(ADDR_L1, 1)
L2 = Layer(ADDR_L2, 2)
L3 = Layer(ADDR_L3, 3)


# ============================================================
# SCAN
# ============================================================

def scan():

    print()
    print("=== MIHU CHAIN ===")

    try:

        dispositivos = _i2c.scan()

        if not dispositivos:
            print("Nenhum dispositivo encontrado")
            return []

        for endereco in dispositivos:

            if endereco == 0x20:
                print("L1 encontrada:", hex(endereco))

            elif endereco == 0x21:
                print("L2 encontrada:", hex(endereco))

            elif endereco == 0x22:
                print("L3 encontrada:", hex(endereco))

            elif endereco == 0x3C:
                print("OLED encontrado:", hex(endereco))

            else:
                print("I2C encontrado:", hex(endereco))

        return dispositivos

    except Exception as erro:

        print("Erro no barramento:", erro)

        return []