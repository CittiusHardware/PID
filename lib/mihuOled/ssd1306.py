# ============================================================
# OLED 128x64 – Driver + Hardware (ARQUIVO ÚNICO)
# ============================================================

from machine import I2C, Pin
from micropython import const
import framebuf

# ------------------------------------------------------------
# COMANDOS SSD1306
# ------------------------------------------------------------

SET_CONTRAST = const(0x81)
SET_ENTIRE_ON = const(0xA4)
SET_NORM_INV = const(0xA6)
SET_DISP = const(0xAE)
SET_MEM_ADDR = const(0x20)
SET_COL_ADDR = const(0x21)
SET_PAGE_ADDR = const(0x22)
SET_DISP_START_LINE = const(0x40)
SET_SEG_REMAP = const(0xA0)
SET_MUX_RATIO = const(0xA8)
SET_COM_OUT_DIR = const(0xC0)
SET_DISP_OFFSET = const(0xD3)
SET_COM_PIN_CFG = const(0xDA)
SET_DISP_CLK_DIV = const(0xD5)
SET_PRECHARGE = const(0xD9)
SET_VCOM_DESEL = const(0xDB)
SET_CHARGE_PUMP = const(0x8D)

# ------------------------------------------------------------
# DRIVER BASE
# ------------------------------------------------------------

class SSD1306(framebuf.FrameBuffer):
    def __init__(self, width, height, external_vcc):
        self.width = width
        self.height = height
        self.external_vcc = external_vcc
        self.pages = self.height // 8
        self.buffer = bytearray(self.pages * self.width)

        super().__init__(self.buffer, self.width, self.height, framebuf.MONO_VLSB)
        self.init_display()

    def init_display(self):
        for cmd in (
            SET_DISP | 0x00,
            SET_MEM_ADDR, 0x00,
            SET_DISP_START_LINE | 0x00,
            SET_SEG_REMAP | 0x01,
            SET_MUX_RATIO, self.height - 1,
            SET_COM_OUT_DIR | 0x08,
            SET_DISP_OFFSET, 0x00,
            SET_COM_PIN_CFG, 0x12,
            SET_DISP_CLK_DIV, 0x80,
            SET_PRECHARGE, 0xF1,
            SET_VCOM_DESEL, 0x30,
            SET_CONTRAST, 0xFF,
            SET_ENTIRE_ON,
            SET_NORM_INV,
            SET_CHARGE_PUMP, 0x14,
            SET_DISP | 0x01,
        ):
            self.write_cmd(cmd)

        self.fill(0)
        self.show()

    def show(self):
        self.write_cmd(SET_COL_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.width - 1)
        self.write_cmd(SET_PAGE_ADDR)
        self.write_cmd(0)
        self.write_cmd(self.pages - 1)
        self.write_data(self.buffer)


    def poweroff(self):
        self.write_cmd(SET_DISP | 0x00)

    def poweron(self):
        self.write_cmd(SET_DISP | 0x01)

    def contrast(self, value):
        self.write_cmd(SET_CONTRAST)
        self.write_cmd(int(value) & 0xFF)

    def invert(self, value):
        self.write_cmd(
            SET_NORM_INV | (int(bool(value)) & 1)
        )


# ------------------------------------------------------------
# I2C
# ------------------------------------------------------------

class SSD1306_I2C(SSD1306):
    def __init__(self, width, height, i2c, addr=0x3C):
        self.i2c = i2c
        self.addr = addr
        self.temp = bytearray(2)
        self.write_list = [b"\x40", None]
        super().__init__(width, height, False)

    def write_cmd(self, cmd):
        self.temp[0] = 0x80
        self.temp[1] = cmd
        self.i2c.writeto(self.addr, self.temp)

    def write_data(self, buf):
        self.write_list[1] = buf
        self.i2c.writevto(self.addr, self.write_list)

    def shift_left(self, n=1, sync=True):
        if n <= 0:
            return
        if n >= self.width:
            self.fill(0)
        else:
            self.scroll(-n, 0)  # empurra o framebuffer pra esquerda
            self.fill_rect(self.width - n, 0, n, self.height, 0)  # limpa a faixa da direita
        if sync:
            self.show()
            
    def shift_right(self, n=1, sync=True):
        if n <= 0:
            return
        if n >= self.width:
            self.fill(0)
        else:
            self.scroll(n, 0)  # empurra pra direita
            self.fill_rect(0, 0, n, self.height, 0)  # limpa a faixa da esquerda
        if sync:
            self.show()

    def shift_up(self, n=1, sync=True):
        if n <= 0:
            return
        if n >= self.height:
            self.fill(0)
        else:
            self.scroll(0, -n)  # empurra pra cima
            self.fill_rect(0, self.height - n, self.width, n, 0)  # limpa a faixa de baixo
        if sync:
            self.show()

    def shift_down(self, n=1, sync=True):
        if n <= 0:
            return
        if n >= self.height:
            self.fill(0)
        else:
            self.scroll(0, n)  # empurra pra baixo
            self.fill_rect(0, 0, self.width, n, 0)  # limpa a faixa de cima
        if sync:
            self.show()
