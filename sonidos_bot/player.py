"""Reproducción de sonidos en el canal de voz con FFmpeg.

Mantiene una única conexión de voz y aplica el volumen y el tiempo de espera
(cooldown) entre sonidos. Si llega un sonido mientras suena otro, corta el
actual y reproduce el nuevo.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import sys
import time
from pathlib import Path

import discord

from .config import Config

log = logging.getLogger("sonidos_bot.player")


def find_ffmpeg() -> str:
    """Busca ffmpeg junto al ejecutable (instalador) y si no, en el PATH."""
    candidates = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)))
        candidates.append(Path(sys.executable).parent)
    candidates.append(Path(__file__).resolve().parent.parent)
    exe = "ffmpeg.exe" if sys.platform == "win32" else "ffmpeg"
    for folder in candidates:
        for path in (folder / exe, folder / "ffmpeg" / exe, folder / "ffmpeg" / "bin" / exe):
            if path.exists():
                return str(path)
    found = shutil.which("ffmpeg")
    if found:
        return found
    raise FileNotFoundError("No se encontró ffmpeg. Instálalo o colócalo junto al programa.")


class Player:
    def __init__(self, config: Config, voice_client_cls: type[discord.VoiceProtocol] | None = None):
        self.config = config
        self.voice_client_cls = voice_client_cls
        self.voice: discord.VoiceClient | None = None
        self._ffmpeg = find_ffmpeg()
        self._last_play = 0.0
        self._lock = asyncio.Lock()

    @property
    def connected(self) -> bool:
        return self.voice is not None and self.voice.is_connected()

    async def connect(self, channel: discord.VoiceChannel) -> discord.VoiceClient:
        async with self._lock:
            if self.connected:
                if self.voice.channel.id != channel.id:
                    await self.voice.move_to(channel)
                return self.voice
            kwargs = {"self_deaf": False, "reconnect": True}
            if self.voice_client_cls is not None:
                kwargs["cls"] = self.voice_client_cls
            self.voice = await channel.connect(**kwargs)
            log.info("Conectado al canal de voz '%s'", channel.name)
            return self.voice

    async def play(self, path: Path, *, ignore_cooldown: bool = False) -> bool:
        """Reproduce ``path``. Devuelve False si se descartó (cooldown o sin conexión)."""
        if not self.connected:
            log.warning("No estoy conectado a un canal de voz")
            return False
        now = time.monotonic()
        if not ignore_cooldown and now - self._last_play < self.config.cooldown_seconds:
            log.debug("Ignorado por cooldown: %s", path.name)
            return False
        self._last_play = now

        if self.voice.is_playing():
            self.voice.stop()
        source = discord.PCMVolumeTransformer(
            discord.FFmpegPCMAudio(str(path), executable=self._ffmpeg),
            volume=self.config.volume,
        )
        self.voice.play(source, after=lambda err: err and log.error("Error reproduciendo %s: %s", path.name, err))
        log.info("Reproduciendo %s", path.name)
        return True

    async def disconnect(self) -> None:
        if self.voice is not None:
            await self.voice.disconnect(force=True)
            self.voice = None
