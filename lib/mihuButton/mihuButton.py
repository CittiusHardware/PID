from machine import ADC, Pin
from time import ticks_ms, ticks_diff
from lib.mihuPinMap import BTN_ANALOG


# ============================================================
# MIHU BUTTON - BIBLIOTECA SIMPLES DE BOTOES ADC
# ============================================================
# Funcoes principais:
#
# raw()        -> valor bruto do ADC
# readName()   -> nome fisico: CIMA, BAIXO, ESQUERDA...
# readKey()    -> tecla logica atual: UP, DOWN, LEFT...
# readFlag()   -> 1 evento por clique, ideal para menus
# read()       -> repeat acelerado, ideal para movimento continuo
# readServo()  -> LEFT/RIGHT com repeat; UP/DOWN/OK/BACK uma vez
# readEvent()  -> ("CLICK", tecla), ("DOUBLE", tecla), ("LONG", tecla)
# readClick()  -> apenas clique simples
# readDouble() -> apenas duplo clique
# readLong()   -> apenas clique longo
# isPressed()  -> verifica se uma tecla esta pressionada
# ============================================================


# ============================================================
# FAIXAS DO ADC -> BOTAO FISICO
# ============================================================
# Ajuste estes valores conforme calibracao da sua placa.
#
# ATENCAO:
# Se o valor SOLTO da placa for perto de 4095,
# a faixa da DIREITA nao pode pegar 4095,
# senao a placa vai entender que RIGHT esta sempre pressionado.

_ADC_MAP = {
    "CIMA":      (550, 640),
    "ESQUERDA": (650, 850),
    "VOLTAR":   (860, 1027),
    "BAIXO":    (1050, 1365),
    "OK":       (1800, 2300),
    "DIREITA":  (4065, 4095),
}


# ============================================================
# BOTAO FISICO -> TECLA LOGICA
# ============================================================

_KEYMAP = {
    "CIMA": "UP",
    "BAIXO": "DOWN",
    "ESQUERDA": "LEFT",
    "DIREITA": "RIGHT",
    "VOLTAR": "BACK",
    "OK": "OK",
}


# ============================================================
# CLASSE PRINCIPAL
# ============================================================

class MihuADCButtons:
    def __init__(
        self,
        pin=BTN_ANALOG,
        *,
        attenuation=ADC.ATTN_11DB,
        release_tol_ms=70,
        first_delay=120,
        repeat_ms=80,
        fast_delay=400,
        faster_delay=900,
        long_press_ms=700,
        double_click_ms=280,
        adc_map=_ADC_MAP,
        keymap=_KEYMAP
    ):
        self.adc = ADC(Pin(pin))
        self.adc.atten(attenuation)

        try:
            self.adc.width(ADC.WIDTH_12BIT)
        except:
            pass

        self.release_tol_ms = int(release_tol_ms)

        self.first_delay = int(first_delay)
        self.repeat_ms = int(repeat_ms)
        self.fast_delay = int(fast_delay)
        self.faster_delay = int(faster_delay)

        self.long_press_ms = int(long_press_ms)
        self.double_click_ms = int(double_click_ms)

        self.adc_map = adc_map
        self.keymap = keymap

        # Estado de repeat
        self._pressed = False
        self._current = None
        self._last_seen = 0
        self._t_down = 0
        self._t_rep = 0

        # Estado de eventos
        self._ev_pressed = False
        self._ev_current = None
        self._ev_last_seen = 0
        self._ev_t_down = 0
        self._ev_long_sent = False

        self._click_waiting = False
        self._click_btn = None
        self._click_time = 0

    # --------------------------------------------------------
    # Leitura bruta
    # --------------------------------------------------------

    def raw(self):
        return self.adc.read()

    # --------------------------------------------------------
    # Nome fisico do botao
    # --------------------------------------------------------

    def read_name(self):
        val = self.raw()

        for name, faixa in self.adc_map.items():
            vmin, vmax = faixa

            if vmin <= val <= vmax:
                return name

        return None

    # --------------------------------------------------------
    # Tecla logica atual, sem repeat
    # --------------------------------------------------------

    def read_key(self):
        name = self.read_name()

        if name is None:
            return None

        return self.keymap.get(name, name)

    # --------------------------------------------------------
    # Repeat com aceleracao
    # --------------------------------------------------------

    def get_repeat_name(self):
        now = ticks_ms()
        btn = self.read_name()

        if btn is not None:
            self._last_seen = now

            if (not self._pressed) or (btn != self._current):
                self._pressed = True
                self._current = btn
                self._t_down = now
                self._t_rep = now
                return btn

            held = ticks_diff(now, self._t_down)

            if held < self.first_delay:
                return None

            if held < self.fast_delay:
                interval = self.repeat_ms
            elif held < self.faster_delay:
                interval = max(20, self.repeat_ms // 2)
            else:
                interval = max(8, self.repeat_ms // 4)

            if ticks_diff(now, self._t_rep) >= interval:
                self._t_rep = now
                return btn

            return None

        if self._pressed and ticks_diff(now, self._last_seen) > self.release_tol_ms:
            self._pressed = False
            self._current = None

        return None

    def get_repeat_key(self):
        name = self.get_repeat_name()

        if name is None:
            return None

        return self.keymap.get(name, name)

    # --------------------------------------------------------
    # Estado pressionado
    # --------------------------------------------------------

    def is_pressed_name(self, name):
        return self._pressed and self._current == name

    def is_pressed_key(self, key):
        if not self._pressed:
            return False

        current_key = self.keymap.get(self._current, self._current)
        return current_key == key

    # --------------------------------------------------------
    # Eventos: CLICK / DOUBLE / LONG
    # --------------------------------------------------------

    def get_event_name(self):
        now = ticks_ms()
        btn = self.read_name()

        if btn is not None:
            self._ev_last_seen = now

            if (not self._ev_pressed) or (btn != self._ev_current):
                self._ev_pressed = True
                self._ev_current = btn
                self._ev_t_down = now
                self._ev_long_sent = False
                return None

            held = ticks_diff(now, self._ev_t_down)

            if (not self._ev_long_sent) and held >= self.long_press_ms:
                self._ev_long_sent = True

                if self._click_waiting and self._click_btn == btn:
                    self._click_waiting = False
                    self._click_btn = None

                return ("LONG", btn)

            return None

        if self._ev_pressed and ticks_diff(now, self._ev_last_seen) > self.release_tol_ms:
            released_btn = self._ev_current
            was_long = self._ev_long_sent

            self._ev_pressed = False
            self._ev_current = None
            self._ev_long_sent = False

            if was_long:
                return None

            if self._click_waiting and self._click_btn == released_btn:
                if ticks_diff(now, self._click_time) <= self.double_click_ms:
                    self._click_waiting = False
                    btn2 = self._click_btn
                    self._click_btn = None
                    return ("DOUBLE", btn2)

            self._click_waiting = True
            self._click_btn = released_btn
            self._click_time = now
            return None

        if self._click_waiting and ticks_diff(now, self._click_time) > self.double_click_ms:
            btn1 = self._click_btn
            self._click_waiting = False
            self._click_btn = None
            return ("CLICK", btn1)

        return None

    def get_event(self):
        ev = self.get_event_name()

        if ev is None:
            return None

        ev_type, btn_name = ev
        return (ev_type, self.keymap.get(btn_name, btn_name))


# ============================================================
# INSTANCIA GLOBAL
# ============================================================

_btn = MihuADCButtons()


# ============================================================
# FUNCOES PUBLICAS
# ============================================================

def raw():
    """
    Retorna o valor bruto do ADC.
    Use para calibracao.
    """
    return _btn.raw()


def readName():
    """
    Retorna o nome fisico do botao:
    CIMA, BAIXO, ESQUERDA, DIREITA, OK, VOLTAR
    ou None.
    """
    return _btn.read_name()


def readKey():
    """
    Retorna a tecla logica atual:
    UP, DOWN, LEFT, RIGHT, OK, BACK
    ou None.

    Esta funcao nao tem trava nem repeat.
    Enquanto segurar, ela continua retornando a tecla.
    """
    return _btn.read_key()


# ------------------------------------------------------------
# 1) MENU - um evento por clique
# ------------------------------------------------------------

_menu_latch = None

def readFlag():
    """
    Ideal para menus.

    Retorna apenas uma vez por pressionamento:
    UP, DOWN, LEFT, RIGHT, OK, BACK
    ou None.
    """
    global _menu_latch

    name = _btn.get_repeat_name()

    if name is None:
        if not _btn._pressed:
            _menu_latch = None
        return None

    if _menu_latch == name and _btn.is_pressed_name(name):
        return None

    _menu_latch = name
    return _btn.keymap.get(name, name)


# ------------------------------------------------------------
# 2) FAST - repeat acelerado livre
# ------------------------------------------------------------

def read():
    """
    Ideal para movimento continuo.

    Retorna com repeticao automatica enquanto o botao estiver segurado.
    A repeticao acelera com o tempo.
    """
    return _btn.get_repeat_key()


# ------------------------------------------------------------
# 3) SERVO - modo misto
# ------------------------------------------------------------

_servo_latch = None
_ONCE_NAMES = {"CIMA", "BAIXO", "OK", "VOLTAR"}

def readServo():
    """
    Ideal para controle de servo/motor.

    UP, DOWN, OK e BACK retornam apenas uma vez por clique.
    LEFT e RIGHT repetem enquanto estiverem pressionados.
    """
    global _servo_latch

    name = _btn.get_repeat_name()

    if name is None:
        if not _btn._pressed:
            _servo_latch = None
        return None

    if name in _ONCE_NAMES:
        if _servo_latch == name and _btn.is_pressed_name(name):
            return None

        _servo_latch = name
        return _btn.keymap.get(name, name)

    return _btn.keymap.get(name, name)


# ------------------------------------------------------------
# 4) EVENTOS
# ------------------------------------------------------------

def readEvent():
    """
    Retorna:
        ("CLICK", "UP")
        ("DOUBLE", "OK")
        ("LONG", "BACK")
    ou None.
    """
    return _btn.get_event()


def readClick():
    """
    Retorna somente a tecla quando houver clique simples.
    Exemplo: OK, UP, BACK.
    """
    ev = _btn.get_event()

    if ev and ev[0] == "CLICK":
        return ev[1]

    return None


def readDouble():
    """
    Retorna somente a tecla quando houver duplo clique.
    """
    ev = _btn.get_event()

    if ev and ev[0] == "DOUBLE":
        return ev[1]

    return None


def readLong():
    """
    Retorna somente a tecla quando houver clique longo.
    """
    ev = _btn.get_event()

    if ev and ev[0] == "LONG":
        return ev[1]

    return None


def isPressed(key):
    """
    Verifica se uma tecla logica esta pressionada.
    Exemplo:
        isPressed("UP")
        isPressed("OK")
    """
    return _btn.is_pressed_key(key)


# ============================================================
# ALIASES OPCIONAIS
# ============================================================
# Mantem compatibilidade com nomes antigos, se algum codigo usar.

read_menu = readFlag
read_fast = read
read_servo = readServo
read_event = readEvent
read_click = readClick
read_double = readDouble
read_long = readLong

