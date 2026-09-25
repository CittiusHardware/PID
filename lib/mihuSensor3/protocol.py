# protocol.py
# Protocolo LEGO EV3 UART com parser totalmente nao bloqueante.
#
# Caracteristicas desta versao:
# - nunca espera bytes dentro de check();
# - nao usa sleep_ms() na recepcao;
# - le todos os bytes ja disponiveis em uma unica chamada;
# - preserva quadros incompletos para a proxima atualizacao;
# - processa varios quadros por chamada sem monopolizar a CPU;
# - preserva hot-plug, heartbeat, retorno para 2400 baud e
#   compartilhamento dinamico de UART0, UART1 e UART2.

from machine import UART, Pin
import time
import struct

from .constants import (
    RESET,
    STARTED,
    DATA_MODE,
    TYPE_COLOR,
    MAX_MODES,
    MAX_DATA_ITEMS,
    HEART_BEAT_MS,
    UART_DATA_TIMEOUT_MS,
    UART_HANDSHAKE_TIMEOUT_MS,
    UART_BAUD_SWITCH_MS,
)

BYTE_ACK = 0x04
BYTE_NACK = 0x02

CMD_SELECT = 0x43
CMD_TYPE = 0x40
CMD_MODES = 0x49
CMD_SPEED = 0x52
CMD_MASK = 0xC0
CMD_INFO = 0x80
CMD_LLL_MASK = 0x38
CMD_LLL_SHIFT = 3
CMD_MMM_MASK = 0x07
CMD_DATA = 0xC0
CMD_WRITE = 0x44

# Limites internos do parser. Nao sao delays de leitura.
# Apenas impedem que uma unica porta monopolize o processador
# caso haja muitos quadros acumulados no buffer da UART.
MAX_RX_BYTES_PER_CHECK = 256
MAX_FRAMES_PER_CHECK = 16
RX_BUFFER_LIMIT = 512

# Um quadro INFO de 34 bytes em 2400 baud leva aproximadamente
# 142 ms para chegar. Por isso, durante o handshake a tolerancia
# para um quadro parcial precisa ser maior.
PARTIAL_TIMEOUT_HANDSHAKE_MS = 250
PARTIAL_TIMEOUT_DATA_MS = 30


class EV3UARTMode:

    def __init__(self):

        self.name = ""
        self.symbol = ""
        self.sets = 1

        # 0=Data8, 1=Data16, 2=Data32, 3=DataF.
        self.data_type = 0

        self.figures = 0
        self.decimals = 0

        self.raw_low = 0.0
        self.raw_high = 0.0

        self.si_low = 0.0
        self.si_high = 0.0

        self.pct_low = 0.0
        self.pct_high = 0.0


class EV3UARTSensor:

    def __init__(
        self,
        uart_id=None,
        gpio_rx=None,
        gpio_tx=None
    ):

        self.uart_id = uart_id
        self.gpio_rx = gpio_rx
        self.gpio_tx = gpio_tx

        self.uart = None
        self.uart_enabled = False

        self.status = RESET
        self.speed = 2400
        self.mode = -1
        self.modes = 0
        self.views = 0
        self.type = -1
        self.num_samples = 1

        self.mode_array = []
        self.value = []

        self.last_nack_ms = 0
        self.last_rx_ms = 0
        self.handshake_start_ms = 0
        self.last_data_ms = 0
        self.last_data_mode = -1

        self.data_errors = 0
        self.consecutive_errors = 0
        self.message_counter = 0

        self.baud_switch_pending = False
        self.baud_switch_at_ms = 0

        self.link_lost = False

        # Buffer persistente do parser nao bloqueante.
        self._rx_buffer = bytearray()
        self._partial_started_ms = time.ticks_ms()

        self._clear_metadata()

    # =================================================
    # ================= UART FISICA =====================
    # =================================================

    def bind_uart_id(self, uart_id):
        """
        Associa uma UART fisica livre a esta porta.

        A associacao nao inicia o protocolo. begin() continua
        sendo responsavel por iniciar sempre em 2400 baud.
        """

        if uart_id is None:
            raise ValueError("uart_id invalido")

        if self.uart_id == uart_id:
            return

        self.deinit()
        self.uart = None
        self.uart_id = uart_id
        self._reset_rx_parser()

    def release_uart_id(self):
        """
        Desassocia a UART somente depois que o ADC confirmou
        que o sensor foi retirado da porta.
        """

        self.deinit()
        self.uart = None
        self.uart_id = None
        self._reset_rx_parser()

    def get_uart_id(self):
        return self.uart_id

    def _init_uart(self, baudrate):

        if self.uart_id is None:
            raise OSError("Nenhuma UART fisica reservada")

        parametros = {
            "baudrate": baudrate,
            "bits": 8,
            "parity": None,
            "stop": 1,
            "rx": Pin(self.gpio_rx),
            "tx": Pin(self.gpio_tx),
            "timeout": 0,
            "timeout_char": 0,
        }

        if self.uart is None:

            self.uart = UART(
                self.uart_id,
                **parametros
            )

        else:

            self.uart.init(
                **parametros
            )

        self.uart_enabled = True

    def deinit(self):
        """
        Desliga a UART e devolve RX/TX para alta impedancia.
        """

        if self.uart is not None:

            try:
                self.uart.deinit()
            except Exception:
                pass

        self.uart_enabled = False

        try:
            Pin(self.gpio_rx, Pin.IN)
        except Exception:
            pass

        try:
            Pin(self.gpio_tx, Pin.IN)
        except Exception:
            pass

    def _clear_uart(self):

        if self.uart is None:
            return

        try:
            quantidade = self.uart.any()

            if quantidade:
                self.uart.read(quantidade)

        except Exception:
            pass

        self._reset_rx_parser()

    # =================================================
    # ============== PARSER NAO BLOQUEANTE =============
    # =================================================

    def _reset_rx_parser(self):

        self._rx_buffer = bytearray()
        self._partial_started_ms = time.ticks_ms()

    def _read_available(self, agora):
        """
        Copia somente os bytes que ja chegaram ao hardware.

        Nunca aguarda um byte futuro e nunca usa sleep_ms().
        """

        if self.uart is None:
            return 0

        try:
            disponivel = self.uart.any()
        except Exception:
            return 0

        if not disponivel:
            return 0

        if disponivel > MAX_RX_BYTES_PER_CHECK:
            disponivel = MAX_RX_BYTES_PER_CHECK

        try:
            recebido = self.uart.read(disponivel)
        except Exception:
            return 0

        if not recebido:
            return 0

        estava_vazio = not self._rx_buffer
        self._rx_buffer.extend(recebido)

        self.last_rx_ms = agora
        self.link_lost = False

        if estava_vazio:
            self._partial_started_ms = agora

        # Protecao contra ruido ou fluxo invalido sem limite.
        if len(self._rx_buffer) > RX_BUFFER_LIMIT:
            self._rx_buffer = self._rx_buffer[-64:]
            self._partial_started_ms = agora

        return len(recebido)

    def _partial_timeout_ms(self):

        if self.status == DATA_MODE:
            return PARTIAL_TIMEOUT_DATA_MS

        return PARTIAL_TIMEOUT_HANDSHAKE_MS

    def _consume_rx(self, quantidade):
        """
        Descarta bytes ja processados sem usar ``del``.

        Algumas versoes do MicroPython nao implementam exclusao
        de itens ou fatias em ``bytearray``. A troca da referencia
        abaixo e compativel com MicroPython e acontece somente
        quando existem bytes efetivamente consumidos.
        """

        if quantidade <= 0:
            return

        tamanho = len(self._rx_buffer)

        if quantidade >= tamanho:
            self._rx_buffer = bytearray()
            return

        self._rx_buffer = bytearray(
            self._rx_buffer[quantidade:]
        )

    def _discard_stale_partial(self, agora):
        """
        Remove um byte de um quadro parcial abandonado.

        Isso apenas recupera sincronismo depois de ruido,
        retirada no meio do quadro ou byte perdido. Nao segura
        a execucao e nao espera o timeout dentro desta funcao.
        """

        if not self._rx_buffer:
            return

        if time.ticks_diff(
            agora,
            self._partial_started_ms
        ) <= self._partial_timeout_ms():
            return

        self._consume_rx(1)
        self._partial_started_ms = agora

    def _expected_frame_length(self, comando):
        """
        Retorna o tamanho total do quadro incluindo comando
        e checksum. Retorna 0 para byte sem formato valido.
        """

        if self.status == DATA_MODE:

            if (comando & CMD_MASK) != CMD_DATA:
                return 0

            lll = (
                comando & CMD_LLL_MASK
            ) >> CMD_LLL_SHIFT

            tamanho = self._exp2(lll)

            if tamanho <= 0:
                return 0

            return 1 + tamanho + 1

        # Durante RESET, somente CMD_TYPE pode iniciar o
        # handshake. Depois disso, em STARTED, os demais
        # quadros de configuracao sao aceitos.
        if comando == CMD_TYPE:
            return 3

        if self.status != STARTED:
            return 0

        if comando == BYTE_ACK:
            return 1

        if comando == CMD_MODES:
            return 4

        if comando == CMD_SPEED:
            return 6

        if (comando & CMD_MASK) == CMD_INFO:

            lll = (
                comando & CMD_LLL_MASK
            ) >> CMD_LLL_SHIFT

            tamanho = self._exp2(lll)

            if tamanho <= 0:
                return 0

            # comando + info_type + payload + checksum
            return 1 + 1 + tamanho + 1

        return 0

    @staticmethod
    def _checksum_ok(quadro):

        checksum = 0xFF

        for byte in quadro[:-1]:
            checksum ^= byte

        return checksum == quadro[-1]

    def _parse_rx_buffer(self, agora):
        """
        Processa apenas quadros completos ja presentes.

        Um quadro incompleto permanece no buffer para a
        proxima chamada de check().
        """

        cursor = 0
        quadros = 0
        tamanho_buffer = len(self._rx_buffer)

        while (
            cursor < tamanho_buffer
            and quadros < MAX_FRAMES_PER_CHECK
            and not self.link_lost
        ):

            comando = self._rx_buffer[cursor]
            tamanho_quadro = self._expected_frame_length(
                comando
            )

            if tamanho_quadro <= 0:
                # Byte fora do protocolo: avanca um byte e
                # procura o proximo cabecalho valido.
                cursor += 1
                continue

            restante = tamanho_buffer - cursor

            if restante < tamanho_quadro:
                break

            quadro = self._rx_buffer[
                cursor:cursor + tamanho_quadro
            ]

            aceito = self._process_frame(
                comando,
                quadro,
                agora
            )

            if aceito:
                cursor += tamanho_quadro
                quadros += 1
            else:
                # Em checksum invalido, avanca apenas um byte
                # para recuperar sincronismo rapidamente.
                cursor += 1

            if self.baud_switch_pending:
                # Bytes restantes pertencem ao baud anterior.
                self._reset_rx_parser()
                return

        if cursor:
            self._consume_rx(cursor)
            self._partial_started_ms = agora

        self._discard_stale_partial(agora)

    def _process_frame(self, comando, quadro, agora):

        if self.status == DATA_MODE:
            return self._process_data_frame(
                comando,
                quadro,
                agora
            )

        return self._process_handshake_frame(
            comando,
            quadro,
            agora
        )

    def _process_data_frame(self, comando, quadro, agora):

        lll = (
            comando & CMD_LLL_MASK
        ) >> CMD_LLL_SHIFT

        tamanho = self._exp2(lll)
        modo_recebido = comando & CMD_MMM_MASK

        if tamanho <= 0:
            return True

        dados = quadro[1:1 + tamanho]

        checksum_ok = self._checksum_ok(quadro)

        # Compatibilidade mantida com o comportamento
        # anterior do sensor de cor no modo 4.
        if (
            self.type == TYPE_COLOR
            and modo_recebido == 4
        ):
            checksum_ok = True

        if not checksum_ok:

            self.data_errors += 1
            self.consecutive_errors += 1

            if self.consecutive_errors > 60:
                self.mark_disconnected()

            return False

        if self._decode_data(
            modo_recebido,
            dados
        ):

            self.consecutive_errors = 0
            self.message_counter += 1
            self.last_data_mode = modo_recebido
            self.last_data_ms = agora

        return True

    def _process_handshake_frame(
        self,
        comando,
        quadro,
        agora
    ):

        if comando == BYTE_ACK:

            try:
                self.uart.write(bytes((BYTE_ACK,)))
            except Exception:
                self.mark_disconnected()
                return True

            self.baud_switch_pending = True
            self.baud_switch_at_ms = time.ticks_add(
                agora,
                UART_BAUD_SWITCH_MS
            )

            return True

        if not self._checksum_ok(quadro):
            return False

        if comando == CMD_TYPE:

            self.type = quadro[1]
            self.status = STARTED
            self.handshake_start_ms = agora
            self.last_rx_ms = agora

            return True

        if comando == CMD_MODES:

            modos = quadro[1]
            vistas = quadro[2]

            self.views = vistas
            self.modes = min(
                modos + 1,
                MAX_MODES
            )

            return True

        if comando == CMD_SPEED:

            velocidade = self._u32_le(
                quadro,
                1
            )

            if velocidade > 0:
                self.speed = velocidade

            return True

        if (comando & CMD_MASK) == CMD_INFO:

            lll = (
                comando & CMD_LLL_MASK
            ) >> CMD_LLL_SHIFT

            tamanho = self._exp2(lll)
            modo = comando & CMD_MMM_MASK

            if (
                tamanho <= 0
                or modo >= MAX_MODES
            ):
                return True

            info_type = quadro[1]
            dados = quadro[2:2 + tamanho]
            objeto = self.mode_array[modo]

            if info_type == 0:

                objeto.name = self._to_str(dados)

            elif (
                info_type == 1
                and len(dados) >= 8
            ):

                objeto.raw_low = self._f32_le(dados, 0)
                objeto.raw_high = self._f32_le(dados, 4)

            elif (
                info_type == 2
                and len(dados) >= 8
            ):

                objeto.pct_low = self._f32_le(dados, 0)
                objeto.pct_high = self._f32_le(dados, 4)

            elif (
                info_type == 3
                and len(dados) >= 8
            ):

                objeto.si_low = self._f32_le(dados, 0)
                objeto.si_high = self._f32_le(dados, 4)

            elif info_type == 4:

                objeto.symbol = self._to_str(dados)

            elif (
                info_type == 0x80
                and len(dados) >= 4
            ):

                objeto.sets = dados[0]
                objeto.data_type = dados[1]
                objeto.figures = dados[2]
                objeto.decimals = dados[3]

            return True

        return True

    # =================================================
    # ================= UTILITARIOS =====================
    # =================================================

    @staticmethod
    def _exp2(valor):

        if 0 <= valor <= 5:
            return 1 << valor

        return 0

    @staticmethod
    def _u32_le(dados, offset=0):

        return (
            dados[offset]
            | (dados[offset + 1] << 8)
            | (dados[offset + 2] << 16)
            | (dados[offset + 3] << 24)
        )

    @staticmethod
    def _i16_le(dados, offset=0):

        valor = (
            dados[offset]
            | (dados[offset + 1] << 8)
        )

        if valor & 0x8000:
            valor -= 0x10000

        return valor

    @staticmethod
    def _f32_le(dados, offset=0):

        return struct.unpack(
            "<f",
            bytes((
                dados[offset],
                dados[offset + 1],
                dados[offset + 2],
                dados[offset + 3]
            ))
        )[0]

    @staticmethod
    def _to_str(dados):

        saida = []

        for byte in dados:

            if byte == 0:
                break

            saida.append(byte)

        try:
            return bytes(saida).decode(
                "ascii",
                "ignore"
            )
        except Exception:
            return ""

    def _clear_metadata(self):

        self.status = RESET
        self.speed = 2400
        self.mode = -1
        self.modes = 0
        self.views = 0
        self.type = -1
        self.num_samples = 1

        self.mode_array = [
            EV3UARTMode()
            for _ in range(MAX_MODES)
        ]

        self.value = [
            0.0
            for _ in range(MAX_DATA_ITEMS)
        ]

        self.last_data_mode = -1

        self.data_errors = 0
        self.consecutive_errors = 0
        self.message_counter = 0

        self.baud_switch_pending = False
        self.baud_switch_at_ms = 0

        self._reset_rx_parser()

    # =================================================
    # ================= CICLO DE VIDA ===================
    # =================================================

    def begin(self):
        """
        Toda conexao e reconexao comeca em 2400 baud.
        """

        self._clear_metadata()

        if self.uart_id is None:
            self.link_lost = True
            return False

        self.link_lost = False

        self._init_uart(2400)
        self._clear_uart()

        agora = time.ticks_ms()

        self.last_nack_ms = agora
        self.last_rx_ms = agora
        self.handshake_start_ms = agora
        self.last_data_ms = agora
        self._partial_started_ms = agora

        return True

    def mark_disconnected(self):
        """
        Perdeu comunicacao: limpa o protocolo, desliga a UART
        e volta a velocidade logica para 2400 baud.

        A reserva da UART fisica nao e liberada aqui. Ela so
        deve ser liberada pelo port.py depois que o ADC confirmar
        que a porta permaneceu VAZIA.
        """

        self.link_lost = True
        self._clear_metadata()
        self.speed = 2400

        self._clear_uart()
        self.deinit()

    def is_uart_enabled(self):
        return self.uart_enabled

    def is_active(self):

        return (
            self.status in (
                STARTED,
                DATA_MODE
            )
            or self.baud_switch_pending
        )

    def is_ready(self):

        return (
            self.status == DATA_MODE
            and self.message_counter > 0
            and self.last_data_mode >= 0
        )

    # =================================================
    # ================= CONSULTAS =======================
    # =================================================

    def get_status(self):
        return self.status

    def get_type(self):
        return self.type

    def get_current_mode(self):
        return self.mode

    def get_number_of_modes(self):
        return self.modes

    def get_mode(self, indice):

        if indice < 0 or indice >= MAX_MODES:
            raise ValueError("Modo fora da faixa")

        return self.mode_array[indice]

    def get_values(self):

        quantidade = max(
            1,
            min(
                self.num_samples,
                MAX_DATA_ITEMS
            )
        )

        return list(
            self.value[:quantidade]
        )

    # =================================================
    # ================= ENVIO ===========================
    # =================================================

    def _send_select(self, modo):

        if (
            self.uart is None
            or not self.uart_enabled
        ):
            raise OSError("UART nao esta ativa")

        checksum = (
            0xFF
            ^ CMD_SELECT
            ^ modo
        )

        self.uart.write(
            bytes((
                CMD_SELECT,
                modo,
                checksum
            ))
        )

    def set_mode(self, modo):

        if modo < 0 or modo >= MAX_MODES:
            raise ValueError("Modo EV3 UART invalido")

        if (
            self.modes > 0
            and modo >= self.modes
        ):
            raise ValueError(
                "Modo nao oferecido pelo sensor"
            )

        self._send_select(modo)

        self.mode = modo

        quantidade = self.mode_array[modo].sets

        if quantidade <= 0:
            quantidade = 1

        self.num_samples = min(
            quantidade,
            MAX_DATA_ITEMS
        )

        self.last_data_mode = -1

        agora = time.ticks_ms()
        self.last_rx_ms = agora
        self.last_data_ms = agora

    def send_write(self, payload_bytes):

        if (
            self.uart is None
            or not self.uart_enabled
        ):
            raise OSError("UART nao esta ativa")

        tamanho_original = len(payload_bytes)

        if tamanho_original <= 0:
            raise ValueError("Payload vazio")

        lll = 0

        while (
            (1 << lll) < tamanho_original
            and lll < 5
        ):
            lll += 1

        tamanho_quadro = 1 << lll

        if tamanho_quadro > 32:
            raise ValueError("Payload maior que 32 bytes")

        payload = bytearray(payload_bytes)

        while len(payload) < tamanho_quadro:
            payload.append(0)

        cabecalho = (
            CMD_WRITE
            | (lll << CMD_LLL_SHIFT)
        )

        checksum = 0xFF ^ cabecalho

        for byte in payload:
            checksum ^= byte

        # Um unico write reduz overhead no driver UART.
        quadro = bytearray(1 + tamanho_quadro + 1)
        quadro[0] = cabecalho
        quadro[1:1 + tamanho_quadro] = payload
        quadro[-1] = checksum

        self.uart.write(quadro)

    # =================================================
    # ================= DECODIFICACAO ===================
    # =================================================

    def _decode_data(self, modo, dados):

        if modo < 0 or modo >= MAX_MODES:
            return False

        tipo_dado = self.mode_array[modo].data_type

        if tipo_dado == 0:
            bytes_por_item = 1
        elif tipo_dado == 1:
            bytes_por_item = 2
        else:
            bytes_por_item = 4

        itens_disponiveis = (
            len(dados) // bytes_por_item
        )

        quantidade = min(
            self.mode_array[modo].sets or 1,
            itens_disponiveis,
            MAX_DATA_ITEMS
        )

        if quantidade <= 0:
            return False

        for indice in range(quantidade):

            offset = indice * bytes_por_item

            if tipo_dado == 0:

                self.value[indice] = float(
                    dados[offset]
                )

            elif tipo_dado == 1:

                self.value[indice] = float(
                    self._i16_le(
                        dados,
                        offset
                    )
                )

            elif tipo_dado == 2:

                valor = self._u32_le(
                    dados,
                    offset
                )

                if valor & 0x80000000:
                    valor -= 0x100000000

                self.value[indice] = float(valor)

            else:

                self.value[indice] = self._f32_le(
                    dados,
                    offset
                )

        self.num_samples = quantidade
        return True

    # =================================================
    # ================= LOOP DO PROTOCOLO ===============
    # =================================================

    def check(self):
        """
        Atualiza a comunicacao sem aguardar nenhum byte.

        O tempo da chamada depende somente da quantidade de
        bytes que ja esta no FIFO da UART, nunca de timeout de
        recepcao ou sleep.
        """

        if (
            self.uart is None
            or not self.uart_enabled
            or self.link_lost
        ):
            return

        agora = time.ticks_ms()

        # Troca de 2400 para a velocidade anunciada pelo sensor.
        # A espera e por estado: check() retorna imediatamente.
        if self.baud_switch_pending:

            if time.ticks_diff(
                agora,
                self.baud_switch_at_ms
            ) < 0:
                return

            self.baud_switch_pending = False
            self._reset_rx_parser()

            try:
                self._init_uart(self.speed)
                self.status = DATA_MODE
                self.set_mode(0)
            except Exception:
                self.mark_disconnected()
                return

            self.last_nack_ms = agora
            self.last_rx_ms = agora
            self.last_data_ms = agora

            self.data_errors = 0
            self.consecutive_errors = 0
            self.message_counter = 0

            return

        if (
            self.status == DATA_MODE
            and time.ticks_diff(
                agora,
                self.last_rx_ms
            ) > UART_DATA_TIMEOUT_MS
        ):
            self.mark_disconnected()
            return

        if (
            self.status == STARTED
            and time.ticks_diff(
                agora,
                self.handshake_start_ms
            ) > UART_HANDSHAKE_TIMEOUT_MS
        ):
            self.mark_disconnected()
            return

        if (
            self.status == DATA_MODE
            and time.ticks_diff(
                agora,
                self.last_nack_ms
            ) > HEART_BEAT_MS
        ):

            try:
                self.uart.write(bytes((BYTE_NACK,)))
                self.last_nack_ms = agora
            except Exception:
                self.mark_disconnected()
                return

        self._read_available(agora)

        if self._rx_buffer:
            self._parse_rx_buffer(agora)
