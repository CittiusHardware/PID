# uart_manager.py
# Compartilha UART0, UART1 e UART2 entre sete portas.

try:
    import _thread
except ImportError:
    _thread = None

from .constants import MAX_UART_SENSORS


class _DummyLock:

    def acquire(self, wait=True):
        return True

    def release(self):
        pass


class UARTManager:

    def __init__(self, uart_ids=(0, 1, 2)):

        self.uart_ids = tuple(
            uart_ids[:MAX_UART_SENSORS]
        )

        self.owners = {
            uart_id: None
            for uart_id in self.uart_ids
        }

        if _thread is not None:
            self._lock = _thread.allocate_lock()
        else:
            self._lock = _DummyLock()

    def _lock_blocking(self):
        self._lock.acquire()

    def _unlock(self):

        try:
            self._lock.release()
        except Exception:
            pass

    def request(self, porta):
        """
        Mantem a UART ja reservada pela porta.

        P1, P2 e P3 tentam primeiro suas UARTs originais:
            P1 -> UART1
            P2 -> UART2
            P3 -> UART0

        M1-M4 usam qualquer UART fisica livre. Se a UART
        preferencial estiver ocupada, a porta interna tambem
        pode usar outra UART livre.
        """

        self._lock_blocking()

        try:

            # Mantem a reserva atual durante reconexao.
            for uart_id in self.uart_ids:

                if self.owners[uart_id] is porta:
                    return uart_id

            preferencial = getattr(
                porta,
                "uart_id",
                None
            )

            if (
                preferencial in self.owners
                and self.owners[preferencial] is None
            ):

                self.owners[preferencial] = porta
                return preferencial

            # Sem UART preferencial ou preferencial ocupada.
            for uart_id in self.uart_ids:

                if self.owners[uart_id] is None:
                    self.owners[uart_id] = porta
                    return uart_id

            return None

        finally:
            self._unlock()

    def release(self, porta):
        """
        Libera a vaga somente quando a porta confirmou que
        deixou de ser UART, normalmente após ADC=VAZIO.
        """

        self._lock_blocking()

        try:

            for uart_id in self.uart_ids:

                if self.owners[uart_id] is porta:
                    self.owners[uart_id] = None
                    return uart_id

            return None

        finally:
            self._unlock()

    def get_slot(self, porta):

        self._lock_blocking()

        try:

            for uart_id in self.uart_ids:

                if self.owners[uart_id] is porta:
                    return uart_id

            return None

        finally:
            self._unlock()

    def used_count(self):

        self._lock_blocking()

        try:
            return sum(
                1
                for owner in self.owners.values()
                if owner is not None
            )
        finally:
            self._unlock()

    def free_count(self):
        return len(self.uart_ids) - self.used_count()

    def report(self):

        self._lock_blocking()

        try:
            return [
                {
                    "uart_id": uart_id,
                    "porta": (
                        self.owners[uart_id].nome
                        if self.owners[uart_id] is not None
                        else None
                    ),
                }
                for uart_id in self.uart_ids
            ]
        finally:
            self._unlock()
