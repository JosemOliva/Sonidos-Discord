"""Lógica del menú de configuración que no depende de la interfaz gráfica.

Separada de ``wizard.py`` para poder probarla sin abrir ventanas.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
import time
import urllib.request
import zipfile
from pathlib import Path

from .config import Binding, ConfigError, app_data_dir, sound_key

VOSK_MODEL_NAME = "vosk-model-small-es-0.42"
VOSK_MODEL_URL = f"https://alphacephei.com/vosk/models/{VOSK_MODEL_NAME}.zip"

# Teclas de tkinter (keysym) que pynput nombra distinto.
_SPECIAL_KEYS = {
    "space": "<space>",
    "Return": "<enter>",
    "Escape": "<esc>",
    "Tab": "<tab>",
    "BackSpace": "<backspace>",
    "Delete": "<delete>",
    "Insert": "<insert>",
    "Home": "<home>",
    "End": "<end>",
    "Prior": "<page_up>",
    "Next": "<page_down>",
    "Up": "<up>",
    "Down": "<down>",
    "Left": "<left>",
    "Right": "<right>",
    "Pause": "<pause>",
    "Scroll_Lock": "<scroll_lock>",
}
_MODIFIER_KEYSYMS = {
    "Shift_L", "Shift_R", "Control_L", "Control_R", "Alt_L", "Alt_R",
    "Meta_L", "Meta_R", "Super_L", "Super_R", "Win_L", "Win_R", "ISO_Level3_Shift",
}

# Máscaras de event.state en tkinter. Alt es 0x20000 en Windows y Mod1 (0x8) en Linux.
_SHIFT, _CONTROL, _ALT_WIN, _ALT_X11 = 0x1, 0x4, 0x20000, 0x8


def tk_event_to_hotkey(keysym: str, state: int) -> str | None:
    """Convierte una pulsación de tkinter al formato de pynput.

    Devuelve None si solo se pulsó un modificador o si la tecla no se puede
    usar como atajo global (en ese caso se puede escribir a mano).
    """
    if keysym in _MODIFIER_KEYSYMS:
        return None
    if keysym in _SPECIAL_KEYS:
        key = _SPECIAL_KEYS[keysym]
    elif keysym.startswith("F") and keysym[1:].isdigit() and 1 <= int(keysym[1:]) <= 24:
        key = f"<{keysym.lower()}>"
    elif len(keysym) == 1 and keysym.isprintable():
        key = keysym.lower()
    else:
        return None

    parts = []
    if state & _CONTROL:
        parts.append("<ctrl>")
    if state & (_ALT_WIN | _ALT_X11):
        parts.append("<alt>")
    if state & _SHIFT:
        parts.append("<shift>")
    parts.append(key)
    return "+".join(parts)


def pretty_hotkey(hotkey: str | None) -> str:
    """"<ctrl>+<alt>+1" -> "Ctrl + Alt + 1", para mostrar en pantalla."""
    if not hotkey:
        return ""
    names = {"ctrl": "Ctrl", "alt": "Alt", "shift": "Shift", "cmd": "Win", "esc": "Esc", "enter": "Enter",
             "space": "Espacio", "page_up": "RePág", "page_down": "AvPág", "delete": "Supr", "insert": "Insert",
             "backspace": "Retroceso", "up": "↑", "down": "↓", "left": "←", "right": "→"}
    parts = []
    for part in hotkey.split("+"):
        name = part.strip("<>")
        parts.append(names.get(name, name.upper() if len(name) <= 3 else name.capitalize()))
    return " + ".join(parts)


def parse_keywords(text: str) -> list[str]:
    """"chiqui tapia, manda más" -> ["chiqui tapia", "manda más"]."""
    return [k.strip() for k in text.replace(";", ",").replace("\n", ",").split(",") if k.strip()]


def parse_discord_id(text: str, label: str) -> int:
    text = text.strip()
    if not text.isdigit():
        raise ConfigError([f"{label}: pega el ID numérico (clic derecho > Copiar ID)."])
    return int(text)


def binding_from_form(sound: str, hotkey: str, button: str, keywords: str) -> Binding:
    button = button.strip()
    if button and not button.isdigit():
        raise ConfigError([f"El botón de mando de '{sound}' debe ser un número (0, 1, 2...)."])
    return Binding(
        sound=sound.strip(),
        hotkey=hotkey.strip() or None,
        gamepad_button=int(button) if button else None,
        keywords=parse_keywords(keywords),
    )


def known_sounds(cache_dir: Path) -> list[str]:
    """Nombres de archivo que el bot ya descargó del canal (para el desplegable)."""
    index = cache_dir / "index.json"
    try:
        return sorted(e["filename"] for e in json.loads(index.read_text(encoding="utf-8")))
    except (OSError, ValueError, KeyError, TypeError):
        return []


def find_cached_sound(cache_dir: Path, sound: str) -> Path | None:
    """Archivo descargado por el bot para ese sonido, si existe (para el botón Probar)."""
    index = cache_dir / "index.json"
    try:
        entries = json.loads(index.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    wanted = sound_key(sound)
    for e in entries:
        if e.get("key") == wanted:
            path = cache_dir / e.get("file", "")
            return path if path.is_file() else None
    return None


def play_preview(path: Path, volume: float = 0.8) -> None:
    """Reproduce el sonido en los altavoces de esta PC (no en Discord)."""
    import os as _os

    _os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
    import pygame

    if not pygame.mixer.get_init():
        pygame.mixer.init()
    sound = pygame.mixer.Sound(str(path))
    sound.set_volume(max(0.0, min(1.0, volume)))
    sound.play()


def capture_gamepad_button(timeout: float = 10.0) -> int | None:
    """Espera a que se pulse cualquier botón de cualquier mando y devuelve su número.

    Si no se pulsa ningún botón, lanza un error que dice qué mandos ve Windows,
    para distinguir un mando no reconocido de un botón que no cuenta como tal.
    """
    from .triggers import xinput
    from .triggers.gamepad import buttons_down, init_pygame_joystick

    pygame = init_pygame_joystick()
    deadline = time.monotonic() + timeout
    sticks: list = []
    try:
        while time.monotonic() < deadline:
            pygame.event.pump()
            if pygame.joystick.get_count() != len(sticks):
                sticks = [pygame.joystick.Joystick(i) for i in range(pygame.joystick.get_count())]
            down = buttons_down(sticks)
            if down:
                return min(down)
            time.sleep(0.01)
        found = [(s.get_name(), s.get_numbuttons()) for s in sticks]
        if not found and xinput.connected_pads():
            found = [("Mando XInput", len(xinput.BUTTON_BITS))]
        raise RuntimeError(describe_no_button(found))
    finally:
        pygame.joystick.quit()


def describe_no_button(sticks: list[tuple[str, int]]) -> str:
    """Mensaje para cuando no se detecta un botón. ``sticks``: (nombre, número de botones)."""
    if not sticks:
        return ("Windows no muestra ningún mando conectado.\n"
                "Revisa el cable o el receptor y el modo del mando (debe estar en modo PC / X-input).")
    names = "\n".join(f"• {name} ({buttons} botones)" for name, buttons in sticks)
    return (f"Mandos detectados:\n{names}\n\n"
            "Pulsa un botón normal (A, B, X, Y, LB, RB, Start...). "
            "La cruceta y los gatillos LT/RT todavía no se pueden usar.")


def download_vosk_model(dest_dir: Path | None = None, progress=None) -> Path:
    """Descarga y descomprime el modelo de voz en español. Devuelve su carpeta."""
    dest_dir = dest_dir or app_data_dir() / "modelos"
    target = dest_dir / VOSK_MODEL_NAME
    if target.is_dir():
        return target
    dest_dir.mkdir(parents=True, exist_ok=True)
    zip_path = dest_dir / f"{VOSK_MODEL_NAME}.zip"

    def hook(blocks, block_size, total):
        if progress and total > 0:
            progress(min(1.0, blocks * block_size / total))

    urllib.request.urlretrieve(VOSK_MODEL_URL, zip_path, reporthook=hook)
    with zipfile.ZipFile(zip_path) as zf:
        zf.extractall(dest_dir)
    zip_path.unlink(missing_ok=True)
    return target


def bot_command() -> list[str]:
    """Comando para lanzar el bot, empaquetado o desde el código fuente."""
    if getattr(sys, "frozen", False):
        exe = Path(sys.executable).with_name("SonidosBot.exe")
        return [str(exe)]
    return [sys.executable, "-m", "sonidos_bot"]


def launch_bot() -> None:
    flags = getattr(subprocess, "CREATE_NEW_CONSOLE", 0)
    subprocess.Popen(bot_command(), creationflags=flags, close_fds=True)


def run_in_thread(target, on_done) -> threading.Thread:
    """Ejecuta ``target`` en segundo plano y llama ``on_done(resultado, error)``."""

    def runner():
        try:
            result, error = target(), None
        except Exception as exc:  # se muestra en la ventana
            result, error = None, exc
        on_done(result, error)

    thread = threading.Thread(target=runner, daemon=True)
    thread.start()
    return thread


def open_folder(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if sys.platform == "win32":
        os.startfile(path)  # type: ignore[attr-defined]
    else:
        subprocess.Popen(["xdg-open", str(path)])
