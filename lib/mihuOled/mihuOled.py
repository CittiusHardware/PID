# =========================================================
# lib/mihuOled/mihuOled.py
# Biblioteca unificada MIHU OLED para MicroPython
# Display SSD1306 128x64 I2C + Writer + Fontes + Desenhos + Icones
#
# Uso simples para alunos:
#   from mihuOled import oled
#   oled.text('Ola', 0, 0)        # inicializa automaticamente
#   oled.rect(0, 16, 60, 20)      # atualiza automaticamente
#
# Para desenhar varias coisas sem piscar/lentidao:
#   oled.autoShow(False)
#   oled.clear()
#   oled.text('Tela', 0, 0)
#   oled.rect(0, 16, 100, 20)
#   oled.show()
#   oled.autoShow(True)
# =========================================================

from machine import I2C, Pin
from time import sleep_ms
import framebuf
import os
import sys
import gc

try:
    from math import (
        sqrt,
        sin,
        cos,
        pi,
    )
except Exception:
    sqrt = None
    sin = None
    cos = None
    pi = 3.141592653589793


VERSION = "1.1.0"

_console_print = print

# ---------------------------------------------------------
# Fontes disponiveis no projeto
# Caminho esperado:
#   lib/mihuOled/font/font6.py
#   lib/mihuOled/font/font10.py
#   lib/mihuOled/font/font16b.py
#   lib/mihuOled/font/freesans20.py
#   lib/mihuOled/font/mont12h.py
#   lib/mihuOled/font/mont18h.py
# ---------------------------------------------------------

FONT_6 = "font6"
FONT_10 = "font10"
FONT_16B = "font16b"
FONT_20 = "freesans20"
FONT_MONT_12 = "mont12h"
FONT_MONT_18 = "mont18h"

FONTS = (
    FONT_6,
    FONT_10,
    FONT_16B,
    FONT_20,
    FONT_MONT_12,
    FONT_MONT_18,
)

# ---------------------------------------------------------
# Defaults MIHU S3
# ---------------------------------------------------------

_DEFAULT_SDA = 39
_DEFAULT_SCL = 40
_DEFAULT_I2C_ID = 0
_DEFAULT_FREQ = 400000
_DEFAULT_WIDTH = 128
_DEFAULT_HEIGHT = 64
_DEFAULT_ADDR = 0x3C

# ---------------------------------------------------------
# Importacao robusta do driver SSD1306
# ---------------------------------------------------------

_SSD1306_I2C = None

# Primeiro procura o arquivo da própria pasta mihuOled.
try:
    from .ssd1306 import SSD1306_I2C as _SSD1306_I2C
except Exception:
    pass

if _SSD1306_I2C is None:
    for _name in (
        "mihuOled.ssd1306",
        "lib.mihuOled.ssd1306",
        "ssd1306",
        "lib.ssd1306",
        "oled.ssd1306",
        "lib.oled.ssd1306",
    ):
        try:
            _m = __import__(
                _name,
                None,
                None,
                ("SSD1306_I2C",),
            )

            _SSD1306_I2C = (
                _m.SSD1306_I2C
            )
            break

        except Exception:
            pass

if _SSD1306_I2C is None:
    raise ImportError(
        "mihuOled: nao achei SSD1306_I2C. "
        "Verifique o arquivo ssd1306.py."
    )

# ---------------------------------------------------------
# Importacao opcional do Writer
# ---------------------------------------------------------

_Writer = None

# Primeiro procura o arquivo da própria pasta mihuOled.
try:
    from .writer import Writer as _Writer
except Exception:
    pass

if _Writer is None:
    for _name in (
        "mihuOled.writer",
        "lib.mihuOled.writer",
        "writer",
        "lib.writer",
        "oled.writer",
        "lib.oled.writer",
    ):
        try:
            _m = __import__(
                _name,
                None,
                None,
                ("Writer",),
            )

            _Writer = _m.Writer
            break

        except Exception:
            pass

# ---------------------------------------------------------
# Importacao opcional de Image, caso exista no projeto
# ---------------------------------------------------------

_Image = None

for _name in (
    "lib.mihuOled.image",
    "image",
    "lib.image",
    "oled.image",
    "lib.oled.image",
):
    try:
        _m = __import__(_name)
        if hasattr(_m, "Image"):
            _Image = _m.Image
            break
    except Exception:
        pass

# ---------------------------------------------------------
# Estado interno
# ---------------------------------------------------------

_i2c = None
_oled = None
_writer = None
_font_name = None
_cursor_x = 0
_cursor_y = 0
_auto_show = True
_scroll_x = None
_last_error = None
_text_regions = {}

_ICON_FOLDER_NAME = "icons"

_DEFAULT_ICON_MODULES = (
    "expression_picture",
    "eye_picture",
    "icons_menu",
    "icons_mihu",
    "informatio_picture",
    "object_picture",
    "progres_picture",
)

_icon_module_cache = {}

# =========================================================
# Helpers internos
# =========================================================

def _safe_int(v, default=0):
    try:
        return int(v)
    except Exception:
        return default


def _norm_color(c):
    return 1 if c else 0


def _sync(sync=None):
    if sync is None:
        sync = _auto_show
    if sync:
        show()


def _clamp(v, vmin, vmax):
    if v < vmin:
        return vmin
    if v > vmax:
        return vmax
    return v


def _is_number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _prepare_text_region(key, x, y, w, h, enabled):
    """Limpa a escrita anterior para evitar números borrados."""

    if not enabled:
        return

    previous = _text_regions.get(key)

    if previous is not None:
        _raw_fill_rect(
            previous[0],
            previous[1],
            previous[2],
            previous[3],
            0,
        )

    _text_regions[key] = (
        int(x),
        int(y),
        max(0, int(w)),
        max(0, int(h)),
    )


def _raw_pixel(x, y, c=1):
    oled().pixel(int(x), int(y), _norm_color(c))


def _raw_line(x0, y0, x1, y1, c=1):
    oled().line(int(x0), int(y0), int(x1), int(y1), _norm_color(c))


def _raw_hline(x, y, w, c=1):
    x = int(x)
    y = int(y)
    w = int(w)
    c = _norm_color(c)
    if w < 0:
        x += w
        w = -w
    try:
        oled().hline(x, y, w, c)
    except Exception:
        for i in range(w):
            oled().pixel(x + i, y, c)


def _raw_vline(x, y, h, c=1):
    x = int(x)
    y = int(y)
    h = int(h)
    c = _norm_color(c)
    if h < 0:
        y += h
        h = -h
    try:
        oled().vline(x, y, h, c)
    except Exception:
        for i in range(h):
            oled().pixel(x, y + i, c)


def _raw_rect(x, y, w, h, c=1):
    oled().rect(int(x), int(y), int(w), int(h), _norm_color(c))


def _raw_fill_rect(x, y, w, h, c=1):
    oled().fill_rect(int(x), int(y), int(w), int(h), _norm_color(c))


def _load_font(name):
    name = str(name)
    for mod in (
        name,
        "font." + name,
        "lib.font." + name,
        "lib.mihuOled.font." + name,
        "lib.mihuOled." + name,
        "lib." + name,
        "oled." + name,
        "lib.oled." + name,
    ):
        try:
            return __import__(mod, None, None, ("*",))
        except Exception:
            pass

    raise ImportError("mihuOled: fonte '{}' nao encontrada.".format(name))


def _font_height(font=None):
    if font is None:
        if _font_name is not None:
            try:
                font = _load_font(_font_name)
            except Exception:
                font = None
    if font is not None:
        try:
            return int(font.height())
        except Exception:
            pass
    return 8


def _font_char_width(font=None):
    if font is None:
        if _font_name is not None:
            try:
                font = _load_font(_font_name)
            except Exception:
                font = None
    if font is not None:
        for attr in ("max_width", "width"):
            if hasattr(font, attr):
                try:
                    fn = getattr(font, attr)
                    return int(fn()) if callable(fn) else int(fn)
                except Exception:
                    pass
    return 8


def _font_string_width(font, msg):
    msg = str(msg)
    total = 0
    if font is None:
        return len(msg) * 8
    for ch in msg:
        if ch == "\n":
            continue
        try:
            _, _, cw = font.get_ch(ch)
            total += int(cw)
        except Exception:
            total += _font_char_width(font)
    return total


def _writer_set_textpos(x, y):
    if _Writer is None or _writer is None:
        return False

    xx = _safe_int(x, 0)
    yy = _safe_int(y, 0)

    # writer.py anexado usa set_textpos(col, row): primeiro X, depois Y.
    try:
        _Writer.set_textpos(xx, yy)
        return True
    except Exception:
        pass

    try:
        _writer.set_textpos(xx, yy)
        return True
    except Exception:
        pass

    return False


def _writer_print(msg, invert=False):
    if _Writer is None or _writer is None:
        return False
    try:
        _writer.printstring(str(msg), bool(invert))
        return True
    except TypeError:
        try:
            _writer.printstring(str(msg))
            return True
        except Exception:
            return False
    except Exception:
        return False


def _call_draw(draw_fn, xoff=0):
    try:
        draw_fn(xoff)
        return
    except TypeError:
        pass
    try:
        draw_fn(oled(), xoff)
        return
    except TypeError:
        pass
    try:
        draw_fn(oled())
        return
    except TypeError:
        pass
    draw_fn()

# =========================================================
# Inicializacao / controle do display
# =========================================================

def init(
    i2c=None,
    sda=_DEFAULT_SDA,
    scl=_DEFAULT_SCL,
    i2c_id=_DEFAULT_I2C_ID,
    freq=_DEFAULT_FREQ,
    width=_DEFAULT_WIDTH,
    height=_DEFAULT_HEIGHT,
    addr=_DEFAULT_ADDR,
    clear_screen=True,
    auto_show=True,
    strict=False,
):
    """
    Inicializa o OLED.

    Nos programas dos alunos não é necessário chamar init().
    A primeira operação gráfica inicializa o display.
    """

    global _i2c
    global _oled
    global _writer
    global _font_name
    global _cursor_x
    global _cursor_y
    global _auto_show
    global _last_error

    if _oled is not None:
        return _oled

    try:
        if i2c is None:
            _i2c = I2C(
                int(i2c_id),
                sda=Pin(int(sda)),
                scl=Pin(int(scl)),
                freq=int(freq),
            )
        else:
            _i2c = i2c

        _oled = _SSD1306_I2C(
            int(width),
            int(height),
            _i2c,
            addr=int(addr),
        )

        _writer = None
        _font_name = None
        _cursor_x = 0
        _cursor_y = 0
        _auto_show = bool(auto_show)
        _last_error = None

        if clear_screen:
            _oled.fill(0)
            _oled.show()

        return _oled

    except Exception as error:
        _oled = None
        _last_error = error

        if strict:
            raise

        return None


def oled():
    if _oled is None:
        display = init()

        if display is None:
            raise OSError(
                "OLED indisponivel: {}".format(
                    _last_error
                )
            )

    return _oled


def i2c():
    if _i2c is None:
        init()
    return _i2c


def width():
    return oled().width


def height():
    return oled().height


def size():
    return oled().width, oled().height


def available():
    """
    Inicializa sob demanda e informa se o OLED está disponível.
    """

    if _oled is not None:
        return True

    return init() is not None


def lastError():
    return _last_error


def info():
    return {
        "library_version": VERSION,
        "available": (
            _oled is not None
            or available()
        ),
        "initialized": _oled is not None,
        "width": (
            _oled.width
            if _oled is not None
            else _DEFAULT_WIDTH
        ),
        "height": (
            _oled.height
            if _oled is not None
            else _DEFAULT_HEIGHT
        ),
        "address": _DEFAULT_ADDR,
        "i2c_id": _DEFAULT_I2C_ID,
        "sda": _DEFAULT_SDA,
        "scl": _DEFAULT_SCL,
        "frequency": _DEFAULT_FREQ,
        "auto_show": _auto_show,
        "font": _font_name,
        "last_error": _last_error,
    }


def end(clear_screen=True):
    """
    Desliga e libera o OLED e o I2C criado pela biblioteca.
    """

    global _i2c
    global _oled
    global _writer
    global _font_name
    global _last_error

    if _oled is not None:
        try:
            if clear_screen:
                _oled.fill(0)
                _oled.show()

            _oled.poweroff()

        except Exception:
            pass

    if _i2c is not None:
        try:
            _i2c.deinit()
        except Exception:
            pass

    _i2c = None
    _oled = None
    _writer = None
    _font_name = None
    _last_error = None

    gc.collect()
    return True


deinit = end


def reset():
    """
    Limpa a tela e restaura cursor, fonte e rolagem.
    """

    global _writer
    global _font_name
    global _cursor_x
    global _cursor_y
    global _scroll_x

    _writer = None
    _font_name = None
    _cursor_x = 0
    _cursor_y = 0
    _scroll_x = None

    clear(0)
    return True


def show():
    oled().show()


def update():
    show()


def refresh():
    show()


def auto_show(enable=True):
    global _auto_show
    _auto_show = bool(enable)
    return _auto_show


def autoShow(enable=True):
    return auto_show(enable)


def getAutoShow():
    return _auto_show


def clear(color=0, sync=None):
    _text_regions.clear()
    oled().fill(_norm_color(color))
    _sync(sync)


def fill(color=1, sync=None):
    oled().fill(_norm_color(color))
    _sync(sync)


def clearArea(x, y, w, h, sync=None):
    _raw_fill_rect(x, y, w, h, 0)
    _sync(sync)


def clearLine(y, h=8, sync=None):
    _raw_fill_rect(0, int(y), oled().width, int(h), 0)
    _sync(sync)


def invert(v=True):
    try:
        oled().invert(1 if v else 0)
    except Exception:
        # Fallback direto para SSD1306
        try:
            oled().write_cmd(0xA7 if v else 0xA6)
        except Exception:
            pass


def contrast(value=255):
    value = _clamp(int(value), 0, 255)
    try:
        oled().contrast(value)
    except Exception:
        try:
            oled().write_cmd(0x81)
            oled().write_cmd(value)
        except Exception:
            pass


def powerOff():
    try:
        oled().poweroff()
    except Exception:
        try:
            oled().write_cmd(0xAE)
        except Exception:
            pass


def powerOn():
    try:
        oled().poweron()
    except Exception:
        try:
            oled().write_cmd(0xAF)
        except Exception:
            pass

# =========================================================
# Texto simples e fontes
# =========================================================

def set_font(name=FONT_6):
    global _writer, _font_name, _cursor_x, _cursor_y

    if name is None:
        return set_font_none()

    if _Writer is None:
        raise ImportError("mihuOled: writer.py nao encontrado.")

    font = _load_font(str(name))

    try:
        _writer = _Writer(oled(), font, False)
    except TypeError:
        _writer = _Writer(oled(), font)

    _font_name = str(name)
    _cursor_x = 0
    _cursor_y = 0
    return True


def setFont(name=FONT_6):
    return set_font(name)


def set_font_none():
    global _writer, _font_name, _cursor_x, _cursor_y
    _writer = None
    _font_name = None
    _cursor_x = 0
    _cursor_y = 0
    return True


def setFontNone():
    return set_font_none()


def get_font():
    return _font_name


def getFont():
    return get_font()


def fonts():
    return FONTS


def fontHeight(name=None):
    if name is not None:
        return _font_height(_load_font(name))
    return _font_height()


def stringWidth(msg, font_name=None):
    if font_name is not None:
        return _font_string_width(_load_font(font_name), msg)
    if _font_name is not None:
        try:
            return _font_string_width(_load_font(_font_name), msg)
        except Exception:
            pass
    if _writer is not None:
        try:
            return int(_writer.stringlen(str(msg)))
        except Exception:
            pass
    return len(str(msg)) * 8


def text(msg, x, y, scale=1, color=1, sync=None, clear_previous=None):
    """
    Escreve texto usando a fonte padrão.

    O quarto parâmetro é a escala:
        oled.text("MIHU", 0, 0, 2)

    Quando msg é numérico, a área anterior é limpa para evitar
    sobreposição ao atualizar o valor.
    """

    scale = max(1, int(scale))

    if scale > 1:
        return text_scale(
            msg,
            x,
            y,
            scale=scale,
            color=color,
            sync=sync,
            clear_previous=clear_previous,
        )

    msg_is_number = _is_number(msg)
    msg = str(msg)
    x = int(x)
    y = int(y)
    clear_previous = msg_is_number if clear_previous is None else bool(clear_previous)
    _prepare_text_region(("text", x, y), x, y, len(msg) * 8, 8, clear_previous)
    oled().text(msg, x, y, _norm_color(color))
    _sync(sync)


def center(msg, y=0, scale=1, color=1, font_name=None, invert=False, sync=None, clear_previous=None):
    msg_is_number = _is_number(msg)
    msg = str(msg)
    scale = max(1, int(scale))
    o = oled()

    if scale == 1 and (font_name is not None or _font_name is not None):
        w = stringWidth(msg, font_name)
        x = (o.width - w) // 2
        if x < 0:
            x = 0
        write(msg, x, y, font_name=font_name, invert=invert, sync=sync,
              clear_previous=msg_is_number if clear_previous is None else clear_previous)
        return

    width_px = len(msg) * 8 * scale
    x = (o.width - width_px) // 2
    if x < 0:
        x = 0
    clear_previous = msg_is_number if clear_previous is None else bool(clear_previous)
    _prepare_text_region(("center", int(y)), x, y, width_px, 8 * scale, clear_previous)

    if scale > 1:
        text_scale(msg, x, y, scale=scale, color=color, sync=sync,
                   clear_previous=False)
    else:
        o.text(msg, x, int(y), _norm_color(color))
        _sync(sync)


def write(msg, x=None, y=None, font_name=None, invert=False, clear_first=False,
          sync=None, clear_previous=None):
    global _writer

    msg_is_number = _is_number(msg)

    if clear_first:
        clear(0, sync=False)

    if font_name is not None:
        set_font(font_name)

    if _Writer is None:
        if x is None:
            x = 0
        if y is None:
            y = 0
        oled().text(str(msg), int(x), int(y), 1)
        _sync(sync)
        return

    if _writer is None:
        set_font(FONT_6)

    if x is not None and y is not None:
        _writer_set_textpos(x, y)

        clear_previous = msg_is_number if clear_previous is None else bool(clear_previous)
        _prepare_text_region(
            ("write", int(x), int(y)),
            x,
            y,
            stringWidth(str(msg), font_name),
            _font_height(font_name),
            clear_previous,
        )

    _writer_print(msg, invert=invert)
    _sync(sync)


def textBox(msg, x, y, w, h, color=1, bg=0, border=1, font_name=None, invert=False, sync=None):
    _raw_fill_rect(x, y, w, h, bg)
    if border:
        _raw_rect(x, y, w, h, color)
    tx = int(x) + 2
    ty = int(y) + 2
    write(msg, tx, ty, font_name=font_name, invert=invert, sync=False)
    _sync(sync)


def set_cursor(x=0, y=0):
    global _cursor_x, _cursor_y
    _cursor_x = _safe_int(x, 0)
    _cursor_y = _safe_int(y, 0)


def setCursor(x=0, y=0):
    return set_cursor(x, y)


def print_(msg="", invert=False, sync=None):
    global _cursor_x, _cursor_y

    if _Writer is not None and _writer is not None:
        _writer_set_textpos(_cursor_x, _cursor_y)
        _writer_print(msg, invert=invert)
        _cursor_x += stringWidth(str(msg))
    else:
        oled().text(str(msg), _cursor_x, _cursor_y, 1)
        _cursor_x += len(str(msg)) * 8

    _sync(sync)


def println_(msg="", invert=False, sync=None):
    global _cursor_x, _cursor_y
    print_(msg, invert=invert, sync=False)
    _cursor_x = 0
    _cursor_y += _font_height()
    _sync(sync)


def print(msg=""):
    return print_(msg, invert=False)


def println(msg=""):
    return println_(msg, invert=False)


def printInvert(msg=""):
    return print_(msg, invert=True)


def printlnInvert(msg=""):
    return println_(msg, invert=True)

# =========================================================
# Texto escalado usando fonte padrao 8x8 do FrameBuffer
# =========================================================

def text_scale(msg, x, y, scale=2, color=1, sync=None, clear_previous=None):
    msg_is_number = _is_number(msg)
    msg = str(msg)
    scale = int(scale)
    if scale < 1:
        scale = 1

    src_w = len(msg) * 8
    src_h = 8
    if src_w <= 0:
        return

    stride = (src_w + 7) // 8
    buf = bytearray(stride * src_h)
    fb = framebuf.FrameBuffer(buf, src_w, src_h, framebuf.MONO_HLSB)
    fb.fill(0)
    fb.text(msg, 0, 0, 1)

    xx = int(x)
    yy = int(y)
    c = _norm_color(color)
    clear_previous = msg_is_number if clear_previous is None else bool(clear_previous)
    _prepare_text_region(
        ("text", xx, yy),
        xx,
        yy,
        src_w * scale,
        src_h * scale,
        clear_previous,
    )

    for py in range(src_h):
        for px in range(src_w):
            if fb.pixel(px, py):
                _raw_fill_rect(xx + px * scale, yy + py * scale, scale, scale, c)

    _sync(sync)


def textScale(msg, x, y, scale=2, color=1):
    return text_scale(msg, x, y, scale=scale, color=color)

# =========================================================
# Primitivas de desenho
# =========================================================

def pixel(x, y, c=1, sync=None):
    _raw_pixel(x, y, c)
    _sync(sync)


def line(x0, y0, x1, y1, c=1, sync=None):
    _raw_line(x0, y0, x1, y1, c)
    _sync(sync)


def hline(x, y, w, color=1, sync=None):
    _raw_hline(x, y, w, color)
    _sync(sync)


def vline(x, y, h, color=1, sync=None):
    _raw_vline(x, y, h, color)
    _sync(sync)


def rect(x, y, w, h, c=1, sync=None):
    _raw_rect(x, y, w, h, c)
    _sync(sync)


def fill_rect(x, y, w, h, c=1, sync=None):
    _raw_fill_rect(x, y, w, h, c)
    _sync(sync)


def fillRect(x, y, w, h, c=1):
    return fill_rect(x, y, w, h, c)


def square(x, y, size, c=1, sync=None):
    _raw_rect(x, y, size, size, c)
    _sync(sync)


def fillSquare(x, y, size, c=1, sync=None):
    _raw_fill_rect(x, y, size, size, c)
    _sync(sync)


def circle(x0, y0, r, c=1, sync=None):
    x0 = int(x0)
    y0 = int(y0)
    r = int(r)
    c = _norm_color(c)

    x = r
    y = 0
    err = 0

    while x >= y:
        _raw_pixel(x0 + x, y0 + y, c)
        _raw_pixel(x0 + y, y0 + x, c)
        _raw_pixel(x0 - y, y0 + x, c)
        _raw_pixel(x0 - x, y0 + y, c)
        _raw_pixel(x0 - x, y0 - y, c)
        _raw_pixel(x0 - y, y0 - x, c)
        _raw_pixel(x0 + y, y0 - x, c)
        _raw_pixel(x0 + x, y0 - y, c)

        y += 1
        if err <= 0:
            err += 2 * y + 1
        if err > 0:
            x -= 1
            err -= 2 * x + 1

    _sync(sync)


def fill_circle(x0, y0, r, c=1, sync=None):
    x0 = int(x0)
    y0 = int(y0)
    r = int(r)
    c = _norm_color(c)

    x = r
    y = 0
    err = 0

    while x >= y:
        _raw_hline(x0 - x, y0 + y, 2 * x + 1, c)
        _raw_hline(x0 - x, y0 - y, 2 * x + 1, c)
        _raw_hline(x0 - y, y0 + x, 2 * y + 1, c)
        _raw_hline(x0 - y, y0 - x, 2 * y + 1, c)

        y += 1
        if err <= 0:
            err += 2 * y + 1
        if err > 0:
            x -= 1
            err -= 2 * x + 1

    _sync(sync)


def fillCircle(x0, y0, r, c=1):
    return fill_circle(x0, y0, r, c)


def triangle(x0, y0, x1, y1, x2, y2, c=1, sync=None):
    _raw_line(x0, y0, x1, y1, c)
    _raw_line(x1, y1, x2, y2, c)
    _raw_line(x2, y2, x0, y0, c)
    _sync(sync)


def fill_triangle(x0, y0, x1, y1, x2, y2, c=1, sync=None):
    # Algoritmo simples por caixa delimitadora. Para 128x64 e didatico, atende bem.
    x0 = int(x0); y0 = int(y0)
    x1 = int(x1); y1 = int(y1)
    x2 = int(x2); y2 = int(y2)
    c = _norm_color(c)

    min_x = _clamp(min(x0, x1, x2), 0, oled().width - 1)
    max_x = _clamp(max(x0, x1, x2), 0, oled().width - 1)
    min_y = _clamp(min(y0, y1, y2), 0, oled().height - 1)
    max_y = _clamp(max(y0, y1, y2), 0, oled().height - 1)

    def sign(px, py, ax, ay, bx, by):
        return (px - bx) * (ay - by) - (ax - bx) * (py - by)

    for yy in range(min_y, max_y + 1):
        for xx in range(min_x, max_x + 1):
            b1 = sign(xx, yy, x0, y0, x1, y1) < 0
            b2 = sign(xx, yy, x1, y1, x2, y2) < 0
            b3 = sign(xx, yy, x2, y2, x0, y0) < 0
            if (b1 == b2) and (b2 == b3):
                _raw_pixel(xx, yy, c)

    _sync(sync)


def fillTriangle(x0, y0, x1, y1, x2, y2, c=1):
    return fill_triangle(x0, y0, x1, y1, x2, y2, c)


def round_rect(x, y, w, h, r=3, c=1, sync=None):
    x = int(x); y = int(y); w = int(w); h = int(h); r = int(r)
    if r < 1:
        return rect(x, y, w, h, c, sync=sync)

    _raw_hline(x + r, y, w - 2 * r, c)
    _raw_hline(x + r, y + h - 1, w - 2 * r, c)
    _raw_vline(x, y + r, h - 2 * r, c)
    _raw_vline(x + w - 1, y + r, h - 2 * r, c)

    # cantos aproximados por circulos
    for yy in range(r + 1):
        for xx in range(r + 1):
            if xx * xx + yy * yy <= r * r:
                _raw_pixel(x + r - xx, y + r - yy, c)
                _raw_pixel(x + w - r - 1 + xx, y + r - yy, c)
                _raw_pixel(x + r - xx, y + h - r - 1 + yy, c)
                _raw_pixel(x + w - r - 1 + xx, y + h - r - 1 + yy, c)

    _sync(sync)


def roundRect(x, y, w, h, r=3, c=1):
    return round_rect(x, y, w, h, r, c)


def fill_round_rect(x, y, w, h, r=3, c=1, sync=None):
    x = int(x); y = int(y); w = int(w); h = int(h); r = int(r)
    if r < 1:
        return fill_rect(x, y, w, h, c, sync=sync)

    _raw_fill_rect(x + r, y, w - 2 * r, h, c)
    _raw_fill_rect(x, y + r, r, h - 2 * r, c)
    _raw_fill_rect(x + w - r, y + r, r, h - 2 * r, c)

    for yy in range(r + 1):
        for xx in range(r + 1):
            if xx * xx + yy * yy <= r * r:
                _raw_pixel(x + r - xx, y + r - yy, c)
                _raw_pixel(x + w - r - 1 + xx, y + r - yy, c)
                _raw_pixel(x + r - xx, y + h - r - 1 + yy, c)
                _raw_pixel(x + w - r - 1 + xx, y + h - r - 1 + yy, c)

    _sync(sync)


def fillRoundRect(x, y, w, h, r=3, c=1):
    return fill_round_rect(x, y, w, h, r, c)


def cross(x, y, size=5, c=1, sync=None):
    x = int(x); y = int(y); size = int(size)
    _raw_line(x - size, y - size, x + size, y + size, c)
    _raw_line(x - size, y + size, x + size, y - size, c)
    _sync(sync)


def check(x, y, size=8, c=1, sync=None):
    x = int(x); y = int(y); size = int(size)
    _raw_line(x, y + size // 2, x + size // 3, y + size, c)
    _raw_line(x + size // 3, y + size, x + size, y, c)
    _sync(sync)


def arrowUp(x, y, size=8, c=1, sync=None):
    x = int(x); y = int(y); size = int(size)
    _raw_line(x, y, x - size // 2, y + size, c)
    _raw_line(x, y, x + size // 2, y + size, c)
    _raw_vline(x, y, size + 1, c)
    _sync(sync)


def arrowDown(x, y, size=8, c=1, sync=None):
    x = int(x); y = int(y); size = int(size)
    _raw_line(x, y + size, x - size // 2, y, c)
    _raw_line(x, y + size, x + size // 2, y, c)
    _raw_vline(x, y, size + 1, c)
    _sync(sync)


def arrowLeft(x, y, size=8, c=1, sync=None):
    x = int(x); y = int(y); size = int(size)
    _raw_line(x, y, x + size, y - size // 2, c)
    _raw_line(x, y, x + size, y + size // 2, c)
    _raw_hline(x, y, size + 1, c)
    _sync(sync)


def arrowRight(x, y, size=8, c=1, sync=None):
    x = int(x); y = int(y); size = int(size)
    _raw_line(x + size, y, x, y - size // 2, c)
    _raw_line(x + size, y, x, y + size // 2, c)
    _raw_hline(x, y, size + 1, c)
    _sync(sync)


def point(x, y, c=1, sync=None):
    """Alias didático de pixel()."""

    return pixel(
        x,
        y,
        c,
        sync=sync,
    )


def polyline(
    points,
    c=1,
    closed=False,
    sync=None,
):
    """
    Desenha uma sequência de linhas.

    points:
        ((x0, y0), (x1, y1), ...)
    """

    points = tuple(points)

    if len(points) < 2:
        return False

    for index in range(
        len(points) - 1
    ):
        x0, y0 = points[index]
        x1, y1 = points[index + 1]

        _raw_line(
            x0,
            y0,
            x1,
            y1,
            c,
        )

    if closed:
        x0, y0 = points[-1]
        x1, y1 = points[0]

        _raw_line(
            x0,
            y0,
            x1,
            y1,
            c,
        )

    _sync(sync)
    return True


def polygon(points, c=1, sync=None):
    """Desenha o contorno de um polígono."""

    return polyline(
        points,
        c=c,
        closed=True,
        sync=sync,
    )


def fill_polygon(
    points,
    c=1,
    sync=None,
):
    """
    Preenche um polígono usando linhas horizontais.
    """

    points = tuple(
        (int(x), int(y))
        for x, y in points
    )

    if len(points) < 3:
        return False

    minimum_y = max(
        0,
        min(point[1] for point in points),
    )

    maximum_y = min(
        oled().height - 1,
        max(point[1] for point in points),
    )

    count = len(points)

    for y in range(
        minimum_y,
        maximum_y + 1,
    ):
        intersections = []

        previous = points[-1]

        for current in points:
            x1, y1 = previous
            x2, y2 = current

            if (
                (y1 <= y < y2)
                or (y2 <= y < y1)
            ):
                x = x1 + (
                    (y - y1)
                    * (x2 - x1)
                    // (y2 - y1)
                )

                intersections.append(x)

            previous = current

        intersections.sort()

        for index in range(
            0,
            len(intersections) - 1,
            2,
        ):
            start_x = intersections[index]
            end_x = intersections[index + 1]

            _raw_hline(
                start_x,
                y,
                end_x - start_x + 1,
                c,
            )

    _sync(sync)
    return True


def fillPolygon(points, c=1, sync=None):
    return fill_polygon(
        points,
        c=c,
        sync=sync,
    )


def ellipse(
    x0,
    y0,
    rx,
    ry,
    c=1,
    sync=None,
):
    """
    Desenha uma elipse centrada em x0/y0.
    """

    x0 = int(x0)
    y0 = int(y0)
    rx = abs(int(rx))
    ry = abs(int(ry))
    c = _norm_color(c)

    if rx == 0:
        _raw_vline(
            x0,
            y0 - ry,
            ry * 2 + 1,
            c,
        )
        _sync(sync)
        return True

    if ry == 0:
        _raw_hline(
            x0 - rx,
            y0,
            rx * 2 + 1,
            c,
        )
        _sync(sync)
        return True

    # Parametrização em 1 grau. Para 128x64 é simples e estável.
    if sin is None or cos is None:
        raise RuntimeError(
            "Funcoes matematicas indisponiveis."
        )

    previous = None

    for degree in range(361):
        angle = degree * pi / 180.0

        x = int(
            round(
                x0 + rx * cos(angle)
            )
        )

        y = int(
            round(
                y0 + ry * sin(angle)
            )
        )

        if previous is not None:
            _raw_line(
                previous[0],
                previous[1],
                x,
                y,
                c,
            )

        previous = (x, y)

    _sync(sync)
    return True


def fill_ellipse(
    x0,
    y0,
    rx,
    ry,
    c=1,
    sync=None,
):
    """
    Preenche uma elipse.
    """

    x0 = int(x0)
    y0 = int(y0)
    rx = abs(int(rx))
    ry = abs(int(ry))
    c = _norm_color(c)

    if rx == 0 or ry == 0:
        return ellipse(
            x0,
            y0,
            rx,
            ry,
            c,
            sync=sync,
        )

    rx_squared = rx * rx
    ry_squared = ry * ry
    total = rx_squared * ry_squared

    for offset_y in range(
        -ry,
        ry + 1,
    ):
        remaining = total - (
            offset_y
            * offset_y
            * rx_squared
        )

        if remaining < 0:
            continue

        # Busca inteira adequada ao display pequeno.
        offset_x = rx

        while (
            offset_x > 0
            and offset_x
            * offset_x
            * ry_squared
            > remaining
        ):
            offset_x -= 1

        _raw_hline(
            x0 - offset_x,
            y0 + offset_y,
            offset_x * 2 + 1,
            c,
        )

    _sync(sync)
    return True


def fillEllipse(
    x0,
    y0,
    rx,
    ry,
    c=1,
    sync=None,
):
    return fill_ellipse(
        x0,
        y0,
        rx,
        ry,
        c,
        sync=sync,
    )


def arc(
    x0,
    y0,
    radius,
    start_angle,
    end_angle,
    c=1,
    sync=None,
):
    """
    Desenha um arco em graus.
    """

    if sin is None or cos is None:
        raise RuntimeError(
            "Funcoes matematicas indisponiveis."
        )

    x0 = int(x0)
    y0 = int(y0)
    radius = abs(int(radius))
    start_angle = float(start_angle)
    end_angle = float(end_angle)

    while end_angle < start_angle:
        end_angle += 360.0

    steps = max(
        1,
        int(end_angle - start_angle),
    )

    previous = None

    for index in range(steps + 1):
        angle = (
            start_angle
            + (end_angle - start_angle)
            * index
            / steps
        )

        radians = angle * pi / 180.0

        x = int(
            round(
                x0 + radius * cos(radians)
            )
        )

        y = int(
            round(
                y0 + radius * sin(radians)
            )
        )

        if previous is not None:
            _raw_line(
                previous[0],
                previous[1],
                x,
                y,
                c,
            )

        previous = (x, y)

    _sync(sync)
    return True


def pie(
    x0,
    y0,
    radius,
    start_angle,
    end_angle,
    c=1,
    fill=False,
    sync=None,
):
    """
    Desenha um setor circular.
    """

    if sin is None or cos is None:
        raise RuntimeError(
            "Funcoes matematicas indisponiveis."
        )

    x0 = int(x0)
    y0 = int(y0)
    radius = abs(int(radius))
    start_angle = float(start_angle)
    end_angle = float(end_angle)

    while end_angle < start_angle:
        end_angle += 360.0

    steps = max(
        1,
        int(end_angle - start_angle),
    )

    previous = None
    first = None
    last = None

    for index in range(steps + 1):
        angle = (
            start_angle
            + (end_angle - start_angle)
            * index
            / steps
        )

        radians = angle * pi / 180.0

        point_x = int(
            round(
                x0 + radius * cos(radians)
            )
        )

        point_y = int(
            round(
                y0 + radius * sin(radians)
            )
        )

        point_value = (
            point_x,
            point_y,
        )

        if first is None:
            first = point_value

        last = point_value

        if fill and previous is not None:
            fill_triangle(
                x0,
                y0,
                previous[0],
                previous[1],
                point_x,
                point_y,
                c,
                sync=False,
            )

        elif previous is not None:
            _raw_line(
                previous[0],
                previous[1],
                point_x,
                point_y,
                c,
            )

        previous = point_value

    if first is not None:
        _raw_line(
            x0,
            y0,
            first[0],
            first[1],
            c,
        )

    if last is not None:
        _raw_line(
            x0,
            y0,
            last[0],
            last[1],
            c,
        )

    _sync(sync)
    return True


def bitmap(
    buffer,
    x,
    y,
    w,
    h,
    fmt=framebuf.MONO_HLSB,
    key=-1,
    sync=None,
):
    """
    Desenha um bitmap RAW.
    """

    framebuffer = make_fb(
        buffer,
        w,
        h,
        fmt,
    )

    oled().blit(
        framebuffer,
        int(x),
        int(y),
        int(key),
    )

    _sync(sync)
    return True


def drawBitmap(
    buffer,
    x,
    y,
    w,
    h,
    fmt=framebuf.MONO_HLSB,
    key=-1,
    sync=None,
):
    return bitmap(
        buffer,
        x,
        y,
        w,
        h,
        fmt=fmt,
        key=key,
        sync=sync,
    )


def frame(
    x=0,
    y=0,
    w=None,
    h=None,
    c=1,
    sync=None,
):
    """
    Desenha uma moldura, usando a tela inteira por padrão.
    """

    display = oled()

    if w is None:
        w = display.width - int(x)

    if h is None:
        h = display.height - int(y)

    return rect(
        x,
        y,
        w,
        h,
        c,
        sync=sync,
    )


# =========================================================
# Componentes graficos prontos
# =========================================================

def progressBar(x, y, w, h, value, min_value=0, max_value=100, border=1, sync=None):
    x = int(x); y = int(y); w = int(w); h = int(h)
    value = int(value); min_value = int(min_value); max_value = int(max_value)
    if max_value == min_value:
        pct = 0
    else:
        pct = (value - min_value) * 100 // (max_value - min_value)
    pct = _clamp(pct, 0, 100)

    if border:
        _raw_rect(x, y, w, h, 1)
        inner_x = x + 2
        inner_y = y + 2
        inner_w = w - 4
        inner_h = h - 4
    else:
        inner_x = x
        inner_y = y
        inner_w = w
        inner_h = h

    if inner_w < 1 or inner_h < 1:
        _sync(sync)
        return

    _raw_fill_rect(inner_x, inner_y, inner_w, inner_h, 0)
    fill_w = inner_w * pct // 100
    if fill_w > 0:
        _raw_fill_rect(inner_x, inner_y, fill_w, inner_h, 1)

    _sync(sync)


def battery(x, y, w, h, value=100, sync=None):
    x = int(x); y = int(y); w = int(w); h = int(h)
    value = _clamp(int(value), 0, 100)

    tip_w = 2
    body_w = w - tip_w - 1
    _raw_rect(x, y, body_w, h, 1)
    _raw_fill_rect(x + body_w, y + h // 3, tip_w, h // 3, 1)

    inner_w = body_w - 4
    inner_h = h - 4
    _raw_fill_rect(x + 2, y + 2, inner_w, inner_h, 0)
    fill_w = inner_w * value // 100
    if fill_w > 0:
        _raw_fill_rect(x + 2, y + 2, fill_w, inner_h, 1)

    _sync(sync)


def menu(title, items, selected=0, x=0, y=0, line_h=12, font_name=None, sync=None):
    clear(0, sync=False)
    if title:
        write(str(title), x, y, font_name=font_name, sync=False)
        y += int(line_h)
        _raw_hline(0, y - 2, oled().width, 1)

    selected = int(selected)
    max_lines = (oled().height - y) // int(line_h)
    start = 0
    if selected >= max_lines:
        start = selected - max_lines + 1

    for i in range(start, min(len(items), start + max_lines)):
        yy = y + (i - start) * int(line_h)
        prefix = ">" if i == selected else " "
        write(prefix + str(items[i]), x, yy, font_name=font_name, invert=(i == selected), sync=False)

    _sync(sync)


def splash(title="MIHU", subtitle="OLED", delay_ms=800):
    clear(0, sync=False)
    center(title, 18, font_name=FONT_MONT_18 if _Writer else None, sync=False)
    center(subtitle, 44, font_name=FONT_10 if _Writer else None, sync=False)
    show()
    sleep_ms(delay_ms)

# =========================================================
# FrameBuffer, bitmaps, PBM e icones
# =========================================================

def make_fb(buf, w, h, fmt=framebuf.MONO_HLSB):
    return framebuf.FrameBuffer(buf, int(w), int(h), fmt)


def makeFb(buf, w, h, fmt=framebuf.MONO_HLSB):
    return make_fb(buf, w, h, fmt)


def blit(fb, x, y, key=-1, sync=None):
    oled().blit(fb, int(x), int(y), key)
    _sync(sync)


def _pbm_parse_p4(pbm_bytes):
    i = 0
    n = len(pbm_bytes)

    def read_line():
        nonlocal i
        j = pbm_bytes.find(b"\n", i)
        if j < 0:
            j = n
        line = pbm_bytes[i:j].strip()
        i = j + 1
        return line

    magic = read_line()
    if magic != b"P4":
        raise ValueError("Nao eh PBM P4")

    line = read_line()
    while line.startswith(b"#") or len(line) == 0:
        line = read_line()

    parts = line.split()
    if len(parts) < 2:
        line2 = read_line()
        parts = (line + b" " + line2).split()

    w = int(parts[0])
    h = int(parts[1])
    row_bytes = (w + 7) // 8
    data_len = row_bytes * h
    data = pbm_bytes[i:i + data_len]

    if len(data) < data_len:
        raise ValueError("Dados PBM insuficientes")

    return w, h, data, row_bytes


def draw_pbm(pbm_bytes, x0=0, y0=0, color=1, invert=False, clear_bg=False, sync=None):
    if not isinstance(pbm_bytes, (bytes, bytearray, memoryview)):
        pbm_bytes = bytearray(pbm_bytes)

    b = bytes(pbm_bytes)
    w, h, data, row_bytes = _pbm_parse_p4(b)
    idx = 0

    for y in range(h):
        row = data[idx:idx + row_bytes]
        idx += row_bytes
        for xb, byte in enumerate(row):
            for bit in range(8):
                x = xb * 8 + bit
                if x >= w:
                    break
                on = (byte & (0x80 >> bit)) != 0
                if invert:
                    on = not on
                if on:
                    _raw_pixel(int(x0) + x, int(y0) + y, color)
                elif clear_bg:
                    _raw_pixel(int(x0) + x, int(y0) + y, 0)

    _sync(sync)
    return w, h


def drawPbm(pbm_bytes, x0=0, y0=0, color=1, invert=False, clear_bg=False):
    return draw_pbm(pbm_bytes, x0, y0, color, invert, clear_bg)


def draw_icon(icon_data, x=0, y=0, w=None, h=None, fmt=framebuf.MONO_HLSB, sync=None):
    o = oled()
    xx = int(x)
    yy = int(y)

    # Icone como funcao: aceita func(oled,x,y), func(x,y), func(oled) ou func()
    if callable(icon_data):
        old_auto = _auto_show
        need_sync = old_auto if sync is None else bool(sync)
        auto_show(False)
        ok = False
        try:
            for args in ((o, xx, yy), (xx, yy), (o,), ()):
                try:
                    icon_data(*args)
                    ok = True
                    break
                except TypeError:
                    pass
        finally:
            auto_show(old_auto)

        if ok:
            if need_sync:
                show()
            return True

        raise TypeError("Icone callable com assinatura nao suportada.")

    # Objeto com buffer, width e height
    if hasattr(icon_data, "buffer") and hasattr(icon_data, "width") and hasattr(icon_data, "height"):
        fb = make_fb(icon_data.buffer, icon_data.width, icon_data.height, fmt)
        o.blit(fb, xx, yy, -1)
        _sync(sync)
        return True

    # FrameBuffer
    try:
        if isinstance(icon_data, framebuf.FrameBuffer):
            o.blit(icon_data, xx, yy, -1)
            _sync(sync)
            return True
    except Exception:
        pass

    # Bytes / bytearray / memoryview
    if isinstance(icon_data, (bytes, bytearray, memoryview)):
        b = bytes(icon_data)

        # PBM P4
        if len(b) >= 2 and b[0:2] == b"P4":
            draw_pbm(b, xx, yy, sync=False)
            _sync(sync)
            return True

        # BMP 1 bit, caso exista image.py
        if _Image is not None and len(b) >= 2 and b[0:2] == b"BM":
            img = _Image().load_bytes(b)
            fb = make_fb(img.buffer, img.width, img.height, fmt)
            o.blit(fb, xx, yy, -1)
            _sync(sync)
            return True

        # RAW precisa largura/altura
        if w is None or h is None:
            raise TypeError("bytes RAW precisa w/h: oled.drawIcon(buf, x, y, w, h)")

        fb = make_fb(b, int(w), int(h), fmt)
        o.blit(fb, xx, yy, -1)
        _sync(sync)
        return True

    raise TypeError("Icone em formato nao suportado: {}".format(type(icon_data)))


def icon(
    icon_data,
    x=0,
    y=0,
    w=None,
    h=None,
    fmt=framebuf.MONO_HLSB,
    module=None,
    sync=None,
):
    if isinstance(icon_data, str):
        icon_data = loadIcon(
            icon_data,
            module=module,
        )

    return draw_icon(
        icon_data,
        x,
        y,
        w,
        h,
        fmt,
        sync=sync,
    )


def drawIcon(
    icon_data,
    x=0,
    y=0,
    w=None,
    h=None,
    fmt=framebuf.MONO_HLSB,
    module=None,
    sync=None,
):
    return icon(
        icon_data,
        x=x,
        y=y,
        w=w,
        h=h,
        fmt=fmt,
        module=module,
        sync=sync,
    )


def drawAnyIcon(
    icon_data,
    x=0,
    y=0,
    w=None,
    h=None,
    fmt=framebuf.MONO_HLSB,
    module=None,
    sync=None,
):
    return icon(
        icon_data,
        x=x,
        y=y,
        w=w,
        h=h,
        fmt=fmt,
        module=module,
        sync=sync,
    )


# Alias antigo
image = draw_icon


# =========================================================
# Icones armazenados em /lib/mihuOled/icons
# =========================================================

def _normalize_symbol_name(value):
    text = str(value).strip().lower()

    for character in (
        " ",
        "-",
        ".",
        ":",
        "/",
        "\\",
    ):
        text = text.replace(
            character,
            "_",
        )

    while "__" in text:
        text = text.replace(
            "__",
            "_",
        )

    return text.strip("_")


def _icon_module_candidates(module_name):
    module_name = str(
        module_name
    ).strip()

    if module_name.endswith(".py"):
        module_name = module_name[:-3]

    module_name = module_name.replace(
        "/",
        ".",
    ).replace(
        "\\",
        ".",
    )

    if module_name.startswith(
        "mihuOled.icons."
    ):
        return (module_name,)

    if module_name.startswith(
        "lib.mihuOled.icons."
    ):
        return (module_name,)

    if module_name.startswith(
        "icons."
    ):
        short_name = module_name[6:]
    else:
        short_name = module_name

    return (
        "mihuOled.icons." + short_name,
        "lib.mihuOled.icons." + short_name,
        "icons." + short_name,
        short_name,
    )


def _import_icon_module(module_name):
    short_name = str(
        module_name
    ).strip()

    if short_name.endswith(".py"):
        short_name = short_name[:-3]

    if short_name in _icon_module_cache:
        return _icon_module_cache[
            short_name
        ]

    last_error = None

    for candidate in _icon_module_candidates(
        short_name
    ):
        try:
            module = __import__(
                candidate,
                None,
                None,
                ("*",),
            )

            _icon_module_cache[
                short_name
            ] = module

            return module

        except Exception as error:
            last_error = error

    raise ImportError(
        "Modulo de icones '{}' nao encontrado: {}".format(
            short_name,
            last_error,
        )
    )


def iconModules():
    """
    Lista os arquivos Python da pasta icons sem importá-los.
    """

    names = []

    # Lista física da pasta instalada.
    candidate_paths = (
        "/lib/mihuOled/icons",
        "lib/mihuOled/icons",
        "mihuOled/icons",
    )

    try:
        base_path = __file__.rsplit(
            "/",
            1,
        )[0]

        candidate_paths = (
            base_path + "/icons",
        ) + candidate_paths

    except Exception:
        pass

    for path in candidate_paths:
        try:
            entries = os.listdir(path)

            for entry in entries:
                if (
                    entry.endswith(".py")
                    and not entry.startswith("_")
                ):
                    name = entry[:-3]

                    if name not in names:
                        names.append(name)

        except Exception:
            pass

    # Fallback para os arquivos informados no projeto.
    for name in _DEFAULT_ICON_MODULES:
        if name not in names:
            names.append(name)

    names.sort()
    return tuple(names)


def _is_icon_value(value):
    if callable(value):
        return True

    if isinstance(
        value,
        (
            bytes,
            bytearray,
            memoryview,
            tuple,
            list,
        ),
    ):
        return True

    if (
        hasattr(value, "buffer")
        and hasattr(value, "width")
        and hasattr(value, "height")
    ):
        return True

    try:
        if isinstance(
            value,
            framebuf.FrameBuffer,
        ):
            return True
    except Exception:
        pass

    return False


def iconNames(module_name):
    """
    Lista os símbolos que podem representar ícones em um módulo.

    Exemplo:
        oled.iconNames("icons_menu")
    """

    module = _import_icon_module(
        module_name
    )

    names = []

    for name in dir(module):
        if name.startswith("_"):
            continue

        try:
            value = getattr(
                module,
                name,
            )
        except Exception:
            continue

        if _is_icon_value(value):
            names.append(name)

        elif isinstance(value, dict):
            for key in value:
                key_name = str(key)

                if key_name not in names:
                    names.append(key_name)

    names.sort()
    return tuple(names)


def _find_case_insensitive(
    container,
    symbol_name,
):
    wanted = _normalize_symbol_name(
        symbol_name
    )

    for name in dir(container):
        if name.startswith("_"):
            continue

        if (
            _normalize_symbol_name(name)
            == wanted
        ):
            return getattr(
                container,
                name,
            )

    return None


def _find_in_dictionaries(
    module,
    symbol_name,
):
    wanted = _normalize_symbol_name(
        symbol_name
    )

    for attribute_name in dir(module):
        if attribute_name.startswith("_"):
            continue

        try:
            value = getattr(
                module,
                attribute_name,
            )
        except Exception:
            continue

        if not isinstance(value, dict):
            continue

        for key, icon_value in value.items():
            if (
                _normalize_symbol_name(key)
                == wanted
            ):
                return icon_value

    return None


def loadIcon(
    name,
    module=None,
):
    """
    Carrega um ícone pelo nome.

    Formas:
        oled.loadIcon("HOME", "icons_menu")
        oled.loadIcon("icons_menu.HOME")
        oled.loadIcon("icons_menu:HOME")
    """

    if not isinstance(name, str):
        return name

    text = name.strip()

    if module is None:
        separator = None

        if ":" in text:
            separator = ":"

        elif "." in text:
            separator = "."

        if separator is not None:
            possible_module, possible_name = (
                text.split(
                    separator,
                    1,
                )
            )

            if possible_module in iconModules():
                module = possible_module
                text = possible_name

    if module is None:
        raise ValueError(
            "Informe o modulo do icone. Exemplo: "
            "oled.printIcon('icons_menu', 'HOME')."
        )

    icon_module = _import_icon_module(
        module
    )

    # Permite caminho interno: Classe.icone
    current = icon_module

    for part in text.replace(
        ":",
        ".",
    ).split("."):
        if not part:
            continue

        found = _find_case_insensitive(
            current,
            part,
        )

        if found is None:
            found = _find_in_dictionaries(
                current,
                part,
            )

        if found is None:
            raise KeyError(
                "Icone '{}' nao encontrado em '{}'. "
                "Disponiveis: {}".format(
                    name,
                    module,
                    iconNames(module),
                )
            )

        current = found

    return current


def printIcon(
    module,
    name,
    x=0,
    y=0,
    w=None,
    h=None,
    fmt=framebuf.MONO_HLSB,
    sync=None,
):
    """
    Desenha um ícone de um arquivo da pasta icons.

    Exemplo:
        oled.printIcon(
            "icons_menu",
            "HOME",
            0,
            0
        )
    """

    icon_data = loadIcon(
        name,
        module=module,
    )

    return draw_icon(
        icon_data,
        x=x,
        y=y,
        w=w,
        h=h,
        fmt=fmt,
        sync=sync,
    )


def showIcon(
    module,
    name,
    x=0,
    y=0,
    clear_first=True,
):
    """
    Limpa a tela, desenha um ícone e atualiza.
    """

    if clear_first:
        clear(
            0,
            sync=False,
        )

    result = printIcon(
        module,
        name,
        x=x,
        y=y,
        sync=False,
    )

    show()
    return result


def iconInfo(
    module,
    name,
):
    icon_value = loadIcon(
        name,
        module=module,
    )

    return {
        "module": str(module),
        "name": str(name),
        "type": type(icon_value).__name__,
        "callable": callable(icon_value),
        "has_buffer": hasattr(
            icon_value,
            "buffer",
        ),
        "width": getattr(
            icon_value,
            "width",
            None,
        ),
        "height": getattr(
            icon_value,
            "height",
            None,
        ),
    }


def unloadIcons(module=None):
    """
    Remove módulos de ícones do cache para liberar memória.
    """

    names_to_remove = []

    if module is None:
        names_to_remove = list(
            _icon_module_cache.keys()
        )
    else:
        names_to_remove = [
            str(module).strip()
        ]

    for short_name in names_to_remove:
        imported_module = _icon_module_cache.pop(
            short_name,
            None,
        )

        if imported_module is None:
            continue

        module_name = getattr(
            imported_module,
            "__name__",
            None,
        )

        if (
            module_name is not None
            and module_name in sys.modules
        ):
            try:
                del sys.modules[
                    module_name
                ]
            except Exception:
                pass

    gc.collect()
    return True


# =========================================================
# Scroll, deslocamento e transicoes
# =========================================================

def scroll(dx=0, dy=0, sync=None):
    oled().scroll(int(dx), int(dy))
    _sync(sync)


def shiftLeft(n=1, sync=None):
    o = oled()
    if hasattr(o, "shift_left"):
        o.shift_left(int(n), sync=False)
    else:
        o.scroll(-int(n), 0)
        _raw_fill_rect(o.width - int(n), 0, int(n), o.height, 0)
    _sync(sync)


def shiftRight(n=1, sync=None):
    o = oled()
    if hasattr(o, "shift_right"):
        o.shift_right(int(n), sync=False)
    else:
        o.scroll(int(n), 0)
        _raw_fill_rect(0, 0, int(n), o.height, 0)
    _sync(sync)


def shiftUp(n=1, sync=None):
    o = oled()
    if hasattr(o, "shift_up"):
        o.shift_up(int(n), sync=False)
    else:
        o.scroll(0, -int(n))
        _raw_fill_rect(0, o.height - int(n), o.width, int(n), 0)
    _sync(sync)


def shiftDown(n=1, sync=None):
    o = oled()
    if hasattr(o, "shift_down"):
        o.shift_down(int(n), sync=False)
    else:
        o.scroll(0, int(n))
        _raw_fill_rect(0, 0, o.width, int(n), 0)
    _sync(sync)


def shift_left(draw_old, draw_new, steps=16, delay_ms=12):
    w = oled().width
    old_auto = _auto_show
    auto_show(False)
    try:
        for i in range(int(steps) + 1):
            dx = (w * i) // int(steps)
            clear(0, sync=False)
            _call_draw(draw_old, -dx)
            _call_draw(draw_new, w - dx)
            show()
            sleep_ms(int(delay_ms))
    finally:
        auto_show(old_auto)


def shift_right(draw_old, draw_new, steps=16, delay_ms=12):
    w = oled().width
    old_auto = _auto_show
    auto_show(False)
    try:
        for i in range(int(steps) + 1):
            dx = (w * i) // int(steps)
            clear(0, sync=False)
            _call_draw(draw_old, dx)
            _call_draw(draw_new, -w + dx)
            show()
            sleep_ms(int(delay_ms))
    finally:
        auto_show(old_auto)


def shiftLeftTransition(draw_old, draw_new, steps=16, delay_ms=12):
    return shift_left(draw_old, draw_new, steps, delay_ms)


def shiftRightTransition(draw_old, draw_new, steps=16, delay_ms=12):
    return shift_right(draw_old, draw_new, steps, delay_ms)


def scroll_text_scale_tick(msg, y=0, scale=2, speed=2, gap=16, clear_first=True, sync=None):
    global _scroll_x

    msg = str(msg)
    scale = max(1, int(scale))
    text_w = len(msg) * 8 * scale

    if _scroll_x is None:
        _scroll_x = oled().width

    if clear_first:
        clear(0, sync=False)

    text_scale(msg, _scroll_x, y, scale=scale, color=1, sync=False)
    _scroll_x -= int(speed)

    if _scroll_x < -(text_w + int(gap)):
        _scroll_x = oled().width

    _sync(sync)


def scrollTextScaleTick(msg, y=0, scale=2, speed=2, gap=16):
    return scroll_text_scale_tick(msg, y, scale, speed, gap)


def reset_scroll():
    global _scroll_x
    _scroll_x = None


def resetScroll():
    return reset_scroll()

# =========================================================
# Ajuda no REPL
# =========================================================

def help():
    _console_print("=== MIHU OLED API UNIFICADA ===")
    _console_print("")
    _console_print("Inicializacao:")
    _console_print("  oled.init()")
    _console_print("  oled.autoShow(True)       # show() automatico")
    _console_print("  oled.autoShow(False)      # modo manual")
    _console_print("  oled.show()")
    _console_print("")
    _console_print("Fontes:")
    _console_print("  oled.fonts()")
    _console_print("  oled.setFont('font6')")
    _console_print("  oled.setFont('font10')")
    _console_print("  oled.setFont('font16b')")
    _console_print("  oled.setFont('freesans20')")
    _console_print("  oled.setFont('mont12h')")
    _console_print("  oled.setFont('mont18h')")
    _console_print("")
    _console_print("Texto:")
    _console_print("  oled.text('abc', x, y)")
    _console_print("  oled.write('abc', x, y, font_name='font10')")
    _console_print("  oled.center('abc', y)")
    _console_print("  oled.setCursor(x, y)")
    _console_print("  oled.print('abc')")
    _console_print("  oled.println('abc')")
    _console_print("  oled.textScale('ABC', x, y, scale=2)")
    _console_print("")
    _console_print("Desenho:")
    _console_print("  oled.pixel(x, y)")
    _console_print("  oled.line(x0, y0, x1, y1)")
    _console_print("  oled.hline(x, y, w)")
    _console_print("  oled.vline(x, y, h)")
    _console_print("  oled.rect(x, y, w, h)")
    _console_print("  oled.fillRect(x, y, w, h)")
    _console_print("  oled.circle(x, y, r)")
    _console_print("  oled.fillCircle(x, y, r)")
    _console_print("  oled.triangle(x0,y0,x1,y1,x2,y2)")
    _console_print("  oled.fillTriangle(x0,y0,x1,y1,x2,y2)")
    _console_print("  oled.roundRect(x, y, w, h, r)")
    _console_print("  oled.ellipse(x, y, rx, ry)")
    _console_print("  oled.fillEllipse(x, y, rx, ry)")
    _console_print("  oled.arc(x, y, raio, inicio, fim)")
    _console_print("  oled.polygon([(x,y), ...])")
    _console_print("  oled.fillPolygon([(x,y), ...])")
    _console_print("")
    _console_print("Componentes:")
    _console_print("  oled.progressBar(x, y, w, h, valor)")
    _console_print("  oled.battery(x, y, w, h, valor)")
    _console_print("  oled.menu('Menu', ['A','B'], selected=0)")
    _console_print("")
    _console_print("Icones e imagens:")
    _console_print("  oled.icon(icon, x, y)")
    _console_print("  oled.drawIcon(icon, x, y)")
    _console_print("  oled.drawPbm(pbmBytes, x, y)")
    _console_print("  oled.iconModules()")
    _console_print("  oled.iconNames('icons_menu')")
    _console_print("  oled.printIcon('icons_menu', 'HOME', x, y)")
    _console_print("  oled.icon('icons_menu.HOME', x, y)")
    _console_print("")
    _console_print("Scroll:")
    _console_print("  oled.shiftLeft(n)")
    _console_print("  oled.shiftRight(n)")
    _console_print("  oled.shiftUp(n)")
    _console_print("  oled.shiftDown(n)")
