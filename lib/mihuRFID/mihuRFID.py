"""
mihuRFID - Driver MicroPython para MFRC522 via I2C.

Baseado na logica da biblioteca MFRC522_I2C usada no projeto MIHU.

Foco:
- MFRC522 em I2C (endereco padrao do modulo: 0x28)
- RST fisico nao necessario
- MIFARE Classic
- leitura de UID
- leitura/escrita de blocos
- leitura/escrita de texto
- verificacao da escrita
- leitura unica enquanto o mesmo cartao permanece no leitor

Exemplo:
    from machine import Pin, I2C
    from mihuRFID import MihuRFID

    i2c = I2C(0, sda=Pin(39), scl=Pin(40), freq=100000)
    rfid = MihuRFID(i2c, address=0x28)

    print(rfid.version_hex())
"""

try:
    from time import sleep_ms, ticks_ms, ticks_diff
except ImportError:
    import time

    def sleep_ms(ms):
        time.sleep(ms / 1000.0)

    def ticks_ms():
        return int(time.monotonic() * 1000)

    def ticks_diff(a, b):
        return a - b


class MihuRFID:
    # =========================================================
    # STATUS
    # =========================================================

    STATUS_OK = 1
    STATUS_ERROR = 2
    STATUS_COLLISION = 3
    STATUS_TIMEOUT = 4
    STATUS_NO_ROOM = 5
    STATUS_INTERNAL_ERROR = 6
    STATUS_INVALID = 7
    STATUS_CRC_WRONG = 8
    STATUS_MIFARE_NACK = 9

    # =========================================================
    # REGISTRADORES MFRC522
    # =========================================================

    CommandReg = 0x01
    ComIEnReg = 0x02
    DivIEnReg = 0x03
    ComIrqReg = 0x04
    DivIrqReg = 0x05
    ErrorReg = 0x06
    Status1Reg = 0x07
    Status2Reg = 0x08
    FIFODataReg = 0x09
    FIFOLevelReg = 0x0A
    WaterLevelReg = 0x0B
    ControlReg = 0x0C
    BitFramingReg = 0x0D
    CollReg = 0x0E

    ModeReg = 0x11
    TxModeReg = 0x12
    RxModeReg = 0x13
    TxControlReg = 0x14
    TxASKReg = 0x15

    CRCResultRegH = 0x21
    CRCResultRegL = 0x22
    RFCfgReg = 0x26
    TModeReg = 0x2A
    TPrescalerReg = 0x2B
    TReloadRegH = 0x2C
    TReloadRegL = 0x2D

    VersionReg = 0x37

    # =========================================================
    # COMANDOS DO MFRC522
    # =========================================================

    PCD_Idle = 0x00
    PCD_CalcCRC = 0x03
    PCD_Transceive = 0x0C
    PCD_MFAuthent = 0x0E
    PCD_SoftReset = 0x0F

    # =========================================================
    # COMANDOS PICC / MIFARE
    # =========================================================

    PICC_CMD_REQA = 0x26
    PICC_CMD_WUPA = 0x52
    PICC_CMD_CT = 0x88

    PICC_CMD_SEL_CL1 = 0x93
    PICC_CMD_SEL_CL2 = 0x95
    PICC_CMD_SEL_CL3 = 0x97

    PICC_CMD_HLTA = 0x50

    PICC_CMD_MF_AUTH_KEY_A = 0x60
    PICC_CMD_MF_AUTH_KEY_B = 0x61
    PICC_CMD_MF_READ = 0x30
    PICC_CMD_MF_WRITE = 0xA0

    MF_ACK = 0x0A

    DEFAULT_KEY = b"\xFF\xFF\xFF\xFF\xFF\xFF"

    # =========================================================
    # INIT
    # =========================================================

    def __init__(
        self,
        i2c,
        address=0x28,
        auto_init=True,
        debug=False,
        presence_misses=4,
    ):
        self.i2c = i2c
        self.address = address
        self.debug = debug

        self.uid = b""
        self.sak = 0

        self.last_status = self.STATUS_OK
        self.last_error = None
        self.last_write_status = self.STATUS_OK

        # Controle de leitura unica
        self._locked_uid = None
        self._presence_misses = 0
        self._presence_misses_limit = max(1, int(presence_misses))

        if auto_init:
            self.init()

    # =========================================================
    # UTILITARIOS
    # =========================================================

    def _log(self, *args):
        if self.debug:
            print(*args)

    def status_name(self, status):
        names = {
            self.STATUS_OK: "Success",
            self.STATUS_ERROR: "Error in communication",
            self.STATUS_COLLISION: "Collision detected",
            self.STATUS_TIMEOUT: "Timeout in communication",
            self.STATUS_NO_ROOM: "Buffer too small",
            self.STATUS_INTERNAL_ERROR: "Internal error",
            self.STATUS_INVALID: "Invalid argument",
            self.STATUS_CRC_WRONG: "CRC_A wrong",
            self.STATUS_MIFARE_NACK: "MIFARE NACK",
        }
        return names.get(status, "Unknown status")

    def _set_status(self, status, message=None):
        self.last_status = status
        self.last_error = message
        return status

    # =========================================================
    # I2C - MESMO MODELO DA BIBLIOTECA ARDUINO
    #
    # WRITE:
    #   [registrador][dados...]
    #
    # READ:
    #   escreve o endereco do registrador
    #   depois faz readfrom()
    # =========================================================

    def _write_reg(self, reg, value):
        self.i2c.writeto(
            self.address,
            bytes((reg & 0xFF, value & 0xFF))
        )

    def _write_regs(self, reg, values):
        data = bytes(values)

        if not data:
            return

        self.i2c.writeto(
            self.address,
            bytes((reg & 0xFF,)) + data
        )

    def _read_reg(self, reg):
        self.i2c.writeto(
            self.address,
            bytes((reg & 0xFF,))
        )

        data = self.i2c.readfrom(
            self.address,
            1
        )

        if not data:
            raise OSError("MFRC522 nao respondeu no I2C")

        return data[0]

    def _read_regs(self, reg, count):
        if count <= 0:
            return b""

        self.i2c.writeto(
            self.address,
            bytes((reg & 0xFF,))
        )

        return bytes(
            self.i2c.readfrom(
                self.address,
                count
            )
        )

    def _set_mask(self, reg, mask):
        self._write_reg(
            reg,
            self._read_reg(reg) | mask
        )

    def _clear_mask(self, reg, mask):
        self._write_reg(
            reg,
            self._read_reg(reg) & (~mask & 0xFF)
        )

    # =========================================================
    # INICIALIZACAO SEM RST FISICO
    # =========================================================

    def init(self):
        self.soft_reset()

        # Mesmos parametros usados na biblioteca MFRC522_I2C
        self._write_reg(self.TModeReg, 0x80)
        self._write_reg(self.TPrescalerReg, 0xA9)
        self._write_reg(self.TReloadRegH, 0x03)
        self._write_reg(self.TReloadRegL, 0xE8)

        self._write_reg(self.TxASKReg, 0x40)
        self._write_reg(self.ModeReg, 0x3D)

        self.antenna_on()

        sleep_ms(10)

        return self.version()

    def soft_reset(self):
        self._write_reg(
            self.CommandReg,
            self.PCD_SoftReset
        )

        sleep_ms(50)

        inicio = ticks_ms()

        while self._read_reg(self.CommandReg) & 0x10:
            if ticks_diff(ticks_ms(), inicio) > 500:
                break

            sleep_ms(1)

    def antenna_on(self):
        value = self._read_reg(self.TxControlReg)

        if (value & 0x03) != 0x03:
            self._write_reg(
                self.TxControlReg,
                value | 0x03
            )

    def antenna_off(self):
        self._clear_mask(
            self.TxControlReg,
            0x03
        )

    def version(self):
        return self._read_reg(self.VersionReg)

    def version_hex(self):
        return "0x%02X" % self.version()

    # =========================================================
    # CRC_A PELO COPROCESSADOR DO MFRC522
    # =========================================================

    def _calculate_crc(self, data):
        self._write_reg(
            self.CommandReg,
            self.PCD_Idle
        )

        self._write_reg(
            self.DivIrqReg,
            0x04
        )

        self._set_mask(
            self.FIFOLevelReg,
            0x80
        )

        self._write_regs(
            self.FIFODataReg,
            data
        )

        self._write_reg(
            self.CommandReg,
            self.PCD_CalcCRC
        )

        inicio = ticks_ms()

        while True:
            n = self._read_reg(self.DivIrqReg)

            if n & 0x04:
                break

            if ticks_diff(ticks_ms(), inicio) > 100:
                return self.STATUS_TIMEOUT, b""

        self._write_reg(
            self.CommandReg,
            self.PCD_Idle
        )

        crc = bytes((
            self._read_reg(self.CRCResultRegL),
            self._read_reg(self.CRCResultRegH),
        ))

        return self.STATUS_OK, crc

    # =========================================================
    # COMUNICACAO COM O CARTAO
    # =========================================================

    def _communicate(
        self,
        command,
        wait_irq,
        send_data,
        max_back_len=0,
        valid_bits=0,
        rx_align=0,
        check_crc=False,
        seed_first=None,
    ):
        tx_last_bits = valid_bits
        bit_framing = ((rx_align & 0x07) << 4) | (tx_last_bits & 0x07)

        self._write_reg(self.CommandReg, self.PCD_Idle)
        self._write_reg(self.ComIrqReg, 0x7F)
        self._set_mask(self.FIFOLevelReg, 0x80)

        self._write_regs(
            self.FIFODataReg,
            send_data
        )

        self._write_reg(
            self.BitFramingReg,
            bit_framing
        )

        self._write_reg(
            self.CommandReg,
            command
        )

        if command == self.PCD_Transceive:
            self._set_mask(
                self.BitFramingReg,
                0x80
            )

        inicio = ticks_ms()
        irq = 0

        while True:
            irq = self._read_reg(self.ComIrqReg)

            if irq & wait_irq:
                break

            if irq & 0x01:
                return (
                    self.STATUS_TIMEOUT,
                    b"",
                    0,
                    0,
                )

            if ticks_diff(ticks_ms(), inicio) > 100:
                return (
                    self.STATUS_TIMEOUT,
                    b"",
                    0,
                    0,
                )

        error_reg = self._read_reg(self.ErrorReg)

        back_data = b""
        rx_valid_bits = 0

        # Diferente da biblioteca antiga, ainda lemos o FIFO mesmo
        # se ErrorReg sinalizar ProtocolErr/ParityErr. Isso permite
        # recuperar um ACK MIFARE valido em alguns modulos I2C.
        if max_back_len:
            n = self._read_reg(self.FIFOLevelReg)

            if n > max_back_len:
                return (
                    self.STATUS_NO_ROOM,
                    b"",
                    0,
                    error_reg,
                )

            if n:
                raw = bytearray(
                    self._read_regs(
                        self.FIFODataReg,
                        n
                    )
                )

                if rx_align and seed_first is not None:
                    mask = 0

                    for i in range(rx_align, 8):
                        mask |= (1 << i)

                    raw[0] = (
                        (seed_first & (~mask & 0xFF))
                        | (raw[0] & mask)
                    )

                back_data = bytes(raw)

            rx_valid_bits = (
                self._read_reg(self.ControlReg)
                & 0x07
            )

        if error_reg & 0x08:
            return (
                self.STATUS_COLLISION,
                back_data,
                rx_valid_bits,
                error_reg,
            )

        if error_reg & 0x13:
            return (
                self.STATUS_ERROR,
                back_data,
                rx_valid_bits,
                error_reg,
            )

        if check_crc and max_back_len:
            if len(back_data) == 1 and rx_valid_bits == 4:
                return (
                    self.STATUS_MIFARE_NACK,
                    back_data,
                    rx_valid_bits,
                    error_reg,
                )

            if len(back_data) < 2 or rx_valid_bits != 0:
                return (
                    self.STATUS_CRC_WRONG,
                    back_data,
                    rx_valid_bits,
                    error_reg,
                )

            status, crc = self._calculate_crc(
                back_data[:-2]
            )

            if status != self.STATUS_OK:
                return (
                    status,
                    back_data,
                    rx_valid_bits,
                    error_reg,
                )

            if crc != back_data[-2:]:
                return (
                    self.STATUS_CRC_WRONG,
                    back_data,
                    rx_valid_bits,
                    error_reg,
                )

        return (
            self.STATUS_OK,
            back_data,
            rx_valid_bits,
            error_reg,
        )

    def _transceive(
        self,
        send_data,
        max_back_len=0,
        valid_bits=0,
        rx_align=0,
        check_crc=False,
        seed_first=None,
    ):
        return self._communicate(
            self.PCD_Transceive,
            0x30,
            send_data,
            max_back_len=max_back_len,
            valid_bits=valid_bits,
            rx_align=rx_align,
            check_crc=check_crc,
            seed_first=seed_first,
        )

    # =========================================================
    # REQA / WUPA
    # =========================================================

    def _request_or_wakeup(self, command):
        self._clear_mask(
            self.CollReg,
            0x80
        )

        status, data, bits, _ = self._transceive(
            bytes((command,)),
            max_back_len=2,
            valid_bits=7,
        )

        if status != self.STATUS_OK:
            return status, b""

        if len(data) != 2 or bits != 0:
            return self.STATUS_ERROR, b""

        return self.STATUS_OK, data

    def request(self):
        return self._request_or_wakeup(
            self.PICC_CMD_REQA
        )

    def wakeup(self):
        return self._request_or_wakeup(
            self.PICC_CMD_WUPA
        )

    def card_present(self):
        status, _ = self.request()

        return (
            status == self.STATUS_OK
            or status == self.STATUS_COLLISION
        )

    # =========================================================
    # ANTICOLISAO / SELECT
    #
    # Suporta UID de 4, 7 e 10 bytes seguindo os tres
    # Cascade Levels da biblioteca Arduino.
    # =========================================================

    def _select(self, known_uid=b"", valid_bits=0):
        if valid_bits > 80:
            return self.STATUS_INVALID, b"", 0

        uid = bytearray(10)

        if known_uid:
            for i, value in enumerate(known_uid[:10]):
                uid[i] = value

        cascade_level = 1
        uid_complete = False
        sak = 0

        self._clear_mask(
            self.CollReg,
            0x80
        )

        while not uid_complete:
            buffer = bytearray(9)

            if cascade_level == 1:
                buffer[0] = self.PICC_CMD_SEL_CL1
                uid_index = 0
                use_cascade_tag = bool(
                    valid_bits and len(known_uid) > 4
                )

            elif cascade_level == 2:
                buffer[0] = self.PICC_CMD_SEL_CL2
                uid_index = 3
                use_cascade_tag = bool(
                    valid_bits and len(known_uid) > 7
                )

            elif cascade_level == 3:
                buffer[0] = self.PICC_CMD_SEL_CL3
                uid_index = 6
                use_cascade_tag = False

            else:
                return (
                    self.STATUS_INTERNAL_ERROR,
                    b"",
                    0,
                )

            current_known_bits = (
                valid_bits - (8 * uid_index)
            )

            if current_known_bits < 0:
                current_known_bits = 0

            index = 2

            if use_cascade_tag:
                buffer[index] = self.PICC_CMD_CT
                index += 1

            bytes_to_copy = (
                current_known_bits // 8
                + (1 if current_known_bits % 8 else 0)
            )

            if bytes_to_copy:
                max_bytes = 3 if use_cascade_tag else 4
                bytes_to_copy = min(
                    bytes_to_copy,
                    max_bytes
                )

                for count in range(bytes_to_copy):
                    buffer[index] = uid[
                        uid_index + count
                    ]
                    index += 1

            if use_cascade_tag:
                current_known_bits += 8

            select_done = False
            response = b""
            rx_valid = 0

            while not select_done:
                if current_known_bits >= 32:
                    buffer[1] = 0x70

                    buffer[6] = (
                        buffer[2]
                        ^ buffer[3]
                        ^ buffer[4]
                        ^ buffer[5]
                    )

                    status, crc = self._calculate_crc(
                        buffer[:7]
                    )

                    if status != self.STATUS_OK:
                        return status, b"", 0

                    buffer[7] = crc[0]
                    buffer[8] = crc[1]

                    tx_last_bits = 0
                    buffer_used = 9
                    response_index = 6
                    response_length = 3

                else:
                    tx_last_bits = (
                        current_known_bits % 8
                    )

                    count = (
                        current_known_bits // 8
                    )

                    index = 2 + count

                    buffer[1] = (
                        (index << 4)
                        + tx_last_bits
                    )

                    buffer_used = (
                        index
                        + (1 if tx_last_bits else 0)
                    )

                    response_index = index
                    response_length = (
                        len(buffer) - index
                    )

                rx_align = tx_last_bits

                seed = (
                    buffer[response_index]
                    if response_index < len(buffer)
                    else None
                )

                status, response, rx_valid, _ = self._transceive(
                    buffer[:buffer_used],
                    max_back_len=response_length,
                    valid_bits=tx_last_bits,
                    rx_align=rx_align,
                    seed_first=seed,
                )

                if response:
                    limite = min(
                        len(response),
                        len(buffer) - response_index
                    )

                    for j in range(limite):
                        buffer[
                            response_index + j
                        ] = response[j]

                if status == self.STATUS_COLLISION:
                    coll_reg = self._read_reg(
                        self.CollReg
                    )

                    if coll_reg & 0x20:
                        return (
                            self.STATUS_COLLISION,
                            b"",
                            0,
                        )

                    collision_pos = (
                        coll_reg & 0x1F
                    )

                    if collision_pos == 0:
                        collision_pos = 32

                    if collision_pos <= current_known_bits:
                        return (
                            self.STATUS_INTERNAL_ERROR,
                            b"",
                            0,
                        )

                    current_known_bits = collision_pos

                    count = (
                        (current_known_bits - 1)
                        % 8
                    )

                    index = (
                        1
                        + (current_known_bits // 8)
                        + (1 if count else 0)
                    )

                    if index < len(buffer):
                        buffer[index] |= (
                            1 << count
                        )

                elif status != self.STATUS_OK:
                    return status, b"", 0

                else:
                    if current_known_bits >= 32:
                        select_done = True
                    else:
                        current_known_bits = 32

            # Copia UID encontrado neste Cascade Level
            source_index = (
                3
                if buffer[2] == self.PICC_CMD_CT
                else 2
            )

            bytes_to_copy = (
                3
                if buffer[2] == self.PICC_CMD_CT
                else 4
            )

            for count in range(bytes_to_copy):
                uid[
                    uid_index + count
                ] = buffer[
                    source_index + count
                ]

            if len(response) != 3 or rx_valid != 0:
                return (
                    self.STATUS_ERROR,
                    b"",
                    0,
                )

            status, crc = self._calculate_crc(
                response[:1]
            )

            if status != self.STATUS_OK:
                return status, b"", 0

            if crc != response[1:3]:
                return (
                    self.STATUS_CRC_WRONG,
                    b"",
                    0,
                )

            if response[0] & 0x04:
                cascade_level += 1
            else:
                uid_complete = True
                sak = response[0]

        uid_size = (
            3 * cascade_level + 1
        )

        result_uid = bytes(
            uid[:uid_size]
        )

        self.uid = result_uid
        self.sak = sak

        return (
            self.STATUS_OK,
            result_uid,
            sak,
        )

    def select(self, wakeup=False):
        if wakeup:
            status, _ = self.wakeup()
        else:
            status, _ = self.request()

        if (
            status != self.STATUS_OK
            and status != self.STATUS_COLLISION
        ):
            self._set_status(status)
            return None

        status, uid, sak = self._select()

        self._set_status(status)

        if status != self.STATUS_OK:
            return None

        self.uid = uid
        self.sak = sak

        return uid

    # =========================================================
    # UID
    # =========================================================

    @staticmethod
    def uid_to_hex(uid, separator=" "):
        if uid is None:
            return None

        return separator.join(
            "%02X" % b
            for b in uid
        )

    def read_uid(self, wakeup=False, halt=True):
        uid = self.select(
            wakeup=wakeup
        )

        if uid is None:
            return None

        if halt:
            self.halt()

        return uid

    # =========================================================
    # AUTENTICACAO MIFARE CLASSIC
    # =========================================================

    def _authenticate(
        self,
        block,
        key=None,
        key_b=False,
    ):
        if not self.uid:
            return self.STATUS_INVALID

        if key is None:
            key = self.DEFAULT_KEY

        key = bytes(key)

        if len(key) != 6:
            return self.STATUS_INVALID

        command = (
            self.PICC_CMD_MF_AUTH_KEY_B
            if key_b
            else self.PICC_CMD_MF_AUTH_KEY_A
        )

        send = bytearray(12)

        send[0] = command
        send[1] = block & 0xFF
        send[2:8] = key

        # A biblioteca Arduino usa os ultimos 4 bytes do UID
        send[8:12] = self.uid[-4:]

        status, _, _, _ = self._communicate(
            self.PCD_MFAuthent,
            0x10,
            send,
        )

        return status

    def stop_crypto1(self):
        self._clear_mask(
            self.Status2Reg,
            0x08
        )

    # =========================================================
    # LEITURA DE BLOCO SELECIONADO
    # =========================================================

    def _read_block_selected(
        self,
        block,
        key=None,
        key_b=False,
    ):
        status = self._authenticate(
            block,
            key=key,
            key_b=key_b,
        )

        if status != self.STATUS_OK:
            self._set_status(
                status,
                "Falha na autenticacao"
            )
            return None

        command = bytearray(4)
        command[0] = self.PICC_CMD_MF_READ
        command[1] = block & 0xFF

        status, crc = self._calculate_crc(
            command[:2]
        )

        if status != self.STATUS_OK:
            self._set_status(status)
            return None

        command[2] = crc[0]
        command[3] = crc[1]

        status, data, _, _ = self._transceive(
            command,
            max_back_len=18,
            check_crc=True,
        )

        self._set_status(status)

        if status != self.STATUS_OK:
            return None

        if len(data) < 18:
            self._set_status(
                self.STATUS_ERROR,
                "Resposta MIFARE_Read incompleta"
            )
            return None

        return bytes(data[:16])

    # =========================================================
    # ACK MIFARE TOLERANTE PARA I2C
    # =========================================================

    def _mifare_transceive(
        self,
        send_data,
        accept_timeout=False,
    ):
        """
        Executa uma etapa MIFARE e valida o ACK.

        IMPORTANTE:
        Nesta versao o ACK nao e mais aceito de forma excessivamente
        tolerante. O ACK MIFARE deve ser uma resposta de 1 byte, com
        4 bits validos e nibble 0xA.

        Mesmo quando esta funcao retorna erro na SEGUNDA etapa de uma
        escrita, o dado pode ter chegado ao cartao. Por isso a API de
        alto nivel sempre faz uma verificacao independente depois.
        """
        if send_data is None or len(send_data) > 16:
            return self.STATUS_INVALID

        status, crc = self._calculate_crc(
            send_data
        )

        if status != self.STATUS_OK:
            return status

        packet = bytes(send_data) + crc

        status, response, valid_bits, error_reg = self._transceive(
            packet,
            max_back_len=18,
        )

        if (
            accept_timeout
            and status == self.STATUS_TIMEOUT
        ):
            return self.STATUS_OK

        # ACK MIFARE valido:
        # exatamente 1 byte, 4 bits validos e nibble 0xA.
        if (
            len(response) == 1
            and valid_bits == 4
            and (response[0] & 0x0F) == self.MF_ACK
        ):
            # Alguns bridges I2C podem deixar ErrorReg marcado mesmo
            # com ACK presente. O ACK real de 4 bits tem prioridade.
            return self.STATUS_OK

        if status != self.STATUS_OK:
            self._log(
                "MIFARE status:",
                status,
                self.status_name(status),
                "ErrorReg=0x%02X" % error_reg,
                "Resposta=",
                response,
                "bits=",
                valid_bits,
            )
            return status

        if (
            len(response) == 1
            and valid_bits == 4
        ):
            return self.STATUS_MIFARE_NACK

        return self.STATUS_ERROR

    def _write_block_selected(
        self,
        block,
        data,
        key=None,
        key_b=False,
    ):
        data = bytes(data)

        if len(data) != 16:
            return self.STATUS_INVALID

        status = self._authenticate(
            block,
            key=key,
            key_b=key_b,
        )

        if status != self.STATUS_OK:
            return status

        # Passo 1: comando WRITE + bloco
        status = self._mifare_transceive(
            bytes((
                self.PICC_CMD_MF_WRITE,
                block & 0xFF,
            ))
        )

        if status != self.STATUS_OK:
            return status

        # Passo 2: 16 bytes
        return self._mifare_transceive(
            data
        )

    # =========================================================
    # HALT / RESELECAO
    # =========================================================

    def halt(self):
        status, crc = self._calculate_crc(
            bytes((
                self.PICC_CMD_HLTA,
                0x00,
            ))
        )

        if status != self.STATUS_OK:
            return status

        packet = bytes((
            self.PICC_CMD_HLTA,
            0x00,
            crc[0],
            crc[1],
        ))

        status, _, _, _ = self._transceive(
            packet
        )

        # Para HLTA o comportamento correto e nao responder,
        # portanto timeout representa sucesso.
        if status == self.STATUS_TIMEOUT:
            return self.STATUS_OK

        if status == self.STATUS_OK:
            return self.STATUS_ERROR

        return status

    def _finish_card(self):
        # Ordem usada pela biblioteca original:
        # HALT primeiro, Crypto1 depois.
        try:
            self.halt()
        finally:
            self.stop_crypto1()

    def _rf_cycle(self, off_ms=40, on_ms=50):
        """
        Reinicia completamente o campo RF.

        Isso remove qualquer estado residual da sessao autenticada e
        obriga o cartao a ser selecionado novamente como uma leitura
        nova. E usado principalmente para validar uma gravacao.
        """
        try:
            self.stop_crypto1()
        except Exception:
            pass

        self.antenna_off()
        sleep_ms(off_ms)

        self.antenna_on()
        sleep_ms(on_ms)

        self.uid = b""
        self.sak = 0

    def _fresh_select_after_write(self):
        """
        Faz uma selecao realmente nova depois da gravacao.

        Diferente da versao anterior, a verificacao nao reutiliza a
        sessao RF anterior. O campo e desligado e ligado novamente.
        """
        self._rf_cycle()

        return self.select(
            wakeup=False
        )

    # =========================================================
    # API DE ALTO NIVEL
    # =========================================================

    def read_block(
        self,
        block=4,
        key=None,
        key_b=False,
        wakeup=False,
    ):
        uid = self.select(
            wakeup=wakeup
        )

        if uid is None:
            return None

        try:
            data = self._read_block_selected(
                block,
                key=key,
                key_b=key_b,
            )

            return data

        finally:
            self._finish_card()

    def read_text(
        self,
        block=4,
        key=None,
        key_b=False,
        wakeup=False,
    ):
        data = self.read_block(
            block=block,
            key=key,
            key_b=key_b,
            wakeup=wakeup,
        )

        if data is None:
            return None

        # Mesmo formato usado no projeto:
        # texto termina no primeiro 0x00.
        end = data.find(b"\x00")

        if end >= 0:
            data = data[:end]

        try:
            return data.decode("utf-8").strip()
        except Exception:
            return "".join(
                chr(b)
                for b in data
                if 32 <= b <= 126
            ).strip()

    def write_block(
        self,
        data,
        block=4,
        key=None,
        key_b=False,
        verify=True,
        retries=3,
        settle_ms=80,
    ):
        """
        Grava exatamente 16 bytes.

        A funcao so retorna True quando a leitura feita DEPOIS de um
        ciclo completo da antena confirma que o bloco realmente ficou
        com os 16 bytes solicitados.

        retries:
            Quantidade maxima de tentativas de gravacao.

        settle_ms:
            Tempo dado ao cartao depois do comando WRITE antes de
            desligar o campo RF. Ajuda principalmente com tags/clones
            mais lentos.
        """
        data = bytes(data)

        if len(data) != 16:
            raise ValueError(
                "write_block exige exatamente 16 bytes"
            )

        retries = max(1, int(retries))
        self.last_verify_data = None
        self.last_write_attempts = 0

        for tentativa in range(1, retries + 1):
            self.last_write_attempts = tentativa

            # Cada tentativa comeca em um estado RF conhecido.
            if tentativa > 1:
                self._rf_cycle()

            uid = self.select()

            if uid is None:
                self._set_status(
                    self.last_status,
                    "Nao foi possivel selecionar o cartao"
                )
                continue

            status = self._write_block_selected(
                block,
                data,
                key=key,
                key_b=key_b,
            )

            self.last_write_status = status

            # Mesmo se o ACK final vier como erro, o dado pode ter
            # chegado ao PICC. Portanto nao declaramos sucesso nem
            # falha aqui; fazemos uma verificacao fisica independente.
            sleep_ms(settle_ms)

            if not verify:
                self._finish_card()
                return status == self.STATUS_OK

            # Verificacao DURAVEL:
            # corta o campo RF, liga novamente e seleciona o cartao
            # do zero. Assim nao aceitamos dados residuais da sessao.
            uid2 = self._fresh_select_after_write()

            if uid2 is None:
                self._set_status(
                    status,
                    "Nao foi possivel selecionar o cartao para verificacao"
                )
                continue

            try:
                leitura = self._read_block_selected(
                    block,
                    key=key,
                    key_b=key_b,
                )

                self.last_verify_data = leitura

                if leitura is not None and leitura == data:
                    self._set_status(
                        self.STATUS_OK
                    )
                    return True

                self._set_status(
                    self.STATUS_ERROR,
                    "Conteudo persistente diferente do solicitado"
                )

            finally:
                self._finish_card()

        return False

    def write_text(
        self,
        text,
        block=4,
        key=None,
        key_b=False,
        verify=True,
        retries=3,
        settle_ms=80,
    ):
        if not isinstance(text, str):
            text = str(text)

        raw = text.encode("utf-8")

        if len(raw) > 15:
            raise ValueError(
                "Texto deve ter no maximo 15 bytes"
            )

        data = raw + (
            b"\x00"
            * (16 - len(raw))
        )

        return self.write_block(
            data,
            block=block,
            key=key,
            key_b=key_b,
            verify=verify,
            retries=retries,
            settle_ms=settle_ms,
        )

    # Alias simples para o projeto
    def read(self, block=4):
        return self.read_text(
            block=block
        )

    def write(
        self,
        text,
        block=4,
        retries=3,
        settle_ms=80,
    ):
        return self.write_text(
            text,
            block=block,
            retries=retries,
            settle_ms=settle_ms,
        )

    # =========================================================
    # LEITURA UNICA ENQUANTO O CARTAO PERMANECE PRESENTE
    # =========================================================

    def _locked_card_still_present(self):
        uid = self.select(
            wakeup=True
        )

        if uid is None:
            return False

        same = (
            self._locked_uid is not None
            and uid == self._locked_uid
        )

        self.halt()

        return same

    def reset_once(self):
        self._locked_uid = None
        self._presence_misses = 0

    def read_once(
        self,
        block=4,
        key=None,
        key_b=False,
    ):
        # Se ja lemos esse cartao, apenas verificamos se ele
        # continua presente. Enquanto estiver presente, retorna None.
        if self._locked_uid is not None:
            if self._locked_card_still_present():
                self._presence_misses = 0
                return None

            self._presence_misses += 1

            if (
                self._presence_misses
                < self._presence_misses_limit
            ):
                return None

            self.reset_once()

        uid = self.select()

        if uid is None:
            return None

        self._locked_uid = bytes(uid)
        self._presence_misses = 0

        try:
            data = self._read_block_selected(
                block,
                key=key,
                key_b=key_b,
            )

            if data is None:
                return None

            end = data.find(b"\x00")

            text_data = (
                data[:end]
                if end >= 0
                else data
            )

            try:
                text = text_data.decode(
                    "utf-8"
                ).strip()
            except Exception:
                text = "".join(
                    chr(b)
                    for b in text_data
                    if 32 <= b <= 126
                ).strip()

            return {
                "uid": bytes(uid),
                "uid_hex": self.uid_to_hex(uid),
                "sak": self.sak,
                "block": block,
                "data": bytes(data),
                "text": text,
            }

        finally:
            self._finish_card()
