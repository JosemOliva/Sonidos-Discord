"""Botones de un mando/joystick conectado a la PC.

Un hilo propio lee los mandos con ``pygame`` (sin abrir ventana). Funciona con
cualquier mando que Windows reconozca y admite conectarlo o desconectarlo con
el bot en marcha. Los números de botón empiezan en 0; el menú del instalador
los detecta pulsando el botón.
"""

from __future__ import annotations

import os
import threading

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
        pressed: dict[tuple[int, int], bool] = {}
        while not self._stop.is_set():
            pygame.event.pump()
            if pygame.joystick.get_count() != len(sticks):
                sticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
                names = ", ".join(s.get_name() for s in sticks) or "ninguno"
                self.log.info("Mandos detectados: %s", names)
            for s in sticks:
                jid = s.get_instance_id()
                for button, key in self._buttons.items():
                    if button >= s.get_numbuttons():
                        continue
                    down = bool(s.get_button(button))
                    if down and not pressed.get((jid, button)):
                        self.fire(key)
                    pressed[(jid, button)] = down
            self._stop.wait(POLL_SECONDS)
        pygame.joystick.quit()
