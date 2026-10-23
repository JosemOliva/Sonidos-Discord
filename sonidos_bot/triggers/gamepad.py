"""Botones de un mando/joystick conectado a la PC.

Un hilo propio lee los mandos con ``pygame`` (sin abrir ventana). Funciona con
cualquier mando que Windows reconozca y admite conectarlo o desconectarlo con
el bot en marcha. Los mandos tipo Xbox se leen además por XInput (ver
``xinput.py``), por si pygame no los ve. Los números de botón empiezan en 0;
el menú del instalador los detecta pulsando el botón.
"""

from __future__ import annotations

import os
import threading

from . import xinput
from .base import Trigger

POLL_SECONDS = 0.01


def init_pygame_joystick():
    """Inicializa solo lo necesario de pygame para leer mandos en segundo plano."""
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_JOYSTICK_ALLOW_BACKGROUND_EVENTS", "1")
    os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame

    pygame.display.init()
    pygame.joystick.init()
    return pygame


def buttons_down(sticks) -> set[int]:
    """Botones pulsados ahora en cualquier mando.

    Manda XInput: un mando Xbox también puede aparecer en pygame con otra
    numeración, y así el mismo botón siempre da el mismo número.
    """
    down = xinput.pressed_buttons()
    if down:
        return down
    return {b for s in sticks for b in range(s.get_numbuttons()) if s.get_button(b)}


class GamepadTrigger(Trigger):
    name = "gamepad"

    async def start(self) -> None:
        self._buttons = {b.gamepad_button: b.sound_key for b in self.config.bindings if b.gamepad_button is not None}
        if not self._buttons:
            self.log.warning("No hay botones de mando configurados")
            self._thread = None
            return
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="gamepad", daemon=True)
        self._thread.start()

    async def stop(self) -> None:
        if self._thread is not None:
            self._stop.set()
            self._thread.join(timeout=2)
            self._thread = None

    def _run(self) -> None:
        try:
            self._poll()
        except Exception:
            self.log.exception("El lector de mandos se detuvo por un error")

    def _poll(self) -> None:
        pygame = init_pygame_joystick()
        sticks: list = []
        down_before: set[int] = set()
        while not self._stop.is_set():
            pygame.event.pump()
            if pygame.joystick.get_count() != len(sticks):
                sticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
                names = ", ".join(s.get_name() for s in sticks) or "ninguno"
                self.log.info("Mandos detectados: %s (XInput: %d)", names, xinput.connected_pads())
            down = buttons_down(sticks)
            for button in down - down_before:
                if button in self._buttons:
                    self.fire(self._buttons[button])
            down_before = down
            self._stop.wait(POLL_SECONDS)
        pygame.joystick.quit()
