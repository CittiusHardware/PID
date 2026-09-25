# port.py
# Porta física com hot-plug seguro e acesso serializado.

from machine import Pin
import time

try:
    import _thread
except ImportError:
    _thread = None

from .adc import ADCDetector
from .protocol import EV3UARTSensor
from .constants import (
    UART,
    BOTAO,
    SOM,
    VAZIO,
    INDEFINIDO,
    RESET,
    DATA_MODE,
    BUTTON,
    SOUND,
    EMPTY,
    UNKNOWN,
    UART_TYPE_NAMES,
    UART_SEM_RECURSO,
    LEITURA_TIMEOUT_MS,
    ADC_CONNECTION_STABLE_MS,
    ADC_UART_EMPTY_STABLE_MS,
    UART_TYPE_TIMEOUT_MS,
    UART_INITIAL_RETRY_MAX,
)


class _DummyLock:

    def acquire(self, wait=True):
        return True

    def release(self):
        pass


class MihuSensorPort:

    def __init__(
        self,
        nome,
        gpio_adc=None,
        uart_id=None,
        gpio_rx=None,
        gpio_tx=None,
        detector=None,
        uart_manager=None
    ):

        self.nome = nome
        self.name = nome

        self.gpio_adc = gpio_adc
        self.uart_id = uart_id
        self.gpio_rx = gpio_rx
        self.gpio_tx = gpio_tx
        self.uart_manager = uart_manager

        if detector is None:

            if gpio_adc is None:
                raise ValueError(
                    nome + ": detector ADC nao informado"
                )

            detector = ADCDetector(gpio_adc)

        self.detector = detector

        self.uart_sensor = EV3UARTSensor(
            uart_id=(
                uart_id
                if uart_manager is None
                else None
            ),
            gpio_rx=gpio_rx,
            gpio_tx=gpio_tx
        )

        self.tipo_conexao = INDEFINIDO

        self.pino_botao = None
        self.estado_botao = False

        self.iniciado = False
        self.uart_sem_recurso = False

        # Estado bruto e estado candidato do ADC.
        #
        # A UART só é ativada após o mesmo tipo permanecer
        # estável durante ADC_CONNECTION_STABLE_MS.
        self.tipo_adc_bruto = INDEFINIDO
        self.candidato_adc = INDEFINIDO
        self.candidato_inicio_ms = time.ticks_ms()

        # Confirmação específica de retirada de sensor UART.
        #
        # Enquanto a UART está funcionando, valores baixos
        # intermediários (BOTAO/INDEFINIDO) são ignorados.
        # A UART só é desmontada pelo ADC quando VAZIO fica
        # estável por ADC_UART_EMPTY_STABLE_MS.
        self.uart_vazio_pendente = False
        self.uart_vazio_inicio_ms = time.ticks_ms()

        # Controle da primeira negociação UART.
        #
        # O sensor pode demorar ~2 s apenas para enviar TYPE. Se TYPE
        # não chegar dentro de UART_TYPE_TIMEOUT_MS, a porta faz UMA
        # segunda tentativa em 2400 baud. Não há loop infinito de reset.
        self.uart_initial_retry_count = 0
        self.uart_retry_exhausted = False
        self.uart_ever_ready = False

        if _thread is not None:
            self._lock = _thread.allocate_lock()
        else:
            self._lock = _DummyLock()

    # =================================================
    # ================= TRAVA DA PORTA ==================
    # =================================================

    def _try_lock(self):

        try:
            return self._lock.acquire(False)
        except TypeError:
            # Alguns ports aceitam apenas acquire().
            return self._lock.acquire(0)

    def _lock_blocking(self):

        self._lock.acquire()

    def _unlock(self):

        try:
            self._lock.release()
        except Exception:
            pass

    # =================================================
    # =============== VALIDAÇÃO DO ADC ==================
    # =================================================

    def _iniciar_candidato_adc_unlocked(self, tipo):

        self.candidato_adc = tipo
        self.candidato_inicio_ms = time.ticks_ms()

    def _candidato_adc_estavel_unlocked(self, tipo):

        agora = time.ticks_ms()

        if tipo != self.candidato_adc:

            self._iniciar_candidato_adc_unlocked(
                tipo
            )

            return False

        return (
            time.ticks_diff(
                agora,
                self.candidato_inicio_ms
            ) >= ADC_CONNECTION_STABLE_MS
        )

    def _cancelar_uart_vazio_unlocked(self):

        self.uart_vazio_pendente = False
        self.uart_vazio_inicio_ms = time.ticks_ms()

    def _uart_vazio_estavel_unlocked(self):

        agora = time.ticks_ms()

        if not self.uart_vazio_pendente:

            self.uart_vazio_pendente = True
            self.uart_vazio_inicio_ms = agora

            return False

        return (
            time.ticks_diff(
                agora,
                self.uart_vazio_inicio_ms
            ) >= ADC_UART_EMPTY_STABLE_MS
        )

    # =================================================
    # ============== RECUPERAÇÃO UART INICIAL ===========
    # =================================================

    def _reset_uart_retry_unlocked(self):
        """
        Inicia um novo episódio físico de conexão UART.
        """
        self.uart_initial_retry_count = 0
        self.uart_retry_exhausted = False
        self.uart_ever_ready = False

    def _uart_initial_restart_unlocked(self):
        """
        Executa no máximo UMA segunda tentativa antes do primeiro
        DATA_MODE válido. Mantém a mesma UART física reservada.
        """
        if self.uart_initial_retry_count >= UART_INITIAL_RETRY_MAX:
            self.uart_retry_exhausted = True
            return False

        self.uart_initial_retry_count += 1
        self.uart_retry_exhausted = False
        return bool(self.uart_sensor.begin())

    def _check_pre_type_timeout_unlocked(self):
        """
        Fecha o buraco existente antes do TYPE.

        O protocolo possui timeout para STARTED, mas antes do TYPE ele
        permanece em RESET. Se a UART está aberta, TYPE ainda é -1 e
        esse estado ultrapassa UART_TYPE_TIMEOUT_MS, refazemos apenas
        uma vez a negociação em 2400 baud.
        """
        sensor = self.uart_sensor

        if self.uart_ever_ready or self.uart_sem_recurso:
            return False

        if not sensor.is_uart_enabled():
            return False

        if sensor.get_type() >= 0:
            self.uart_retry_exhausted = False
            return False

        if sensor.get_status() != RESET:
            return False

        inicio = sensor.handshake_start_ms
        if not inicio:
            return False

        agora = time.ticks_ms()
        if time.ticks_diff(agora, inicio) < UART_TYPE_TIMEOUT_MS:
            return False

        if self.uart_initial_retry_count < UART_INITIAL_RETRY_MAX:
            return self._uart_initial_restart_unlocked()

        # Segunda tentativa já foi usada. Continua ouvindo sem novos
        # resets; se um TYPE atrasado chegar, o parser ainda o aceita.
        self.uart_retry_exhausted = True
        return False

    # =================================================
    # ================= GERÊNCIA UART ===================
    # =================================================

    def _reservar_uart_unlocked(self):
        """
        Reserva uma UART física sem alterar o fluxo original
        do protocolo EV3. Se a porta já possui uma vaga, a
        mesma UART é mantida durante a reconexão.
        """

        if self.uart_manager is None:
            uart_id = self.uart_id
        else:
            uart_id = self.uart_manager.request(self)

        if uart_id is None:

            self.uart_sem_recurso = True

            # Garante diagnóstico em 2400 e pinos seguros,
            # mas não ocupa uma quarta UART física.
            self.uart_sensor.mark_disconnected()
            self.uart_sensor.release_uart_id()

            return False

        self.uart_sensor.bind_uart_id(
            uart_id
        )

        self.uart_sem_recurso = False
        return True

    def _liberar_uart_unlocked(self):
        """
        Libera a UART somente após a porta deixar de ser UART.

        Uma perda do protocolo com ADC ainda em UART não passa
        por esta função: nesse caso begin() recomeça em 2400 na
        mesma vaga, exatamente como na biblioteca original.
        """

        self.uart_sensor.mark_disconnected()

        if self.uart_manager is not None:
            self.uart_manager.release(self)

        self.uart_sensor.release_uart_id()
        self.uart_sem_recurso = False

    def _neutralizar_porta_unlocked(self):
        """
        Desativa UART e deixa RX/TX em alta impedância
        enquanto o novo estado elétrico ainda está instável.
        """

        self.tipo_conexao = INDEFINIDO
        self._cancelar_uart_vazio_unlocked()
        self._entrar_analogico_ou_vazio_unlocked()

    # =================================================
    # ================= CONFIGURAÇÃO ====================
    # =================================================

    def _desativar_uart_unlocked(self):

        self._liberar_uart_unlocked()

    def _entrar_uart_unlocked(self):

        self.pino_botao = None
        self._cancelar_uart_vazio_unlocked()

        if not self._reservar_uart_unlocked():
            return False

        # EV3UARTSensor.begin() sempre reinicia em 2400.
        return self.uart_sensor.begin()

    def _entrar_botao_unlocked(self):

        self._desativar_uart_unlocked()

        self.pino_botao = Pin(
            self.gpio_rx,
            Pin.IN,
            Pin.PULL_DOWN
        )

        self.estado_botao = bool(
            self.pino_botao.value()
        )

    def _entrar_analogico_ou_vazio_unlocked(self):

        self._desativar_uart_unlocked()
        self.pino_botao = None

        try:
            Pin(self.gpio_rx, Pin.IN)
        except Exception:
            pass

        try:
            Pin(self.gpio_tx, Pin.IN)
        except Exception:
            pass

    def _aplicar_tipo_unlocked(self, tipo):

        if tipo == UART:
            self._entrar_uart_unlocked()

        elif tipo == BOTAO:
            self._entrar_botao_unlocked()

        else:
            self._entrar_analogico_ou_vazio_unlocked()

    def _begin_unlocked(self):

        _, tipo_adc, _ = self.detector.atualizar(
            forcar=True
        )

        self.tipo_adc_bruto = tipo_adc
        self._iniciar_candidato_adc_unlocked(
            tipo_adc
        )

        # Porta vazia já é um estado eletricamente seguro.
        # Outros tipos precisam ser confirmados antes de
        # ativar UART, pull-down ou qualquer interface.
        if tipo_adc == VAZIO:

            self.tipo_conexao = VAZIO
            self._aplicar_tipo_unlocked(
                VAZIO
            )

        else:

            self.tipo_conexao = INDEFINIDO
            self._entrar_analogico_ou_vazio_unlocked()

        self.iniciado = True

    def begin(self):

        self._lock_blocking()

        try:
            self._begin_unlocked()
        finally:
            self._unlock()

    # =================================================
    # ================= SERVIÇO CONTÍNUO ================
    # =================================================

    def _atualizar_botao_unlocked(self):

        if (
            self.tipo_conexao == BOTAO
            and self.pino_botao is not None
        ):

            self.estado_botao = bool(
                self.pino_botao.value()
            )

    def _service_update_unlocked(self):

        if not self.iniciado:
            self._begin_unlocked()

        # Exatamente uma leitura ADC por atualização.
        _, tipo_adc, _ = self.detector.atualizar(
            forcar=True
        )

        self.tipo_adc_bruto = tipo_adc

        # Mantém o candidato bruto apenas para diagnóstico.
        if tipo_adc != self.candidato_adc:
            self._iniciar_candidato_adc_unlocked(
                tipo_adc
            )

        # =================================================
        # UART ATIVA
        # =================================================

        if self.tipo_conexao == UART:

            # Uma UART válida não deve ser desmontada por
            # leituras intermediárias de 30 a 200.
            #
            # O desligamento elétrico pelo ADC ocorre apenas
            # quando a porta permanece realmente VAZIA.
            if tipo_adc == VAZIO:

                if self._uart_vazio_estavel_unlocked():

                    self.tipo_conexao = VAZIO
                    self._reset_uart_retry_unlocked()

                    # Aqui o ADC confirmou a retirada. Somente
                    # agora a vaga UART é realmente liberada.
                    self._aplicar_tipo_unlocked(
                        VAZIO
                    )

                    self._iniciar_candidato_adc_unlocked(
                        VAZIO
                    )

                else:

                    # Durante a confirmação de VAZIO mantém o
                    # protocolo original ativo, caso o contato
                    # elétrico volte antes do tempo mínimo.
                    if not self.uart_sem_recurso:
                        self.uart_sensor.check()

                return

            # Voltou de um pulso de VAZIO ou continua em uma
            # faixa baixa. Cancela a retirada pendente.
            self._cancelar_uart_vazio_unlocked()

            # Uma quarta porta UART permanece detectada, porém
            # não instancia hardware. Quando surgir uma vaga,
            # ela começa normalmente pelo handshake em 2400.
            if self.uart_sem_recurso:

                if tipo_adc == UART:

                    if self._reservar_uart_unlocked():
                        self.uart_sensor.begin()

                else:

                    self._neutralizar_porta_unlocked()
                    self._iniciar_candidato_adc_unlocked(
                        tipo_adc
                    )

                return

            self.uart_sensor.check()

            # Se já chegou à primeira leitura, futuras perdas de link
            # continuam usando a reconexão automática normal.
            if self.uart_sensor.is_ready():
                self.uart_ever_ready = True
                self.uart_retry_exhausted = False

            # Proteção específica para a fase anterior ao TYPE.
            # Não bloqueia e, no máximo, reinicia uma vez.
            self._check_pre_type_timeout_unlocked()

            if self.uart_sensor.link_lost:

                # A UART confirmada não deve ser desmontada porque a
                # amostra ADC momentânea parece BOTAO/INDEFINIDO. O
                # diagnóstico real mostrou exatamente esse cenário
                # com sensor COLOR funcionando em 57600. A retirada
                # física já é tratada acima somente por VAZIO estável.
                if self.uart_ever_ready:
                    # Sensor já funcionou: reconexão normal, sem limite
                    # de tentativa inicial.
                    self.uart_sensor.begin()

                elif (
                    self.uart_initial_retry_count
                    < UART_INITIAL_RETRY_MAX
                ):
                    # Primeira negociação falhou: só mais uma tentativa.
                    self._uart_initial_restart_unlocked()

                else:
                    # Segunda tentativa falhou. Não entra em loop de
                    # reset. Mantém a reserva até VAZIO confirmar que o
                    # sensor foi retirado.
                    self.uart_retry_exhausted = True

            return

        # =================================================
        # UART DESLIGADA / ESTADO ANALÓGICO
        # =================================================

        self._cancelar_uart_vazio_unlocked()

        # Enquanto um botao ja reconhecido estiver pressionado,
        # o valor do ADC pode sair temporariamente da faixa BOTAO.
        # Mantemos a conexao e lemos o estado pelo RX digital.
        # Ao soltar, o ADC volta a participar normalmente da
        # deteccao automatica e do hot-plug.
        if self.tipo_conexao == BOTAO:
            self._atualizar_botao_unlocked()

            if self.estado_botao:
                return

        # Se botao solto ou som ja estavam configurados e o ADC
        # mudou, volta imediatamente a alta impedancia.
        if (
            self.tipo_conexao not in (
                VAZIO,
                INDEFINIDO
            )
            and tipo_adc != self.tipo_conexao
        ):

            self._neutralizar_porta_unlocked()
            self._iniciar_candidato_adc_unlocked(
                tipo_adc
            )

            return

        # Estado confirmado e ainda igual.
        if (
            tipo_adc == self.tipo_conexao
            and self.tipo_conexao != INDEFINIDO
        ):

            if self.tipo_conexao == BOTAO:
                self._atualizar_botao_unlocked()

            return

        # Conexão de UART, botão ou som só acontece depois
        # da classificação permanecer estável.
        if not self._candidato_adc_estavel_unlocked(
            tipo_adc
        ):

            return

        if tipo_adc != self.tipo_conexao:

            # Uma transição confirmada para UART representa um novo
            # episódio físico. Permite novamente uma única segunda
            # tentativa de negociação.
            if tipo_adc == UART:
                self._reset_uart_retry_unlocked()

            self.tipo_conexao = tipo_adc

            self._aplicar_tipo_unlocked(
                tipo_adc
            )

        if self.tipo_conexao == BOTAO:
            self._atualizar_botao_unlocked()

    def service_update(self):
        """
        Atualização não bloqueante para a thread de serviço.

        Se o código do aluno estiver trocando modo ou lendo
        a mesma porta, esta atualização é simplesmente
        ignorada e será tentada no próximo ciclo.
        """

        if not self._try_lock():
            return

        try:
            self._service_update_unlocked()
        finally:
            self._unlock()

    def update(self):

        self.service_update()

    def wait_connection(
        self,
        tipo_esperado,
        timeout_ms=LEITURA_TIMEOUT_MS
    ):
        """
        Aguarda uma conexão já detectada ou mantém o serviço
        cooperativo até a porta alcançar o tipo esperado.

        Para BOTAO e SOM, retorna assim que a classificação
        ADC estiver confirmada.

        Para UART, aguarda também o handshake e DATA_MODE.
        """

        inicio = time.ticks_ms()

        while True:

            self.service_update()

            if self.tipo_conexao == tipo_esperado:

                if tipo_esperado != UART:
                    return True

                if self.uart_sensor.is_ready():
                    return True

            if time.ticks_diff(
                time.ticks_ms(),
                inicio
            ) >= timeout_ms:

                if (
                    tipo_esperado == UART
                    and self.uart_sem_recurso
                ):

                    raise OSError(
                        self.nome
                        + ": UART detectada, mas as 3 UARTs "
                        + "fisicas estao ocupadas"
                    )

                raise OSError(
                    self.nome
                    + ": conexao nao ficou pronta"
                )

            time.sleep_ms(1)

    # =================================================
    # ================= ESTADO E CACHE ==================
    # =================================================

    def is_uart_ready(self):

        return (
            self.tipo_conexao == UART
            and not self.uart_sem_recurso
            and self.uart_sensor.is_ready()
        )

    def is_ready(self):

        if self.tipo_conexao == UART:
            return self.is_uart_ready()

        return self.tipo_conexao != INDEFINIDO

    def is_uart_waiting_resource(self):

        return (
            self.tipo_conexao == UART
            and self.uart_sem_recurso
        )

    def get_uart_slot(self):
        return self.uart_sensor.get_uart_id()

    def get_adc_source(self):

        if hasattr(self.detector, "get_source"):
            return self.detector.get_source()

        return "ADC_INTERNO"

    def get_adc_channel(self):

        if hasattr(self.detector, "get_channel"):
            return self.detector.get_channel()

        return None

    def get_adc(self):
        """
        Retorna o ADC educacional normalizado em 0..4095.
        """

        return self.detector.get_valor()

    def get_adc_raw(self):
        """
        Retorna a última amostra física do detector.
        """

        if hasattr(
            self.detector,
            "get_raw_value",
        ):
            return self.detector.get_raw_value()

        return self.detector.get_valor()

    def get_adc_filtered_raw(self):
        """
        Retorna a mediana na escala original do detector.
        """

        if hasattr(
            self.detector,
            "get_filtered_raw",
        ):
            return (
                self.detector.get_filtered_raw()
            )

        return self.detector.get_valor()

    def get_adc_classification_value(self):
        """
        Valor usado internamente para classificar a conexão.
        """

        if hasattr(
            self.detector,
            "get_classification_value",
        ):
            return (
                self.detector
                .get_classification_value()
            )

        return self.detector.get_valor()

    def get_adc_data(self):
        if hasattr(
            self.detector,
            "get_data",
        ):
            return self.detector.get_data()

        return {
            "source": self.get_adc_source(),
            "channel": self.get_adc_channel(),
            "gpio": self.gpio_adc,
            "raw": self.get_adc(),
            "filtered": self.get_adc(),
            "classification_value": (
                self.get_adc()
            ),
            "value": self.get_adc(),
            "percent": (
                self.get_adc() * 100
            ) // 4095,
            "type": self.tipo_adc_bruto,
            "valid": True,
            "last_error": None,
        }

    def get_adc_error(self):
        if hasattr(
            self.detector,
            "get_error",
        ):
            return self.detector.get_error()

        return None

    def reset_adc_filter(self):
        if hasattr(
            self.detector,
            "reset_filter",
        ):
            return self.detector.reset_filter()

        return False

    def get_connection_type(self):
        return self.tipo_conexao

    def get_adc_raw_type(self):
        return self.tipo_adc_bruto

    def get_adc_candidate(self):
        return self.candidato_adc

    def get_adc_candidate_ms(self):

        return max(
            0,
            time.ticks_diff(
                time.ticks_ms(),
                self.candidato_inicio_ms
            )
        )

    def is_uart_empty_pending(self):

        return self.uart_vazio_pendente

    def get_uart_empty_candidate_ms(self):

        if not self.uart_vazio_pendente:
            return 0

        return max(
            0,
            time.ticks_diff(
                time.ticks_ms(),
                self.uart_vazio_inicio_ms
            )
        )

    def get_uart_type(self):

        if (
            self.tipo_conexao != UART
            or self.uart_sem_recurso
        ):
            return -1

        return self.uart_sensor.get_type()

    def get_sensor_type(self):

        if self.tipo_conexao == BOTAO:
            return BUTTON

        if self.tipo_conexao == SOM:
            return SOUND

        if self.tipo_conexao == VAZIO:
            return EMPTY

        if self.tipo_conexao != UART:
            return UNKNOWN

        if self.uart_sem_recurso:
            return UART_SEM_RECURSO

        return UART_TYPE_NAMES.get(
            self.uart_sensor.get_type(),
            UNKNOWN
        )

    def get_baud(self):
        return self.uart_sensor.speed

    def is_uart_enabled(self):
        return self.uart_sensor.is_uart_enabled()

    def get_button(self):
        """
        Le o RX digital sem esperar a classificacao do ADC.

        A leitura explicita do aluno e independente do reconhecimento
        automatico. Isso evita timeout quando o ADC muda durante o
        pressionamento do botao.
        """

        self._lock_blocking()

        try:
            # A chamada explicita do aluno assume temporariamente
            # que esta porta contem um botao. Isso separa a leitura
            # digital da classificacao ADC, que pode variar durante
            # o pressionamento. Quando as chamadas cessarem e o botao
            # estiver solto, o servico volta a detectar normalmente.
            if (
                self.tipo_conexao != BOTAO
                or self.pino_botao is None
            ):
                self._desativar_uart_unlocked()
                self.tipo_conexao = BOTAO
                self.pino_botao = Pin(
                    self.gpio_rx,
                    Pin.IN,
                    Pin.PULL_DOWN
                )

            # Evita que a proxima atualizacao execute begin() e
            # apague o modo digital que acabou de ser solicitado.
            self.iniciado = True

            self.estado_botao = bool(
                self.pino_botao.value()
            )

            return self.estado_botao

        finally:
            self._unlock()

    def get_uart_initial_retry_count(self):
        return self.uart_initial_retry_count

    def is_uart_retry_exhausted(self):
        return self.uart_retry_exhausted

    def has_uart_ever_ready(self):
        return self.uart_ever_ready

    # =================================================
    # ================= LEITURA UART ====================
    # =================================================

    def read_uart_mode(
        self,
        tipo_uart_esperado,
        modo,
        timeout_ms=LEITURA_TIMEOUT_MS
    ):
        """
        Leitura serializada.

        No mesmo modo retorna somente o último valor do
        cache. A thread de serviço é responsável por
        receber continuamente os novos quadros.

        Na troca de modo, esta função assume a porta até
        chegar o primeiro quadro do novo modo.
        """

        self._lock_blocking()

        try:

            sensor = self.uart_sensor

            if self.uart_sem_recurso:

                raise OSError(
                    self.nome
                    + ": UART detectada, mas sem recurso livre"
                )

            if not self.is_uart_ready():

                raise OSError(
                    self.nome
                    + ": sensor UART ainda nao esta pronto"
                )

            if sensor.get_type() != tipo_uart_esperado:

                raise ValueError(
                    self.nome
                    + ": tipo UART recebido "
                    + str(sensor.get_type())
                    + ", esperado "
                    + str(tipo_uart_esperado)
                )

            # Mesmo modo: zero acesso concorrente à UART.
            # Retorna o cache já atualizado pela thread.
            if (
                sensor.get_current_mode() == modo
                and sensor.last_data_mode == modo
            ):

                return sensor.get_values()

            contador_anterior = sensor.message_counter
            sensor.set_mode(modo)

            inicio = time.ticks_ms()

            while True:

                self._service_update_unlocked()

                if (
                    self.tipo_conexao != UART
                    or sensor.link_lost
                ):

                    raise OSError(
                        self.nome
                        + ": sensor UART desconectado"
                    )

                if (
                    sensor.get_status() == DATA_MODE
                    and sensor.last_data_mode == modo
                    and sensor.message_counter
                    > contador_anterior
                ):

                    return sensor.get_values()

                if time.ticks_diff(
                    time.ticks_ms(),
                    inicio
                ) >= timeout_ms:

                    raise OSError(
                        self.nome
                        + ": timeout lendo modo "
                        + str(modo)
                    )

        finally:
            self._unlock()

    def reset(self):

        self._lock_blocking()

        try:

            self.tipo_conexao = INDEFINIDO
            self.pino_botao = None
            self.estado_botao = False
            self.iniciado = False

            if hasattr(
                self.detector,
                "reset_filter",
            ):
                self.detector.reset_filter()
            else:
                self.detector.tipo = INDEFINIDO

            self.tipo_adc_bruto = INDEFINIDO
            self.candidato_adc = INDEFINIDO
            self.candidato_inicio_ms = time.ticks_ms()
            self.uart_vazio_pendente = False
            self.uart_vazio_inicio_ms = time.ticks_ms()
            self._reset_uart_retry_unlocked()
            self._liberar_uart_unlocked()

        finally:
            self._unlock()
