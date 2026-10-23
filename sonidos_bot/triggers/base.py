"""Contrato común para todos los disparadores (teclado, mando, palabra clave).

Cada disparador corre por su cuenta (algunos en hilos propios, como el
teclado o el mando) y, cuando detecta algo, llama a ``fire`` con el nombre
del sonido. ``fire`` es seguro de llamar desde cualquier hilo: entrega el
pedido al bucle de asyncio del bot.
"""

from __future__ import annotations

import asyncio
import logging
from abc import ABC, abstractmethod
from typing import Awaitable, Callable

from ..config import Config

# Recibe (clave_del_sonido, nombre_del_disparador).
PlayCallback = Callable[[str, str], Awaitable[None]]


class Trigger(ABC):
    name: str = "base"

    def __init__(self, config: Config, on_trigger: PlayCallback, loop: asyncio.AbstractEventLoop):
        self.config = config
        self._on_trigger = on_trigger
        self._loop = loop
        self.log = logging.getLogger(f"sonidos_bot.trigger.{self.name}")

    def fire(self, sound_key: str) -> None:
        self.log.debug("Disparado '%s'", sound_key)
        asyncio.run_coroutine_threadsafe(self._on_trigger(sound_key, self.name), self._loop)

    @abstractmethod
    async def start(self) -> None:
        """Empieza a escuchar. No debe bloquear el bucle de eventos."""

    @abstractmethod
    async def stop(self) -> None:
        """Libera hilos, dispositivos y hooks."""

    def voice_connected(self, voice) -> None:
        """El bot entró (o volvió a entrar) al canal de voz. Solo lo usa el modo por voz."""
