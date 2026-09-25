try:
    from lib.mihuOled import mihuOled as oled
except Exception:
    oled = None

from .cjk import (
    is_cjk,
    draw_char,
    CELL_W,
    CELL_H,
)
from ..i18n import (
    t,
    test_label,
    result_message,
)


WIDTH = 128
HEIGHT = 64

MENU_VISIBLE_ROWS = 5
MENU_ROW_HEIGHT = 10
MENU_FIRST_Y = 14

SCROLL_X = 124
SCROLL_Y = 14
SCROLL_W = 3
SCROLL_H = 48


def init():
    if oled is None:
        return False

    try:
        oled.init()

        try:
            oled.autoShow(False)
        except Exception:
            pass

        return True

    except Exception:
        return False


def _device():
    if oled is None:
        return None

    try:
        return oled.oled()
    except Exception:
        return None


def _show():
    if oled is None:
        return

    try:
        oled.show()
    except Exception:
        pass


def clear(sync=False):
    if oled is None:
        return

    try:
        oled.clear(sync=sync)
        return
    except Exception:
        pass

    try:
        oled.clear()
    except Exception:
        pass

    if sync:
        _show()


def _ascii_text(text, x, y):
    if oled is None:
        return

    try:
        oled.text(
            str(text),
            int(x),
            int(y),
            scale=1,
            color=1,
            sync=False,
        )
        return
    except Exception:
        pass

    try:
        oled.text(
            str(text),
            int(x),
            int(y),
            color=1,
            sync=False,
        )
        return
    except Exception:
        pass

    try:
        oled.text(
            str(text),
            int(x),
            int(y),
        )
    except Exception:
        pass


def _text(text, x, y, sync=False):
    """
    Mixed ASCII + Chinese renderer.

    ASCII uses the normal mihuOled font.
    Chinese uses a tiny 10x10 bitmap set generated only for
    the factory-test interface.
    """
    if oled is None:
        return

    text = str(text)
    dev = _device()

    # Fast path for pure ASCII.
    has_cjk = False

    for char in text:
        if is_cjk(char):
            has_cjk = True
            break

    if not has_cjk or dev is None:
        _ascii_text(
            text,
            x,
            y,
        )

        if sync:
            _show()

        return

    cursor_x = int(x)
    ascii_buffer = ""
    ascii_start_x = cursor_x

    def flush_ascii():
        nonlocal ascii_buffer
        nonlocal ascii_start_x

        if ascii_buffer:
            _ascii_text(
                ascii_buffer,
                ascii_start_x,
                y,
            )
            ascii_buffer = ""

    for char in text:

        if is_cjk(char):
            flush_ascii()

            draw_char(
                dev,
                char,
                cursor_x,
                y,
                1,
            )

            cursor_x += CELL_W
            ascii_start_x = cursor_x

        else:
            if not ascii_buffer:
                ascii_start_x = cursor_x

            ascii_buffer += char
            cursor_x += 8

    flush_ascii()

    if sync:
        _show()


def _fill_rect(x, y, w, h, color=1):
    if oled is None:
        return False

    for name in (
        "fill_rect",
        "fillRect",
    ):
        fn = getattr(
            oled,
            name,
            None,
        )

        if fn is None:
            continue

        try:
            fn(
                int(x),
                int(y),
                int(w),
                int(h),
                int(color),
                sync=False,
            )
            return True
        except TypeError:
            try:
                fn(
                    int(x),
                    int(y),
                    int(w),
                    int(h),
                    int(color),
                )
                return True
            except Exception:
                pass
        except Exception:
            pass

    return False


def _rect(x, y, w, h, color=1):
    if oled is None:
        return False

    for name in (
        "rect",
        "drawRect",
    ):
        fn = getattr(
            oled,
            name,
            None,
        )

        if fn is None:
            continue

        try:
            fn(
                int(x),
                int(y),
                int(w),
                int(h),
                int(color),
                sync=False,
            )
            return True
        except TypeError:
            try:
                fn(
                    int(x),
                    int(y),
                    int(w),
                    int(h),
                    int(color),
                )
                return True
            except Exception:
                pass
        except Exception:
            pass

    return False


def fill_white():
    """
    Turns every OLED pixel on.
    """
    if oled is None:
        return

    clear(False)

    if not _fill_rect(
        0,
        0,
        WIDTH,
        HEIGHT,
        1,
    ):
        try:
            oled.fill(
                1,
                sync=False,
            )
        except TypeError:
            try:
                oled.fill(1)
            except Exception:
                pass
        except Exception:
            pass

    _show()


def show_lines(lines):
    if oled is None:
        return

    clear(False)

    y = 0

    for line in lines[:6]:
        _text(
            str(line),
            0,
            y,
            False,
        )
        y += 10

    _show()


def _menu_window(
    index,
    total,
    visible,
):
    if total <= visible:
        return 0

    if index < visible:
        return 0

    start = (
        index
        - visible
        + 1
    )

    max_start = (
        total
        - visible
    )

    if start > max_start:
        start = max_start

    return start


def _draw_scrollbar(
    total,
    visible,
    start,
):
    if total <= visible:
        return

    _rect(
        SCROLL_X,
        SCROLL_Y,
        SCROLL_W,
        SCROLL_H,
        1,
    )

    inner_h = (
        SCROLL_H
        - 2
    )

    thumb_h = (
        inner_h
        * visible
    ) // total

    if thumb_h < 7:
        thumb_h = 7

    max_start = (
        total
        - visible
    )

    travel = (
        inner_h
        - thumb_h
    )

    if max_start <= 0:
        thumb_y = (
            SCROLL_Y
            + 1
        )
    else:
        thumb_y = (
            SCROLL_Y
            + 1
            + (
                travel
                * start
            ) // max_start
        )

    _fill_rect(
        SCROLL_X + 1,
        thumb_y,
        1,
        thumb_h,
        1,
    )


def show_menu(
    title,
    items,
    selected_index,
    visible_rows=MENU_VISIBLE_ROWS,
):
    if oled is None:
        return

    items = tuple(items)
    total = len(items)

    if total == 0:
        show_lines([
            title,
            "",
            t("no_items"),
        ])
        return

    if selected_index < 0:
        selected_index = 0

    if selected_index >= total:
        selected_index = total - 1

    visible = min(
        int(visible_rows),
        total,
    )

    start = _menu_window(
        selected_index,
        total,
        visible,
    )

    clear(False)

    _text(
        str(title),
        0,
        0,
        False,
    )

    _fill_rect(
        0,
        11,
        121,
        1,
        1,
    )

    for row in range(visible):
        item_index = (
            start
            + row
        )

        if item_index >= total:
            break

        label = str(
            items[item_index]
        )

        prefix = (
            ">"
            if item_index == selected_index
            else " "
        )

        _text(
            prefix + label,
            0,
            MENU_FIRST_Y
            + (
                row
                * MENU_ROW_HEIGHT
            ),
            False,
        )

    _draw_scrollbar(
        total,
        visible,
        start,
    )

    _show()


def result_screen(
    name,
    passed,
    message="",
):
    status = (
        t("pass_short")
        if passed
        else t("fail_short")
    )

    localized_message = (
        result_message(
            message
        )
    )

    show_lines([
        test_label(name),
        "",
        status,
        "",
        localized_message,
    ])
