"""Biblioteca de sonidos: descarga los audios de Discord y los cachea.

Los sonidos salen de dos sitios: el panel de sonidos (soundboard) del
servidor y, si está configurado, los adjuntos de audio del canal
``sounds_channel_id``. Todo se guarda en ``config.cache_dir``. Un sonido del
panel se llama como en Discord (``El Manda Mas`` -> ``el manda mas``); si
coincide con un adjunto del canal, gana el adjunto.
 Cada adjunto se identifica por su nombre de archivo sin
extensión, normalizado (``Chiqui Tapia.mp3`` -> ``chiqui tapia``). Si el mismo
nombre aparece varias veces en el canal, gana el mensaje más reciente, así que
para cambiar un sonido basta con volver a subirlo con el mismo nombre.

Un ``index.json`` en la caché recuerda qué adjunto corresponde a cada archivo,
para no volver a descargar lo que no cambió y para poder arrancar con la
última copia si Discord no responde.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from .config import AUDIO_EXTENSIONS, Config, sound_key

INDEX_FILENAME = "index.json"

log = logging.getLogger("sonidos_bot.library")


@dataclass
class CachedSound:
    key: str
    filename: str
    attachment_id: int
    file: str  # nombre del archivo dentro de la caché


def is_audio(attachment) -> bool:
    content_type = (getattr(attachment, "content_type", None) or "").lower()
    return content_type.startswith("audio/") or Path(attachment.filename).suffix.lower() in AUDIO_EXTENSIONS


class SoundboardItem:
    """Envuelve un sonido del panel para descargarlo igual que un adjunto."""

    def __init__(self, sound):
        self.id = sound.id
        self.filename = sound.name
        self._sound = sound

    async def save(self, path: Path) -> None:
        data = await self._sound.read()
        path.write_bytes(data)

    @staticmethod
    def suffix() -> str:
        # Discord guarda los sonidos del panel en MP3 u OGG; FFmpeg y pygame
        # reconocen el formato por el contenido, la extensión da igual.
        return ".audio"


class SoundLibrary:
    def __init__(self, config: Config):
        self.config = config
        self.cache_dir = config.cache_dir
        self._entries: dict[str, CachedSound] = {}

    # -- consulta -----------------------------------------------------------

    def get(self, key: str) -> Path | None:
        entry = self._entries.get(key)
        if entry is None:
            return None
        path = self.cache_dir / entry.file
        return path if path.exists() else None

    def names(self) -> list[str]:
        return sorted(self._entries)

    def missing_bindings(self) -> list[str]:
        """Sonidos del config que no están en Discord."""
        return [b.sound for b in self.config.bindings if b.sound_key not in self._entries]

    # -- índice local -------------------------------------------------------

    def load_cached(self) -> None:
        """Carga lo que ya estaba descargado, sin tocar Discord."""
        index = self.cache_dir / INDEX_FILENAME
        if not index.exists():
            return
        try:
            data = json.loads(index.read_text(encoding="utf-8"))
            entries = {d["key"]: CachedSound(**d) for d in data}
        except (ValueError, TypeError, KeyError) as exc:
            log.warning("Índice de caché dañado, se descargará todo de nuevo: %s", exc)
            return
        self._entries = {k: e for k, e in entries.items() if (self.cache_dir / e.file).exists()}
        log.info("%d sonidos en caché local", len(self._entries))

    def _save_index(self) -> None:
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        data = [asdict(e) for e in self._entries.values()]
        tmp = self.cache_dir / (INDEX_FILENAME + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.cache_dir / INDEX_FILENAME)

    # -- sincronización con Discord ----------------------------------------

    async def sync(self, channel=None, soundboard=()) -> None:
        """Deja la caché igual a lo que hay en el panel de sonidos y en el canal."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        found: dict[str, object] = {}
        if channel is not None:
            async for message in channel.history(limit=None, oldest_first=False):
                for attachment in message.attachments:
                    if not is_audio(attachment):
                        continue
                    key = sound_key(attachment.filename)
                    found.setdefault(key, attachment)  # el más reciente primero
        for sound in soundboard:
            found.setdefault(sound_key(sound.name), SoundboardItem(sound))

        new_entries: dict[str, CachedSound] = {}
        for key, attachment in found.items():
            new_entries[key] = await self._ensure_downloaded(key, attachment)

        stale = {e.file for e in self._entries.values()} - {e.file for e in new_entries.values()}
        for name in stale:
            (self.cache_dir / name).unlink(missing_ok=True)

        self._entries = new_entries
        self._save_index()
        log.info("Biblioteca sincronizada: %d sonidos (%s)", len(self._entries), ", ".join(self.names()))
        for missing in self.missing_bindings():
            log.warning("El sonido '%s' está en el config pero no en Discord", missing)

    async def add_from_message(self, message) -> list[str]:
        """Agrega los audios de un mensaje nuevo del canal. Devuelve las claves añadidas."""
        added = []
        for attachment in message.attachments:
            if is_audio(attachment):
                key = sound_key(attachment.filename)
                old = self._entries.get(key)
                self._entries[key] = await self._ensure_downloaded(key, attachment)
                if old and old.file != self._entries[key].file:
                    (self.cache_dir / old.file).unlink(missing_ok=True)
                added.append(key)
        if added:
            self._save_index()
            log.info("Sonidos nuevos o actualizados: %s", ", ".join(added))
        return added

    async def _ensure_downloaded(self, key: str, attachment) -> CachedSound:
        if isinstance(attachment, SoundboardItem):
            suffix = attachment.suffix()
        else:
            suffix = Path(attachment.filename).suffix.lower() or ".audio"
        file = f"{attachment.id}{suffix}"
        path = self.cache_dir / file
        current = self._entries.get(key)
        if not (current and current.attachment_id == attachment.id and path.exists()):
            log.info("Descargando %s", attachment.filename)
            await attachment.save(path)
        return CachedSound(key=key, filename=attachment.filename, attachment_id=attachment.id, file=file)
