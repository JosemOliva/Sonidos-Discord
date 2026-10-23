"""Carga, validación y guardado de la configuración del bot.

La configuración vive en un único archivo JSON. Por defecto se guarda en la
carpeta de datos del usuario (``%APPDATA%\\SonidosBot`` en Windows) para que
el instalador pueda escribirla sin permisos de administrador y para que cada
PC tenga la suya.
"""

from __future__ import annotations

import json
import os
import sys
import unicodedata
from dataclasses import asdict, dataclass, field
from pathlib import Path

APP_NAME = "SonidosBot"
CONFIG_FILENAME = "config.json"
TOKEN_ENV_VAR = "SONIDOS_BOT_TOKEN"

VALID_MODES = ("keyboard", "gamepad", "text_keyword", "voice_keyword")
AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac", ".opus", ".webm"}


class ConfigError(ValueError):
    """La configuración existe pero tiene valores inválidos o incompletos."""

    def __init__(self, problems: list[str]):
        self.problems = problems
        super().__init__("Configuración inválida:\n  - " + "\n  - ".join(problems))


def app_data_dir() -> Path:
    """Carpeta donde se guardan la configuración, la caché de sonidos y los logs."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / APP_NAME
    base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / APP_NAME.lower()


def default_config_path() -> Path:
    return app_data_dir() / CONFIG_FILENAME


def normalize_text(text: str) -> str:
    """Minúsculas, sin tildes y con espacios simples.

    Se usa tanto para nombres de sonidos como para palabras clave, así
    "Chiqui  Tapía" y "chiqui tapia" se consideran iguales.
    """
    decomposed = unicodedata.normalize("NFKD", text)
    without_accents = "".join(c for c in decomposed if not unicodedata.combining(c))
    return " ".join(without_accents.lower().split())


def sound_key(filename: str) -> str:
    """Clave única de un sonido a partir de su nombre de archivo o del panel de sonidos.

    Discord cambia los espacios por guiones bajos al subir adjuntos, así que
    ``Chiqui Tapia.mp3`` y ``chiqui_tapia.mp3`` dan la misma clave. Solo se
    quita la extensión si es de audio, para que un nombre del panel de sonidos
    como ``Sr. Tapia`` no pierda nada.
    """
    path = Path(filename)
    stem = path.stem if path.suffix.lower() in AUDIO_EXTENSIONS else filename
    stem = stem.replace("_", " ").replace("-", " ")
    return normalize_text(stem)


@dataclass
class DiscordSettings:
    token: str = ""
    guild_id: int = 0
    voice_channel_id: int = 0
    sounds_channel_id: int = 0  # opcional: 0 = solo el panel de sonidos del servidor


@dataclass
class ModeSettings:
    keyboard: bool = True
    gamepad: bool = False
    text_keyword: bool = True
    voice_keyword: bool = False

    def enabled(self) -> list[str]:
        return [name for name in VALID_MODES if getattr(self, name)]


@dataclass
class Binding:
    """Asocia un sonido con lo que lo dispara en cada modo."""

    sound: str
    hotkey: str | None = None
    gamepad_button: int | None = None
    keywords: list[str] = field(default_factory=list)

    @property
    def sound_key(self) -> str:
        return sound_key(self.sound)


@dataclass
class Config:
    discord: DiscordSettings = field(default_factory=DiscordSettings)
    modes: ModeSettings = field(default_factory=ModeSettings)
    bindings: list[Binding] = field(default_factory=list)
    volume: float = 0.8
    cooldown_seconds: float = 2.0
    voice_model_path: str = ""
    path: Path | None = field(default=None, repr=False, compare=False)

    @property
    def cache_dir(self) -> Path:
        base = self.path.parent if self.path else app_data_dir()
        return base / "sonidos"

    def validate(self) -> None:
        problems: list[str] = []
        d = self.discord
        if not d.token:
            problems.append(f"Falta el token del bot (discord.token o variable {TOKEN_ENV_VAR}).")
        for name in ("guild_id", "voice_channel_id"):
            if getattr(d, name) <= 0:
                problems.append(f"discord.{name} debe ser el ID numérico de Discord.")
        if d.sounds_channel_id < 0:
            problems.append("discord.sounds_channel_id debe ser el ID numérico de Discord o 0.")

        if not self.modes.enabled():
            problems.append("Hay que activar al menos un modo en 'modes'.")
        if not 0.0 <= self.volume <= 2.0:
            problems.append("volume debe estar entre 0.0 y 2.0.")
        if self.cooldown_seconds < 0:
            problems.append("cooldown_seconds no puede ser negativo.")
        if self.modes.voice_keyword and not self.voice_model_path:
            problems.append("El modo voice_keyword necesita voice_model_path (modelo Vosk en español).")

        seen_hotkeys: dict[str, str] = {}
        seen_buttons: dict[int, str] = {}
        seen_keywords: dict[str, str] = {}
        for b in self.bindings:
            if not b.sound.strip():
                problems.append("Hay un binding sin nombre de sonido.")
                continue
            if b.hotkey is None and b.gamepad_button is None and not b.keywords:
                problems.append(f"El sonido '{b.sound}' no tiene ninguna tecla, botón ni palabra clave.")
            if b.hotkey:
                key = b.hotkey.lower().replace(" ", "")
                if key in seen_hotkeys:
                    problems.append(f"La tecla '{b.hotkey}' está repetida en '{seen_hotkeys[key]}' y '{b.sound}'.")
                seen_hotkeys[key] = b.sound
            if b.gamepad_button is not None:
                if b.gamepad_button < 0:
                    problems.append(f"El botón de mando de '{b.sound}' no puede ser negativo.")
                elif b.gamepad_button in seen_buttons:
                    problems.append(
                        f"El botón {b.gamepad_button} está repetido en '{seen_buttons[b.gamepad_button]}' y '{b.sound}'."
                    )
                seen_buttons[b.gamepad_button] = b.sound
            for kw in b.keywords:
                norm = normalize_text(kw)
                if not norm:
                    problems.append(f"El sonido '{b.sound}' tiene una palabra clave vacía.")
                elif norm in seen_keywords and seen_keywords[norm] != b.sound:
                    problems.append(f"La palabra clave '{kw}' está en '{seen_keywords[norm]}' y '{b.sound}'.")
                seen_keywords[norm] = b.sound

        if problems:
            raise ConfigError(problems)

    def to_dict(self) -> dict:
        data = asdict(self)
        data.pop("path")
        return data


def _from_dict(data: dict) -> Config:
    try:
        discord = DiscordSettings(**data.get("discord", {}))
        modes = ModeSettings(**data.get("modes", {}))
        bindings = [Binding(**b) for b in data.get("bindings", [])]
        extra = {k: data[k] for k in ("volume", "cooldown_seconds", "voice_model_path") if k in data}
    except TypeError as exc:  # clave desconocida o tipo incorrecto
        raise ConfigError([f"Formato inesperado: {exc}"]) from exc
    return Config(discord=discord, modes=modes, bindings=bindings, **extra)


def load_config(path: Path | None = None, *, validate: bool = True) -> Config:
    path = Path(path) if path else default_config_path()
    if not path.exists():
        raise FileNotFoundError(f"No existe {path}. Ejecuta el instalador o copia config.example.json.")
    with path.open(encoding="utf-8") as fh:
        try:
            data = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ConfigError([f"{path} no es un JSON válido: {exc}"]) from exc

    config = _from_dict(data)
    config.path = path
    # La variable de entorno permite no guardar el token en disco.
    env_token = os.environ.get(TOKEN_ENV_VAR)
    if env_token:
        config.discord.token = env_token
    if validate:
        config.validate()
    return config


def save_config(config: Config, path: Path | None = None) -> Path:
    path = Path(path or config.path or default_config_path())
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with tmp.open("w", encoding="utf-8") as fh:
        json.dump(config.to_dict(), fh, indent=2, ensure_ascii=False)
    tmp.replace(path)
    config.path = path
    return path
