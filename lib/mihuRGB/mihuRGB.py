from machine import Pin
import neopixel
import time

try:
    from mihuPinMap import LED_RGB
except ImportError:
    from lib.mihuPinMap import LED_RGB


VERSION = "1.1.0"


# ============================================================
# CONFIGURAÇÃO PADRÃO
# ============================================================

_DEFAULT_TOTAL = 30
_DEFAULT_LEFT_SIZE = 15

# Limite de brilho mantido por segurança elétrica.
# O aluno continua usando brightness entre 0 e 100.
_DEFAULT_MAX_BRIGHTNESS = 60

# Redução adicional quando todos os canais estão em 255.
_WHITE_FACTOR = 0.5


# ============================================================
# ESTADO INTERNO
# ============================================================

_np = None
_total = _DEFAULT_TOTAL
_left_size = _DEFAULT_LEFT_SIZE
_max_brightness = _DEFAULT_MAX_BRIGHTNESS

_available = False
_last_error = None
_started = False


# ============================================================
# FUNÇÕES INTERNAS
# ============================================================

def _clamp(value, minimum, maximum):
    value = int(value)

    if value < minimum:
        return minimum

    if value > maximum:
        return maximum

    return value


def _logical_to_physical(index):
    """
    Mapeamento lógico dos 30 LEDs.

    Índices lógicos:
        0..14  -> lado esquerdo, do centro para fora
        15..29 -> lado direito, do centro para fora

    Mapeamento físico:
        esquerda e direita são invertidas para que as
        animações nasçam no centro da placa.
    """

    index = int(index)

    if index < 0 or index >= _total:
        raise IndexError(
            "LED fora do intervalo: {}. Use 0..{}.".format(
                index,
                _total - 1,
            )
        )

    if index < _left_size:
        return (_left_size - 1) - index

    return (_total - 1) - (index - _left_size)


def _adjust_color(r, g, b, brightness):
    """
    Aplica brilho e proteção de corrente.

    r, g, b:
        0..255

    brightness:
        0..100

    O brilho efetivo é limitado por _max_brightness.
    """

    r = _clamp(r, 0, 255)
    g = _clamp(g, 0, 255)
    b = _clamp(b, 0, 255)

    brightness = _clamp(brightness, 0, 100)
    brightness = min(brightness, _max_brightness)

    scale = brightness / 100.0

    if r == 255 and g == 255 and b == 255:
        scale *= _WHITE_FACTOR

    return (
        int(r * scale),
        int(g * scale),
        int(b * scale),
    )


def _require_available():
    if not _available or _np is None:
        if not rgb._start():
            raise RuntimeError(
                "RGB indisponível: {}".format(
                    _last_error
                )
            )

    return True


def _write():
    _require_available()
    _np.write()


def _set_logical(index, color):
    physical = _logical_to_physical(index)
    _np[physical] = color


# ============================================================
# OBJETO PRINCIPAL
# ============================================================

class MIHURGB:
    """
    Interface simples para os LEDs RGB.

    Uso:
        rgb.left(255, 0, 0, 60)
        rgb.right(0, 0, 255, 60)
        rgb.all(255, 255, 255, 30)
        rgb.range(0, 5, 0, 255, 0, 60)
        rgb.sync(0, 255, 0, 0, 60)
        rgb.clear()
    """

    def __init__(self):
        # Nenhum GPIO ou NeoPixel é criado durante o import.
        pass

    # --------------------------------------------------------
    # Inicialização e configuração
    # --------------------------------------------------------

    def _start(
        self,
        total_leds=None,
        left_size=None,
        max_brightness=None,
        clear=True,
        force=False,
        strict=False,
    ):
        """
        Inicializa o NeoPixel somente quando necessário.
        """

        global _np
        global _total
        global _left_size
        global _max_brightness
        global _available
        global _last_error
        global _started

        if (
            _started
            and _available
            and _np is not None
            and not force
        ):
            return True

        try:
            if total_leds is None:
                total_leds = _total

            if left_size is None:
                left_size = _left_size

            if max_brightness is None:
                max_brightness = _max_brightness

            total_leds = int(total_leds)
            left_size = int(left_size)
            max_brightness = int(max_brightness)

            if total_leds <= 0:
                raise ValueError(
                    "total_leds deve ser maior que zero."
                )

            if (
                left_size <= 0
                or left_size >= total_leds
            ):
                raise ValueError(
                    "left_size deve ficar entre 1 e total_leds - 1."
                )

            _total = total_leds
            _left_size = left_size
            _max_brightness = _clamp(
                max_brightness,
                0,
                100,
            )

            pin = Pin(
                LED_RGB,
                Pin.OUT,
            )

            _np = neopixel.NeoPixel(
                pin,
                _total,
            )

            _available = True
            _started = True
            _last_error = None

            if clear:
                for index in range(_total):
                    _np[index] = (
                        0,
                        0,
                        0,
                    )

                _np.write()

            return True

        except Exception as error:
            _np = None
            _available = False
            _started = False
            _last_error = error

            if strict:
                raise

            return False

    def init(
        self,
        total_leds=_DEFAULT_TOTAL,
        left_size=_DEFAULT_LEFT_SIZE,
        max_brightness=_DEFAULT_MAX_BRIGHTNESS,
        clear=True,
        strict=False,
    ):
        """
        Compatibilidade com versões anteriores.

        Não é necessário chamar init() nos novos programas.
        """

        return self._start(
            total_leds=total_leds,
            left_size=left_size,
            max_brightness=max_brightness,
            clear=clear,
            force=True,
            strict=strict,
        )

    def config(
        self,
        total_leds=None,
        left_size=None,
        max_brightness=None,
    ):
        """
        Consulta ou altera a configuração.

        Consulta:
            print(rgb.config())

        Alteração:
            rgb.config(max_brightness=80)
        """

        global _total
        global _left_size
        global _max_brightness

        if (
            total_leds is None
            and left_size is None
            and max_brightness is None
        ):
            return {
                "total_leds": _total,
                "left_size": _left_size,
                "right_size": _total - _left_size,
                "max_brightness": _max_brightness,
                "available": _available,
            }

        new_total = (
            _total if total_leds is None else int(total_leds)
        )

        new_left = (
            _left_size if left_size is None else int(left_size)
        )

        new_max = (
            _max_brightness
            if max_brightness is None
            else int(max_brightness)
        )

        # Reinicializa somente quando quantidade ou divisão mudarem.
        if new_total != _total or new_left != _left_size:
            if _started:
                self._start(
                    total_leds=new_total,
                    left_size=new_left,
                    max_brightness=new_max,
                    clear=True,
                    force=True,
                )
            else:
                _total = new_total
                _left_size = new_left
                _max_brightness = _clamp(
                    new_max,
                    0,
                    100,
                )

            return self.config()

        _max_brightness = _clamp(new_max, 0, 100)

        return self.config()

    def setConfig(
        self,
        total_leds=None,
        left_size=None,
        max_brightness=None,
    ):
        """
        Alias educacional de config().
        """

        return self.config(
            total_leds=total_leds,
            left_size=left_size,
            max_brightness=max_brightness,
        )

    def available(self):
        return self._start(
            clear=False
        )

    def last_error(self):
        return _last_error

    def lastError(self):
        return _last_error

    def count(self):
        return _total

    def info(self):
        return {
            "library_version": VERSION,
            "started": _started,
            "available": _available,
            "pin": LED_RGB,
            "total_leds": _total,
            "left_size": _left_size,
            "right_size": (
                _total - _left_size
            ),
            "max_brightness": (
                _max_brightness
            ),
            "white_factor": _WHITE_FACTOR,
            "last_error": _last_error,
        }

    def end(self, clear=True):
        """
        Libera o objeto NeoPixel.
        """

        global _np
        global _available
        global _started

        if _np is not None and clear:
            try:
                for index in range(_total):
                    _np[index] = (
                        0,
                        0,
                        0,
                    )

                _np.write()
            except Exception:
                pass

        _np = None
        _available = False
        _started = False
        return True

    deinit = end

    # --------------------------------------------------------
    # Atualização
    # --------------------------------------------------------

    def show(self):
        _write()
        return True

    # --------------------------------------------------------
    # Operações solicitadas
    # --------------------------------------------------------

    def clear(self):
        """Desliga todos os LEDs."""

        _require_available()

        for index in range(_total):
            _np[index] = (0, 0, 0)

        _np.write()
        return True

    def left(self, r, g, b, brightness=60):
        """Define todos os LEDs do lado esquerdo."""

        _require_available()
        color = _adjust_color(r, g, b, brightness)

        for index in range(0, _left_size):
            _set_logical(index, color)

        _np.write()
        return True

    def right(self, r, g, b, brightness=60):
        """Define todos os LEDs do lado direito."""

        _require_available()
        color = _adjust_color(r, g, b, brightness)

        for index in range(_left_size, _total):
            _set_logical(index, color)

        _np.write()
        return True

    def all(self, r, g, b, brightness=60):
        """Define todos os LEDs com a mesma cor."""

        _require_available()
        color = _adjust_color(r, g, b, brightness)

        for index in range(_total):
            _np[index] = color

        _np.write()
        return True

    def range(
        self,
        start,
        end,
        r,
        g,
        b,
        brightness=60,
    ):
        """
        Define um intervalo lógico inclusivo.

        Exemplo:
            rgb.range(0, 5, 255, 0, 0, 60)

        Acende os LEDs 0, 1, 2, 3, 4 e 5.
        """

        _require_available()

        start = int(start)
        end = int(end)

        if start > end:
            start, end = end, start

        start = _clamp(start, 0, _total - 1)
        end = _clamp(end, 0, _total - 1)

        color = _adjust_color(r, g, b, brightness)

        for index in range(start, end + 1):
            _set_logical(index, color)

        _np.write()
        return True

    def sync(self, i, r, g, b, brightness=60):
        """
        Define um par simétrico de LEDs.

        Para uma fita com 30 LEDs:
            i=0  -> par central
            i=1  -> segundo par a partir do centro
            ...
            i=14 -> par das extremidades
        """

        _require_available()

        i = int(i)
        pair_count = min(
            _left_size,
            _total - _left_size,
        )

        if i < 0 or i >= pair_count:
            raise IndexError(
                "sync aceita índices de 0 a {}.".format(
                    pair_count - 1
                )
            )

        left_index = i
        right_index = (_total - 1) - i

        color = _adjust_color(r, g, b, brightness)

        _set_logical(left_index, color)
        _set_logical(right_index, color)

        _np.write()
        return True

    # --------------------------------------------------------
    # Recursos adicionais
    # --------------------------------------------------------

    def set(self, i, r, g, b, brightness=60):
        """Define um único LED lógico."""

        _require_available()
        color = _adjust_color(
            r,
            g,
            b,
            brightness,
        )

        _set_logical(
            int(i),
            color,
        )

        _np.write()
        return True

    def read(self, i):
        """
        Retorna a cor atual de um LED lógico.

        Retorno:
            (vermelho, verde, azul)
        """

        _require_available()

        physical = _logical_to_physical(
            int(i)
        )

        return tuple(
            _np[physical]
        )

    def fill(
        self,
        r,
        g,
        b,
        brightness=60,
    ):
        """
        Alias educacional de all().
        """

        return self.all(
            r,
            g,
            b,
            brightness,
        )

    def off(self, i):
        """Desliga um único LED lógico."""

        return self.set(i, 0, 0, 0, 0)

    def raw(self):
        """Retorna o objeto NeoPixel para uso avançado."""

        _require_available()
        return _np

    def blink(
        self,
        r,
        g,
        b,
        brightness=60,
        times=3,
        interval_ms=200,
    ):
        """
        Pisca todos os LEDs.
        """

        times = max(
            1,
            int(times),
        )

        interval_ms = max(
            0,
            int(interval_ms),
        )

        for _ in range(times):
            self.all(
                r,
                g,
                b,
                brightness,
            )

            time.sleep_ms(
                interval_ms
            )

            self.clear()

            time.sleep_ms(
                interval_ms
            )

        return True

    def chase(
        self,
        r,
        g,
        b,
        brightness=60,
        delay_ms=40,
        clear_after=True,
    ):
        """
        Percorre os LEDs lógicos do centro para as extremidades.
        """

        delay_ms = max(
            0,
            int(delay_ms),
        )

        self.clear()

        for index in range(_total):
            self.set(
                index,
                r,
                g,
                b,
                brightness,
            )

            time.sleep_ms(
                delay_ms
            )

            if clear_after:
                self.off(index)

        return True

    def symmetricChase(
        self,
        r,
        g,
        b,
        brightness=60,
        delay_ms=60,
        clear_after=True,
    ):
        """
        Percorre os pares simétricos do centro para fora.
        """

        pair_count = min(
            _left_size,
            _total - _left_size,
        )

        self.clear()

        for index in range(pair_count):
            self.sync(
                index,
                r,
                g,
                b,
                brightness,
            )

            time.sleep_ms(
                max(
                    0,
                    int(delay_ms),
                )
            )

            if clear_after:
                self.sync(
                    index,
                    0,
                    0,
                    0,
                    0,
                )

        return True

    def progress(
        self,
        value,
        r=0,
        g=255,
        b=0,
        brightness=60,
    ):
        """
        Exibe uma barra de 0 a 100 nos 30 LEDs.
        """

        value = _clamp(
            value,
            0,
            100,
        )

        active = int(
            round(
                value
                * _total
                / 100.0
            )
        )

        _require_available()

        color = _adjust_color(
            r,
            g,
            b,
            brightness,
        )

        for index in range(_total):
            if index < active:
                _set_logical(
                    index,
                    color,
                )
            else:
                _set_logical(
                    index,
                    (
                        0,
                        0,
                        0,
                    ),
                )

        _np.write()
        return active

    def reflectance(
        self,
        value,
        brightness=60,
        smoothing=0.08,
        fade=0.25,
    ):
        """
        Visualização simétrica de refletância entre 0 e 100.
        """

        return refletancia_leds(
            value,
            brilho=brightness,
            suavizacao=smoothing,
            fade_led=fade,
        )

    def ultrasonic(
        self,
        distance_cm,
        brightness=60,
        min_cm=3,
        max_cm=100,
        smoothing=0.12,
        fade=0.3,
    ):
        """
        Visualização do sensor ultrassônico.
        """

        return ultrassonico_leds(
            distance_cm,
            brilho=brightness,
            min_cm=min_cm,
            max_cm=max_cm,
            suavizacao=smoothing,
            fade_led=fade,
        )


# Objeto único usado pelos alunos.
rgb = MIHURGB()


# ============================================================
# COMPATIBILIDADE COM A BIBLIOTECA ANTIGA
# ============================================================

def mihuRGBconfig(
    left_size=15,
    right_start=15,
    max_brightness=None,
):
    # right_start é mantido apenas por compatibilidade.
    del right_start

    return rgb.config(
        left_size=left_size,
        max_brightness=max_brightness,
    )


def mihuRGBclear():
    return rgb.clear()


def mihuRGBset(i, r, g, b, brilho=60):
    return rgb.set(i, r, g, b, brilho)


def mihuRGBleft(r, g, b, brilho=60):
    return rgb.left(r, g, b, brilho)


def mihuRGBright(r, g, b, brilho=60):
    return rgb.right(r, g, b, brilho)


def mihuRGBall(r, g, b, brilho=60):
    return rgb.all(r, g, b, brilho)


def mihuRGBrange(
    start,
    end,
    r,
    g,
    b,
    brilho=60,
):
    return rgb.range(
        start,
        end,
        r,
        g,
        b,
        brilho,
    )


def mihuRGBsym(i, r, g, b, brilho=60):
    return rgb.sync(i, r, g, b, brilho)


# Alias com o nome da nova API.
def mihuRGBsync(i, r, g, b, brilho=60):
    return rgb.sync(i, r, g, b, brilho)


# ============================================================
# VISUALIZAÇÃO DE REFLETÂNCIA
# ============================================================

_refletancia_suave = 0.0
_led_levels = [0.0] * 15


def refletancia_leds(
    valor,
    brilho=60,
    suavizacao=0.08,
    fade_led=0.25,
):
    global _refletancia_suave
    global _led_levels

    valor = _clamp(valor, 0, 100)

    _refletancia_suave += (
        valor - _refletancia_suave
    ) * suavizacao

    pair_count = min(
        _left_size,
        _total - _left_size,
    )

    # Recria o estado caso a quantidade de pares seja alterada.
    if len(_led_levels) != pair_count:
        _led_levels = [0.0] * pair_count

    level = (
        _refletancia_suave / 100.0
    ) * pair_count

    color_values = []

    for i in range(pair_count):
        target = level - i

        if target < 0:
            target = 0

        elif target > 1:
            target = 1

        _led_levels[i] += (
            target - _led_levels[i]
        ) * fade_led

        led_brightness = int(
            brilho * _led_levels[i]
        )

        color_values.append(led_brightness)

    # Atualiza todos os pares antes de enviar para a fita.
    for i in range(pair_count):
        left_index = i
        right_index = (_total - 1) - i

        color = _adjust_color(
            190,
            190,
            190,
            color_values[i],
        )

        _set_logical(left_index, color)
        _set_logical(right_index, color)

    _write()
    return True


# ============================================================
# VISUALIZAÇÃO DO SENSOR ULTRASSÔNICO
# ============================================================

_ultra_suave = 0.0
_ultra_led_levels = [0.0] * 15


def _lerp(a, b, t):
    return int(a + (b - a) * t)


def ultrassonico_leds(
    distancia_cm,
    *,
    brilho=60,
    min_cm=3,
    max_cm=100,
    suavizacao=0.12,
    fade_led=0.3
):
    global _ultra_suave
    global _ultra_led_levels

    if max_cm <= min_cm:
        raise ValueError(
            "max_cm deve ser maior que min_cm."
        )

    if distancia_cm < min_cm:
        distancia_cm = min_cm

    elif distancia_cm > max_cm:
        distancia_cm = max_cm

    normalized = (
        distancia_cm - min_cm
    ) / (max_cm - min_cm)

    normalized = 1.0 - normalized

    _ultra_suave += (
        normalized - _ultra_suave
    ) * suavizacao

    pair_count = min(
        _left_size,
        _total - _left_size,
    )

    if len(_ultra_led_levels) != pair_count:
        _ultra_led_levels = [0.0] * pair_count

    level = _ultra_suave * pair_count

    r = _lerp(255, 0, 1 - _ultra_suave)
    g = _lerp(0, 120, 1 - _ultra_suave)
    b = _lerp(0, 255, 1 - _ultra_suave)

    for i in range(pair_count):
        target = level - i

        if target < 0:
            target = 0

        elif target > 1:
            target = 1

        _ultra_led_levels[i] += (
            target - _ultra_led_levels[i]
        ) * fade_led

        led_brightness = int(
            brilho * _ultra_led_levels[i]
        )

        color = _adjust_color(
            r,
            g,
            b,
            led_brightness,
        )

        left_index = i
        right_index = (_total - 1) - i

        _set_logical(left_index, color)
        _set_logical(right_index, color)

    _write()
    return True
