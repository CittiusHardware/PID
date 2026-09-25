# service.py
# Mantém heartbeat, recepção e hot-plug durante a execução.

import time

from .constants import (
    UART,
    BOOT_DISCOVERY_MS,
    BOOT_TIMEOUT_MS,
)


class SensorService:

    def __init__(self, portas, adc_services=()):

        self.portas = portas
        self.adc_services = tuple(adc_services)
        self.iniciado = False
        self.boot_concluido = False

    def begin(self):

        for adc_service in self.adc_services:
            adc_service.update()

        for porta in self.portas:
            porta.begin()

        self.iniciado = True

    def update(self):

        if not self.iniciado:
            self.begin()

        # O ADS1115 é atualizado antes das portas para que
        # M1-M4 recebam continuamente novas amostras.
        for adc_service in self.adc_services:
            adc_service.update()

        # A ordem também define a prioridade quando uma vaga
        # UART é liberada: P1, P2, P3, M1, M2, M3, M4.
        for porta in self.portas:
            porta.service_update()

    def prepare_boot(
        self,
        discovery_ms=BOOT_DISCOVERY_MS,
        timeout_ms=BOOT_TIMEOUT_MS
    ):
        """
        Executada pelo sistema antes de setupAluno().

        1. Procura sensores durante a janela de boot.
        2. Para as portas UART encontradas, conclui
           handshake, troca de baud, heartbeat e primeira
           leitura do modo 0.
        3. Retorna sem deixar conexão para o aluno fazer.
        """

        if not self.iniciado:
            self.begin()

        inicio = time.ticks_ms()
        fim_descoberta = time.ticks_add(
            inicio,
            discovery_ms
        )
        fim_total = time.ticks_add(
            inicio,
            timeout_ms
        )

        portas_uart_encontradas = []

        while True:

            self.update()

            for porta in self.portas:

                if (
                    porta.get_connection_type() == UART
                    and porta not in portas_uart_encontradas
                ):

                    portas_uart_encontradas.append(porta)

            descoberta_terminou = (
                time.ticks_diff(
                    time.ticks_ms(),
                    fim_descoberta
                ) >= 0
            )

            pendentes = [
                porta
                for porta in portas_uart_encontradas
                if (
                    not porta.is_uart_waiting_resource()
                    and not porta.is_uart_ready()
                )
            ]

            if descoberta_terminou and not pendentes:

                self.boot_concluido = True
                return True

            if time.ticks_diff(
                time.ticks_ms(),
                fim_total
            ) >= 0:

                self.boot_concluido = True
                return False

    def is_ready(self, porta=None):

        if porta is not None:
            return porta.is_ready()

        return all(
            item.is_ready()
            for item in self.portas
        )

    def report(self):

        return [
            {
                "porta": porta.nome,
                "adc": porta.get_adc(),
                "adc_fonte": porta.get_adc_source(),
                "ads_canal": porta.get_adc_channel(),
                "adc_bruto": porta.get_adc_raw_type(),
                "adc_candidato": porta.get_adc_candidate(),
                "adc_candidato_ms": porta.get_adc_candidate_ms(),
                "uart_vazio_pendente": porta.is_uart_empty_pending(),
                "uart_vazio_ms": porta.get_uart_empty_candidate_ms(),
                "conexao": porta.get_connection_type(),
                "sensor": porta.get_sensor_type(),
                "uart_type": porta.get_uart_type(),
                "uart_slot": porta.get_uart_slot(),
                "uart_sem_recurso": porta.is_uart_waiting_resource(),
                "baud": porta.get_baud(),
                "uart_ativa": porta.is_uart_enabled(),
                "pronto": porta.is_ready(),
                "uart_retry_count": porta.get_uart_initial_retry_count(),
                "uart_retry_exhausted": porta.is_uart_retry_exhausted(),
                "uart_ever_ready": porta.has_uart_ever_ready(),
                "modo": porta.uart_sensor.get_current_mode(),
            }
            for porta in self.portas
        ]
