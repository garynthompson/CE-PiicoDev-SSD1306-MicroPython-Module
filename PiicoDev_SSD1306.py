# Sends data to the Core Electronics PiicoDev OLED SSD1306 Display
# Ported by Peter Johnston at Core Electronics October 2021
# Original Repos:
# 2021-09-12:
# https://github.com/micropython/micropython/blob/master/drivers/display/ssd1306.py
# 2021-08-01:
# https://github.com/fizban99/microbit_ssd1306/blob/master/ssd1306_text.py
# 2021-07-15:
# https://github.com/adafruit/Adafruit_Python_SSD1306/blob/master/Adafruit_SSD1306/SSD1306.py

# 2021 OCT 14 - Initial release
# 2022 JAN 04 - Remove dependency on PIL module.  Improve compatibility with pbm files.
from PiicoDev_Unified import *
from math import cos, sin, radians

_SET_CONTRAST = b"\x81"
_SET_ENTIRE_ON = b"\xA4"
_SET_NORM_INV = b"\xA6"
_SET_DISP = b"\xAE"
_SET_DISP_O1 = b"\xAF"
_SET_MEM_ADDR = b"\x20"
_SET_COL_ADDR = b"\x21"
_SET_PAGE_ADDR = b"\x22"
_SET_DISP_START_LINE = b"\x40"
_SET_SEG_REMAP = b"\xA0"
_SET_SEG_REMAP_O1 = b"\xA1"
_SET_MUX_RATIO = b"\xA8"
_SET_IREF_SELECT = b"\xAD"
_SET_COM_OUT_DIR = b"\xC0"
_SET_COM_OUT_DIR_O8 = b"\xC8"
_SET_DISP_OFFSET = b"\xD3"
_SET_COM_PIN_CFG = b"\xDA"
_SET_DISP_CLK_DIV = b"\xD5"
_SET_PRECHARGE = b"\xD9"
_SET_VCOM_DESEL = b"\xDB"
_SET_CHARGE_PUMP = b"\x8D"
_X0 = b"\x00"
_X1 = b"\x01"

WIDTH = 128
HEIGHT = 64
DEFAULT_ADDRESS = 0x3C
_DATA_CMD = int.from_bytes(b"\x40", "big")
_CMD = int.from_bytes(b"\x80", "big")

if PLATFORM_BUILD == "microbit":
    # noinspection PyUnresolvedReferences
    from microbit import *

    # noinspection PyUnresolvedReferences
    from utime import sleep_ms

    # noinspection PyUnresolvedReferences
    from ustruct import pack_into
elif PLATFORM_BUILD == "Linux":
    from struct import pack_into
elif PLATFORM_BUILD == "micropython":
    pass  # This is imported later.
else:
    raise NotImplementedError(f"Unsupported platform {PLATFORM_BUILD}")


if PLATFORM_BUILD in ("microbit", "Linux"):

    # noinspection PyUnresolvedReferences,SpellCheckingInspection
    class FrameBuffer:
        """
        A mixin to provide compatibility with MicroPython
        """

        resource_path = ""

        def __init__(self, *args, **kwargs):
            pass

        # Framebuffer manipulation, used by Microbit and Linux
        def _set_pos(self, col=0, page=0):
            self.write_cmd(0xB0 | page)  # page number
            # take upper and lower value of col * 2
            c1, c2 = col * 2 & 0x0F, col >> 3
            self.write_cmd(0x00 | c1)  # lower start column address
            self.write_cmd(0x10 | c2)  # upper start column address

        def fill(self, c=0):
            for i in range(0, 1024):
                if c > 0:
                    self.buffer[i] = 0xFF
                else:
                    self.buffer[i] = 0x00

        def pixel(self, x, y, color):
            x = x & (WIDTH - 1)
            y = y & (HEIGHT - 1)
            page, shift_page = divmod(y, 8)
            ind = x + page * 128
            b = (
                self.buffer[ind] | (1 << shift_page)
                if color
                else self.buffer[ind] & ~(1 << shift_page)
            )
            pack_into(">B", self.buffer, ind, b)
            self._set_pos(x, page)

        def line(self, x1, y1, x2, y2, c):
            # bresenham
            steep = abs(y2 - y1) > abs(x2 - x1)

            if steep:
                # Swap x/y
                tmp = x1
                x1 = y1
                y1 = tmp

                tmp = y2
                y2 = x2
                x2 = tmp

            if x1 > x2:
                # Swap start/end
                tmp = x1
                x1 = x2
                x2 = tmp
                tmp = y1
                y1 = y2
                y2 = tmp

            dx = x2 - x1
            dy = abs(y2 - y1)

            err = dx / 2

            if y1 < y2:
                y_step = 1
            else:
                y_step = -1

            while x1 <= x2:
                if steep:
                    self.pixel(y1, x1, c)
                else:
                    self.pixel(x1, y1, c)
                err -= dy
                if err < 0:
                    y1 += y_step
                    err += dx
                x1 += 1

        def hline(self, x, y, l, c):
            self.line(x, y, x + l, y, c)

        def vline(self, x, y, h, c):
            self.line(x, y, x, y + h, c)

        def rect(self, x, y, w, h, c):
            self.hline(x, y, w, c)
            self.hline(x, y + h, w, c)
            self.vline(x, y, h, c)
            self.vline(x + w, y, h, c)

        def fill_rect(self, x, y, w, h, c):
            for i in range(y, y + h):
                self.hline(x, i, w, c)

        def text(self, text, x, y, c=1):
            font_file = open(f"{self.resource_path}font-pet-me-128.dat", "rb")
            font = bytearray(font_file.read())
            for text_index in range(0, len(text)):
                for col in range(8):
                    font_data_pixel_values = font[
                        (ord(text[text_index]) - 32) * 8 + col
                    ]
                    for i in range(0, 7):
                        if font_data_pixel_values & 1 << i != 0:
                            x_coordinate = x + col + text_index * 8
                            y_coordinate = y + i
                            if x_coordinate < WIDTH and y_coordinate < HEIGHT:
                                self.pixel(x_coordinate, y_coordinate, c)

else:
    # Micropython already provides a FrameBuffer class.
    # noinspection PyUnresolvedReferences
    from framebuf import FrameBuffer, MONO_VLSB


# noinspection PyPep8Naming
class PiicoDev_SSD1306(FrameBuffer):
    # noinspection SpellCheckingInspection
    """
    Exception masking has been removed from this class as this risks errors
    passing silenced.  It is recommended to wrap calls to this class in a
    try-except block when sending commands to the device.

    On Micropython 1.2.5 the Framebuffer class has the following:
    ['__class__', '__name__', '__bases__', '__dict__', 'blit', 'ellipse',
    'fill', 'fill_rect', 'hline', 'line', 'pixel',
    'poly', 'rect', 'scroll', 'text', 'vline']

    """

    def __init__(self, bus=None, freq=None, sda=None, scl=None, addr=DEFAULT_ADDRESS):
        self.i2c = create_unified_i2c(bus=bus, freq=freq, sda=sda, scl=scl)
        self.addr = addr
        self.width = WIDTH
        self._w1 = bytes([WIDTH - 1])
        self.height = HEIGHT
        self._h1 = bytes([HEIGHT - 1])
        self.pages = HEIGHT // 8
        self._last_page = bytes([self.pages - 1])
        self.buffer = memoryview(bytearray(self.pages * WIDTH))
        try:
            self.init_display()
            super().__init__(self.buffer, WIDTH, HEIGHT, MONO_VLSB)
            self.fill(0)
            self.show()
        except Exception as e:
            raise RuntimeError(f"{e} {i2c_err_str.format(self.addr)}")

    def init_display(self):
        for cmd in (
            _SET_DISP,  # display off
            # address setting
            _SET_MEM_ADDR,
            _X0,  # horizontal
            # resolution and layout
            _SET_DISP_START_LINE,  # start at line 0
            _SET_SEG_REMAP_O1,  # column addr 127 mapped to SEG0
            _SET_MUX_RATIO,
            self._h1,
            _SET_COM_OUT_DIR_O8,  # scan from COM[N] to COM0
            _SET_DISP_OFFSET,
            _X0,
            _SET_COM_PIN_CFG,
            b"\x12",
            # timing and driving scheme
            _SET_DISP_CLK_DIV,
            b"\x80",
            _SET_PRECHARGE,
            b"\xF1",
            _SET_VCOM_DESEL,
            b"\x30",  # 0.83*Vcc
            # display
            _SET_CONTRAST,
            b"\xFF",  # maximum
            _SET_ENTIRE_ON,  # output follows RAM contents
            _SET_NORM_INV,  # not inverted
            _SET_IREF_SELECT,
            b"\x30",  # enable internal IREF during display on
            # charge pump
            _SET_CHARGE_PUMP,
            b"\x14",
            _SET_DISP_O1,  # display on
        ):  # on
            self._cmd(cmd)

    def power_off(self):
        self._cmd(_SET_DISP)

    def power_on(self):
        self._cmd(_SET_DISP_O1)

    def set_contrast(self, contrast):
        self._cmd(_SET_CONTRAST)
        self._cmd(bytes([contrast]))

    def invert(self, invert):
        self._cmd(bytes([int.from_bytes(_SET_NORM_INV, "big") | (invert & 1)]))

    def rotate(self, rotate):
        self._cmd(
            bytes([int.from_bytes(_SET_COM_OUT_DIR, "big") | ((rotate & 1) << 3)])
        )
        self._cmd(bytes([int.from_bytes(_SET_SEG_REMAP, "big") | (rotate & 1)]))

    def show(self):
        self._cmd(_SET_COL_ADDR)
        self._cmd(_X0)
        self._cmd(self._w1)
        self._cmd(_SET_PAGE_ADDR)
        self._cmd(_X0)
        self._cmd(self._last_page)
        self.i2c.writeto_mem(self.addr, _DATA_CMD, self.buffer)

    def _cmd(self, cmd: bytes):
        """
        Raises an exception if the command fails
        """
        self.i2c.writeto_mem(self.addr, _CMD, cmd)

    def circ(self, x, y, r, t=1, c=1):
        for i in range(x - r, x + r + 1):
            for j in range(y - r, y + r + 1):
                if t == 1:
                    if (i - x) ** 2 + (j - y) ** 2 < r**2:
                        self.pixel(i, j, 1)
                else:
                    if ((i - x) ** 2 + (j - y) ** 2 < r**2) and (
                        (i - x) ** 2 + (j - y) ** 2 >= (r - r * t - 1) ** 2
                    ):
                        self.pixel(i, j, c)

    def arc(self, x, y, r, stAng, enAng, t=0, c=1):
        for i in range(r * (1 - t) - 1, r):
            for ta in range(stAng, enAng, 1):
                X = int(i * cos(radians(ta)) + x)
                Y = int(i * sin(radians(ta)) + y)
                self.pixel(X, Y, c)

    def load_pbm(self, filename, c):
        with open(filename, "rb") as f:
            line = f.readline()
            if line.startswith(b"P4") is False:
                print("Not a valid pbm P4 file")
                return
            line = f.readline()
            while line.startswith(b"#") is True:
                line = f.readline()
            data_piicodev = bytearray(f.read())
        for byte in range(WIDTH // 8 * HEIGHT):
            for bit in range(8):
                if data_piicodev[byte] & 1 << bit != 0:
                    x_coordinate = ((7 - bit) + (byte * 8)) % WIDTH
                    y_coordinate = byte * 8 // WIDTH
                    if x_coordinate < WIDTH and y_coordinate < HEIGHT:
                        self.pixel(x_coordinate, y_coordinate, c)

    class graph2D:  # noqa
        def __init__(
            self,
            originX=0,  # noqa
            originY=HEIGHT - 1,  # noqa
            width=WIDTH,
            height=HEIGHT,
            minValue=0,  # noqa
            maxValue=255,  # noqa
            c=1,
            bars=False,
        ):
            self.minValue = minValue
            self.maxValue = maxValue
            self.originX = originX
            self.originY = originY
            self.width = width
            self.height = height
            self.c = c
            self.m = (1 - height) / (maxValue - minValue)
            self.offset = originY - self.m * minValue
            self.bars = bars
            self.data = []

    def updateGraph2D(self, graph, value):
        graph.data.insert(0, value)
        if len(graph.data) > graph.width:
            graph.data.pop()
        x = graph.originX + graph.width - 1
        m = graph.c
        for value in graph.data:
            y = round(graph.m * value + graph.offset)
            if graph.bars:
                for idx in range(y, graph.originY + 1):
                    if graph.originX <= x < (
                        graph.originX + graph.width
                    ) and graph.originY >= idx > (graph.originY - graph.height):
                        self.pixel(x, idx, m)
            else:
                if graph.originX <= x < (
                    graph.originX + graph.width
                ) and graph.originY >= y > (graph.originY - graph.height):
                    self.pixel(x, y, m)
            x -= 1


def _get_address(asw, address):
    if asw == 0:
        _a = 0x3C
    elif asw == 1:
        _a = 0x3D
    else:
        _a = address  # parse desired address from direct address input or asw switch position (0 or 1)
    # noinspection PyBroadException
    try:
        if compat_ind >= 1:
            pass
        else:
            print(compat_str)
    except:
        print(compat_str)
    return _a


if PLATFORM_BUILD == "micropython":

    def create_PiicoDev_SSD1306(  # noqa
        address=DEFAULT_ADDRESS, bus=None, freq=None, sda=None, scl=None, asw=None
    ):
        _a = _get_address(asw, address)
        display = PiicoDev_SSD1306(addr=_a, bus=bus, freq=freq, sda=sda, scl=scl)
        return display

elif PLATFORM_BUILD == "microbit":

    # noinspection PyUnusedLocal
    def create_PiicoDev_SSD1306(  # noqa
        address=DEFAULT_ADDRESS, bus=None, freq=None, sda=None, scl=None, asw=None
    ):
        _a = _get_address(asw, address)
        display = PiicoDev_SSD1306(addr=_a, freq=freq)
        return display

elif PLATFORM_BUILD == "Linux":

    # noinspection PyUnusedLocal
    def create_PiicoDev_SSD1306(  # noqa
        address=DEFAULT_ADDRESS, bus=None, freq=None, sda=None, scl=None, asw=None
    ):
        _a = _get_address(asw, address)
        display = PiicoDev_SSD1306(addr=_a, freq=freq)
        return display

else:
    raise NotImplementedError(f"Unsupported platform {PLATFORM_BUILD}")
