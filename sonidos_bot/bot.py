"""Cliente de Discord que une configuración, biblioteca, reproductor y disparadores.

Flujo:
  1. Al conectarse, sincroniza la biblioteca desde el canal de sonidos.
  2. Entra al canal de voz configurado (y vuelve a entrar si lo sacan).
  3. Arranca los disparadores de los modos activos.
  4. Cada disparo busca el sonido y lo reproduce.

El config se vigila en disco: si se edita (a mano o desde el menú del
instalador) se recarga sin reiniciar el bot, así se pueden añadir o cambiar
palabras clave, teclas y sonidos en caliente.
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import tasks

from .config import Config, ConfigError, load_config, normalize_text
from .player import Player
from .sound_library import SoundLibrary
from .triggers import TRIGGERS, Trigger
from .triggers.text_keyword import TextKeywordTrigger

log = logging.getLogger("sonidos_bot.bot")

CONFIG_POLL_SECONDS = 5
REJOIN_DELAY_SECONDS = 5


def voice_client_class(config: Config) -> type[discord.VoiceProtocol] | None:
    """El modo por voz necesita un cliente que además reciba audio."""
    if not config.modes.voice_keyword:
        return None
    from discord.ext import voice_recv

    return voice_recv.VoiceRecvClient


class SoundBot(discord.Client):
    def __init__(self, config: Config):
        intents = discord.Intents.default()
        intents.message_content = True  # necesario para las palabras clave por texto
        intents.voice_states = True
        super().__init__(intents=intents)
        self.config = config
        self.tree = app_commands.CommandTree(self)
        self.library = SoundLibrary(config)
        self.player = Player(config, voice_client_class(config))
        self.triggers: list[Trigger] = []
        self._ready_once = False
        self._config_mtime = self._read_config_mtime()
        self._register_commands()

    # -- arranque -----------------------------------------------------------

    def run(self) -> None:  # type: ignore[override]
        super().run(self.config.discord.token, log_handler=None)

    async def setup_hook(self) -> None:
        guild = discord.Object(id=self.config.discord.guild_id)
        self.tree.copy_global_to(guild=guild)
        await self.tree.sync(guild=guild)
        self.library.load_cached()

    async def on_ready(self) -> None:
        log.info("Conectado como %s", self.user)
        if self._ready_once:  # on_ready se repite tras cada reconexión
            return
        self._ready_once = True
        await self._sync_library()
        await self._join_voice()
        await self._start_triggers()
        self._watch_config.start()

    async def close(self) -> None:
        await self._stop_triggers()
        await self.player.disconnect()
        await super().close()

    # -- piezas -------------------------------------------------------------

    def _guild(self) -> discord.Guild:
        guild = self.get_guild(self.config.discord.guild_id)
        if guild is None:
            raise RuntimeError("El bot no está en el servidor configurado (guild_id).")
        return guild

    async def _sync_library(self) -> None:
        guild = self._guild()
        channel = None
        if self.config.discord.sounds_channel_id:
            channel = guild.get_channel(self.config.discord.sounds_channel_id)
            if not isinstance(channel, (discord.TextChannel, discord.VoiceChannel)):
                log.error("sounds_channel_id no es un canal de texto del servidor, solo uso el panel de sonidos")
                channel = None
        try:
            soundboard = await guild.fetch_soundboard_sounds()
        except discord.DiscordException as exc:
            log.warning("No se pudo leer el panel de sonidos del servidor: %s", exc)
            soundboard = list(guild.soundboard_sounds)
        try:
            await self.library.sync(channel, soundboard)
        except discord.DiscordException as exc:
            log.error("No se pudieron descargar los sonidos, uso la caché local: %s", exc)

    async def _join_voice(self) -> None:
        channel = self._guild().get_channel(self.config.discord.voice_channel_id)
        if not isinstance(channel, (discord.VoiceChannel, discord.StageChannel)):
            log.error("voice_channel_id no es un canal de voz del servidor")
            return
        voice = await self.player.connect(channel)
        for trigger in self.triggers:
            trigger.voice_connected(voice)

    async def _start_triggers(self) -> None:
        loop = asyncio.get_running_loop()
        for mode in self.config.modes.enabled():
            trigger = TRIGGERS[mode](self.config, self.play_sound, loop)
            try:
                await trigger.start()
            except Exception:
                log.exception("No se pudo iniciar el modo '%s'", mode)
                continue
            self.triggers.append(trigger)
            if self.player.connected:
                trigger.voice_connected(self.player.voice)
            log.info("Modo '%s' activo", mode)

    async def _stop_triggers(self) -> None:
        for trigger in self.triggers:
            try:
                await trigger.stop()
            except Exception:
                log.exception("Error deteniendo '%s'", trigger.name)
        self.triggers.clear()

    async def play_sound(self, key: str, source: str, *, ignore_cooldown: bool = False) -> bool:
        path = self.library.get(key)
        if path is None:
            log.warning("[%s] No hay ningún sonido llamado '%s' en el canal", source, key)
            return False
        if not self.player.connected:
            await self._join_voice()
        return await self.player.play(path, ignore_cooldown=ignore_cooldown)

    # -- eventos ------------------------------------------------------------

    async def on_message(self, message: discord.Message) -> None:
        if message.author == self.user or message.guild is None:
            return
        if message.guild.id != self.config.discord.guild_id:
            return
        if message.channel.id == self.config.discord.sounds_channel_id:
            await self.library.add_from_message(message)
            return
        for trigger in self.triggers:
            if isinstance(trigger, TextKeywordTrigger):
                trigger.handle_message(message.content)

    async def on_soundboard_sound_create(self, sound) -> None:
        await self._soundboard_changed(sound)

    async def on_soundboard_sound_update(self, before, after) -> None:
        await self._soundboard_changed(after)

    async def on_soundboard_sound_delete(self, sound) -> None:
        await self._soundboard_changed(sound)

    async def _soundboard_changed(self, sound) -> None:
        if sound.guild is not None and sound.guild.id == self.config.discord.guild_id:
            log.info("Cambió el panel de sonidos (%s), vuelvo a sincronizar", sound.name)
            await self._sync_library()

    async def on_voice_state_update(self, member, before, after) -> None:
        if member.id != self.user.id or after.channel is not None:
            return
        log.warning("Salí del canal de voz, compruebo en %ds si hay que volver a entrar", REJOIN_DELAY_SECONDS)
        await asyncio.sleep(REJOIN_DELAY_SECONDS)
        # Si fue una recarga del config o el cierre del bot, ya está resuelto.
        if self.is_closed() or self.player.connected:
            return
        await self.player.disconnect()
        await self._join_voice()

    # -- recarga del config -------------------------------------------------

    def _read_config_mtime(self) -> float | None:
        try:
            return self.config.path.stat().st_mtime if self.config.path else None
        except OSError:
            return None

    @tasks.loop(seconds=CONFIG_POLL_SECONDS)
    async def _watch_config(self) -> None:
        mtime = self._read_config_mtime()
        if mtime is not None and mtime != self._config_mtime:
            self._config_mtime = mtime
            await self.reload_config()

    async def reload_config(self) -> str:
        try:
            new = load_config(self.config.path)
        except (FileNotFoundError, ConfigError) as exc:
            log.error("No recargo el config, sigo con el anterior: %s", exc)
            return f"El config tiene errores, sigo con el anterior:\n{exc}"

        old = self.config
        if new.discord.token != old.discord.token or new.discord.guild_id != old.discord.guild_id:
            log.warning("Cambiar el token o el servidor requiere reiniciar el bot")
        await self._stop_triggers()
        self.config = new
        self.library.config = new
        self.player.config = new

        if new.discord.sounds_channel_id != old.discord.sounds_channel_id:
            await self._sync_library()
        for missing in self.library.missing_bindings():
            log.warning("El sonido '%s' está en el config pero no en Discord", missing)

        new_cls = voice_client_class(new)
        if new.discord.voice_channel_id != old.discord.voice_channel_id or new_cls is not self.player.voice_client_cls:
            await self.player.disconnect()
            self.player.voice_client_cls = new_cls
            await self._join_voice()

        await self._start_triggers()
        log.info("Config recargado")
        return "Config recargado."

    # -- comandos /slash ----------------------------------------------------

    def _register_commands(self) -> None:
        @self.tree.command(name="sonidos", description="Lista los sonidos disponibles y cómo se activan")
        async def sonidos(interaction: discord.Interaction) -> None:
            lines = []
            bindings = {b.sound_key: b for b in self.config.bindings}
            for key in self.library.names():
                b = bindings.get(key)
                extra = []
                if b and b.keywords:
                    extra.append("palabras: " + ", ".join(f'"{k}"' for k in b.keywords))
                if b and b.hotkey:
                    extra.append(f"tecla: {b.hotkey}")
                if b and b.gamepad_button is not None:
                    extra.append(f"mando: botón {b.gamepad_button}")
                lines.append(f"• **{key}**" + (f" ({'; '.join(extra)})" if extra else ""))
            text = "\n".join(lines) or "No hay sonidos en el canal todavía."
            await interaction.response.send_message(text[:2000], ephemeral=True)

        @self.tree.command(name="tocar", description="Reproduce un sonido")
        @app_commands.describe(nombre="Nombre del sonido")
        async def tocar(interaction: discord.Interaction, nombre: str) -> None:
            ok = await self.play_sound(normalize_text(nombre), "comando", ignore_cooldown=True)
            msg = f"▶ {nombre}" if ok else f"No pude reproducir '{nombre}'."
            await interaction.response.send_message(msg, ephemeral=True)

        @tocar.autocomplete("nombre")
        async def tocar_autocomplete(interaction: discord.Interaction, current: str):
            current = normalize_text(current)
            return [app_commands.Choice(name=n, value=n) for n in self.library.names() if current in n][:25]

        @self.tree.command(name="recargar", description="Vuelve a leer el config y los sonidos del canal")
        async def recargar(interaction: discord.Interaction) -> None:
            await interaction.response.defer(ephemeral=True, thinking=True)
            result = await self.reload_config()
            await self._sync_library()
            await interaction.followup.send(f"{result} {len(self.library.names())} sonidos disponibles.", ephemeral=True)
