"""Atajos de teclado globales (funcionan aunque la ventana no tenga el foco).

Usa el formato de ``pynput``: ``<ctrl>+<alt>+1``, ``<f9>``, ``<shift>+a``.
"""

from __future__ import annotations

from .base import Trigger


class KeyboardTrigger(Trigger):
    name = "keyboard"

    async def start(self) -> None:
        from pynput import keyboard

        hotkeys = {}
        for b in self.config.bindings:
            if not b.hotkey:
                continue
            try:
                keyboard.HotKey.parse(b.hotkey)
            except ValueError:
                self.log.error("Atajo inválido '%s' para '%s', lo ignoro", b.hotkey, b.sound)
                continue
            hotkeys[b.hotkey] = lambda key=b.sound_key: self.fire(key)

        if not hotkeys:
            self.log.warning("No hay atajos de teclado configurados")
            self._listener = None
            return
        self._listener = keyboard.GlobalHotKeys(hotkeys)
        self._listener.daemon = True
        self._listener.start()

    async def stop(self) -> None:
        if self._listener is not None:
            self._listener.stop()
            self._listener = None
