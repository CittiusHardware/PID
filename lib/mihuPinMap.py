# =============================================================
# MIHU Pin Map — Mapeamento Oficial do Hardware
# =============================================================

# -------------------------
# SERVOS (IDs numéricos)
# -------------------------
S1, S2, S3, S4 = 1, 2, 3, 4
S5, S6, S7, S8 = 5, 6, 7, 8

# Mapeamento dos canais do PCA9685 para cada servo
SERVO_CHANNELS = {
    S1: 8,
    S2: 9,
    S3: 10,
    S4: 11,
    S5: 12,
    S6: 13,
    S7: 14,
    S8: 15,
}

# -------------------------
# MOTORES (IDs numéricos)
# -------------------------
M1, M2, M3, M4 = 1, 2, 3, 4

# Cada motor usa DOIS canais do PCA9685 (A e B)
MOTOR_CHANNELS = {
    M1: (0, 1),
    M2: (2, 3),
    M3: (4, 5),
    M4: (6, 7),
}

# -------------------------
# ENCODERS DOS MOTORES
# -------------------------
ENCODER_PINS = {
    M1: (11, 41),
    M2: (12, 47),
    M3: (13, 42),
    M4: (14, 45),
}

# -------------------------
# I2C PRINCIPAL
# -------------------------
I2C_SDA = 39
I2C_SCL = 40

# Endereço padrão do PCA9685
PCA_ADDRESS = 0x40

# -------------------------
# TAGS DA PLACA (GPIOs diretos)
# -------------------------
LED_RGB     = 48
BTN_ANALOG  = 10   # Botões ADC
