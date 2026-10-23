"""Lectura directa de mandos XInput (Xbox y compatibles) en Windows.

Respaldo de ``pygame``: algunos mandos que Windows muestra como
"Controller (XBOX 360 For Windows)" no llegan a pygame cuando se lee desde un
hilo sin ventana. Aquí se consultan con ``XInputGetState`` y los botones se
numeran igual que en pygame (A=0, B=1, X=2, Y=3, LB=4, RB=5, Back=6,
Start=7, L3=8, R3=9), así que un número guardado sirve con cualquiera de los
dos lectores.
"""

from __future__ import annotations

import ctypes
import sys

MAX_PADS = 4

# Bit de cada botón en wButtons, en el orden de pygame.
BUTTON_BITS = (0x1000, 0x2000, 0x4000, 0x8000, 0x0100, 0x0200, 0x0020, 0x0010, 0x0040, 0x0080)


class _Gamepad(ctypes.Structure):
    _fields_ = [
        ("wButtons", ctypes.c_ushort),
        ("bLeftTrigger", ctypes.c_ubyte),
        ("bRightTrigger", ctypes.c_ubyte),
        ("sThumbLX", ctypes.c_short),
        ("sThumbLY", ctypes.c_short),
        ("sThumbRX", ctypes.c_short),
        ("sThumbRY", ctypes.c_short),
    ]


class _State(ctypes.Structure):
    _fields_ = [("dwPacketNumber", ctypes.c_uint), ("Gamepad", _Gamepad)]


def _load():
    if sys.platform != "win32":
        return None
    for name in ("xinput1_4", "xinput1_3", "xinput9_1_0"):
        try:
            return getattr(ctypes.windll, name)
        except OSError:
            continue
    return None


_dll = _load()


def buttons_from_mask(mask: int) -> set[int]:
    """Convierte la máscara ``wButtons`` en números de botón al estilo pygame."""
    return {i for i, bit in enumerate(BUTTON_BITS) if mask & bit}


def connected_pads() -> int:
    """Cuántos mandos XInput hay conectados (0 fuera de Windows)."""
    if _dll is None:
        return 0
    state = _State()
    return sum(1 for pad in range(MAX_PADS) if _dll.XInputGetState(pad, ctypes.byref(state)) == 0)


def pressed_buttons() -> set[int]:
    """Botones pulsados ahora mismo en cualquier mando XInput."""
    if _dll is None:
        return set()
    pressed: set[int] = set()
    state = _State()
    for pad in range(MAX_PADS):
        if _dll.XInputGetState(pad, ctypes.byref(state)) == 0:
            pressed |= buttons_from_mask(state.Gamepad.wButtons)
    return pressed
