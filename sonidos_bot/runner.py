"""Ejecuta el bot dentro de la app de configuración, en un hilo propio.

La ventana (Tk) necesita el hilo principal, así que el bot vive en otro hilo
con su propio bucle de asyncio. ``stop()`` le pide que salga del canal de voz
y espera a que termine, para que al cerrar la app el bot no quede colgado en
Discord.
"""

from __future__ import annotations

import asyncio
import logging
import threading

from .config import Config

log = logging.getLogger("sonidos_bot.runner")

STOPPED, STARTING, CONNECTED, ERROR = "detenido", "iniciando", "conectado", "error"


class BotRunner:
    def __init__(self, on_state=None):
        """``on_state(estado, detalle)`` se llama desde el hilo del bot."""
        self.on_state = on_state or (lambda state, detail: None)
        self.state = STOPPED
        self.config: Config | None = None
        self._thread: threading.Thread | None = None
        self._loop: asyncio.AbstractEventLoop | None = None
        self._bot = None

    @property
    def running(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def start(self, config: Config) -> None:
        if self.running:
            return
        self.config = config
        self._set(STARTING, "")
        self._thread = threading.Thread(target=self._run, args=(config,), name="bot", daemon=True)
        self._thread.start()

    def stop(self, timeout: float = 6.0) -> None:
        """Sale del canal de voz y apaga el bot. Bloquea hasta ``timeout`` segundos."""
        loop, bot, thread = self._loop, self._bot, self._thread
        if loop is not None and bot is not None and loop.is_running():
            future = asyncio.run_coroutine_threadsafe(bot.close(), loop)
            try:
                future.result(timeout=timeout)
            except Exception as exc:  # se cierra igual
                log.warning("El bot no se cerró del todo: %s", exc)
        if thread is not None:
            thread.join(timeout=timeout)

    def needs_restart(self, config: Config) -> bool:
        """El token y el servidor solo se aplican al arrancar."""
        old = self.config
        return old is not None and (old.discord.token, old.discord.guild_id) != (
            config.discord.token, config.discord.guild_id)

    # -- hilo del bot -------------------------------------------------------

    def _set(self, state: str, detail: str) -> None:
        self.state = state
        self.on_state(state, detail)

    def _run(self, config: Config) -> None:
        try:
            asyncio.run(self._main(config))
        except Exception as exc:
            log.exception("El bot se detuvo por un error")
            self._set(ERROR, describe_error(exc))
        else:
            self._set(STOPPED, "")
        finally:
            self._loop = self._bot = None

    async def _main(self, config: Config) -> None:
        from .bot import SoundBot  # importa discord.py solo cuando hace falta

        self._loop = asyncio.get_running_loop()
        self._bot = SoundBot(config, on_connected=lambda bot: self._set(CONNECTED, str(bot.user)))
        async with self._bot:
            await self._bot.start(config.discord.token)


def describe_error(exc: Exception) -> str:
    """Mensaje para la ventana a partir de los errores típicos al arrancar."""
    name = type(exc).__name__
    if name == "LoginFailure":
        return "El token no es válido. Cópialo de nuevo en el portal de Discord (Bot > Reset Token)."
    if name == "PrivilegedIntentsRequired":
        return "Falta activar 'Message Content Intent' en el portal de Discord (sección Bot)."
    return f"{name}: {exc}"
