"""La app Sonidos Bot: menú de configuración con el bot dentro.

Tema oscuro con los colores de Discord y una barra lateral con estas
secciones:
  Conexión: token e IDs del servidor y los canales.
  Modos:    teclado, mando, palabra clave por texto y por voz.
  Sonidos:  cada sonido con sus palabras clave, su tecla y su botón.
  Ajustes:  volumen, tiempo entre sonidos y carpeta de datos.
  Registro: lo que va haciendo el bot.

El bot corre en un hilo de esta misma ventana (ver ``runner.py``): se inicia
y se detiene con el botón de la barra lateral y se apaga al cerrar la
ventana, saliendo antes del canal de voz. Al guardar con el bot en marcha,
los cambios se aplican solos.

Opciones: ``--iniciar`` arranca el bot al abrir y ``--minimizado`` abre la
ventana minimizada (las usa el acceso directo de inicio con Windows).
"""

from __future__ import annotations

import argparse
import logging
import queue
import tkinter as tk
from tkinter import filedialog, messagebox

import customtkinter as ctk

from . import __version__
from .__main__ import setup_logging
from .config import (
    Binding,
    Config,
    ConfigError,
    app_data_dir,
    default_config_path,
    load_config,
    save_config,
)
from .wizard_helpers import (
    already_running,
    binding_from_form,
    capture_gamepad_button,
    download_vosk_model,
    fetch_soundboard_names,
    find_cached_sound,
    known_sounds,
    open_folder,
    parse_discord_id,
    play_preview,
    pretty_hotkey,
    run_in_thread,
    tk_event_to_hotkey,
)
from .runner import CONNECTED, ERROR, STARTING, STOPPED, BotRunner

# Paleta de Discord (modo oscuro) con acentos naranja.
BG = "#313338"
SIDEBAR = "#2B2D31"
CARD = "#2B2D31"
INPUT = "#1E1F22"
CHIP = "#404249"
TEXT = "#F2F3F5"
MUTED = "#B5BAC1"
ACCENT = "#F57C00"  # naranja principal (botones, deslizadores, progreso)
ACCENT_HOVER = "#D96C00"
GREEN = "#FF9800"  # naranja claro para "Guardar e iniciar" e interruptores encendidos
GREEN_HOVER = "#E68600"
RED = "#DA373C"
RED_HOVER = "#A12828"
GRAY_BTN = "#4E5058"
GRAY_HOVER = "#6D6F78"

DEFAULT_BINDINGS = [
    Binding(sound="chiqui_tapia.mp3", hotkey="<ctrl>+<alt>+1", gamepad_button=0, keywords=["chiqui tapia"]),
    Binding(sound="manda_mas.mp3", hotkey="<ctrl>+<alt>+2", gamepad_button=1, keywords=["manda mas"]),
    Binding(sound="uruguayo.mp3", hotkey="<ctrl>+<alt>+3", gamepad_button=2, keywords=["uruguayo"]),
]

MODES = [
    ("keyboard", "⌨", "Teclado", "Un atajo en esta PC reproduce el sonido, incluso dentro de un juego."),
    ("gamepad", "🎮", "Mando", "Un botón del mando conectado a esta PC reproduce el sonido."),
    ("text_keyword", "💬", "Palabra por texto", "Alguien escribe la palabra clave en el chat del servidor."),
    ("voice_keyword", "🎙", "Palabra por voz", "Alguien dice la palabra clave en el canal de voz."),
]

PAGES = [("conexion", "Conexión"), ("modos", "Modos"), ("sonidos", "Sonidos"), ("ajustes", "Ajustes"),
         ("registro", "Registro")]
MAX_LOG_LINES = 1000

BOT_STATES = {  # estado: (texto, color del punto, texto del botón)
    STOPPED: ("Bot detenido", MUTED, "▶  Guardar e iniciar bot"),
    STARTING: ("Conectando…", ACCENT, "■  Detener bot"),
    CONNECTED: ("Bot conectado", "#23A55A", "■  Detener bot"),
    ERROR: ("El bot se detuvo por un error", RED, "▶  Guardar e iniciar bot"),
}


def load_or_default() -> Config:
    try:
        return load_config(validate=False)
    except FileNotFoundError:
        config = Config(bindings=[Binding(**vars(b)) for b in DEFAULT_BINDINGS])
        config.modes.voice_keyword = True
        return config
    except ConfigError as exc:
        messagebox.showwarning("Config dañado", f"No se pudo leer el config, empiezo de cero.\n\n{exc}")
        return Config()


# -- piezas reutilizables -----------------------------------------------------


def font(size: int = 13, bold: bool = False) -> ctk.CTkFont:
    return ctk.CTkFont(size=size, weight="bold" if bold else "normal")


def card(parent, **kwargs) -> ctk.CTkFrame:
    return ctk.CTkFrame(parent, fg_color=CARD, corner_radius=10, **kwargs)


def field_label(parent, text: str) -> ctk.CTkLabel:
    """Etiqueta en mayúsculas pequeñas, como en los formularios de Discord."""
    return ctk.CTkLabel(parent, text=text.upper(), font=font(11, bold=True), text_color=MUTED, anchor="w")


def entry(parent, var: tk.StringVar, **kwargs) -> ctk.CTkEntry:
    return ctk.CTkEntry(parent, textvariable=var, fg_color=INPUT, border_width=0, height=36,
                        text_color=TEXT, corner_radius=6, **kwargs)


def button(parent, text: str, command, kind: str = "accent", **kwargs) -> ctk.CTkButton:
    colors = {
        "accent": (ACCENT, ACCENT_HOVER),
        "green": (GREEN, GREEN_HOVER),
        "red": (RED, RED_HOVER),
        "gray": (GRAY_BTN, GRAY_HOVER),
    }[kind]
    kwargs.setdefault("height", 34)
    return ctk.CTkButton(parent, text=text, command=command, fg_color=colors[0], hover_color=colors[1],
                         text_color=TEXT, corner_radius=6, font=font(13, bold=True), **kwargs)


def chip(parent, text: str) -> ctk.CTkLabel:
    return ctk.CTkLabel(parent, text=f"  {text}  ", fg_color=CHIP, corner_radius=12, text_color=TEXT,
                        font=font(12), height=24)


def page_header(parent, title: str, subtitle: str, wrap: int = 560) -> None:
    ctk.CTkLabel(parent, text=title, font=font(22, bold=True), text_color=TEXT, anchor="w").pack(
        fill="x", padx=28, pady=(24, 0))
    ctk.CTkLabel(parent, text=subtitle, font=font(13), text_color=MUTED, anchor="w", justify="left",
                 wraplength=wrap).pack(fill="x", padx=28, pady=(2, 14))


# -- ventana principal --------------------------------------------------------


class WindowLogHandler(logging.Handler):
    """Manda cada línea del log a la sección Registro (desde cualquier hilo)."""

    def __init__(self, window: "Wizard"):
        super().__init__(level=logging.INFO)
        self.window = window
        self.setFormatter(logging.Formatter("%(asctime)s  %(levelname)-7s %(message)s", "%H:%M:%S"))

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self.window.call_in_ui(self.window._append_log, self.format(record))
        except Exception:
            self.handleError(record)


class Wizard(ctk.CTk):
    def __init__(self, autostart: bool = False):
        ctk.set_appearance_mode("dark")
        super().__init__(fg_color=BG)
        self.title("Sonidos Bot")
        self.geometry("920x620")
        self.minsize(860, 560)
        self.config_data = load_or_default()
        self.bindings: list[Binding] = list(self.config_data.bindings)
        self._ui_queue: queue.Queue = queue.Queue()
        self.after(100, self._drain_ui_queue)

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)
        self._build_sidebar()

        self.pages: dict[str, ctk.CTkFrame] = {}
        builders = {"conexion": self._page_connection, "modos": self._page_modes,
                    "sonidos": self._page_sounds, "ajustes": self._page_settings,
                    "registro": self._page_log}
        for name, _ in PAGES:
            frame = ctk.CTkFrame(self, fg_color=BG, corner_radius=0)
            builders[name](frame)
            self.pages[name] = frame
        self.show_page("sonidos" if self.config_data.discord.token else "conexion")

        setup_logging(extra=[WindowLogHandler(self)])
        self.runner = BotRunner(on_state=lambda state, detail: self.call_in_ui(self._bot_state_changed, state, detail))
        self.protocol("WM_DELETE_WINDOW", self._on_close)
        if autostart and self.config_data.discord.token:
            self.after(300, lambda: self.save(start=True))

    # -- hilos --------------------------------------------------------------

    def call_in_ui(self, fn, *args) -> None:
        """Desde otro hilo: ejecuta ``fn`` en el hilo de la ventana."""
        self._ui_queue.put((fn, args))

    def _drain_ui_queue(self) -> None:
        while not self._ui_queue.empty():
            fn, args = self._ui_queue.get_nowait()
            fn(*args)
        self.after(100, self._drain_ui_queue)

    # -- barra lateral ------------------------------------------------------

    def _build_sidebar(self) -> None:
        side = ctk.CTkFrame(self, fg_color=SIDEBAR, corner_radius=0, width=220)
        side.grid(row=0, column=0, sticky="nsw")
        side.grid_propagate(False)
        side.grid_columnconfigure(0, weight=1)
        side.grid_rowconfigure(len(PAGES) + 2, weight=1)

        ctk.CTkLabel(side, text="🔊 Sonidos Bot", font=font(20, bold=True), text_color=TEXT, anchor="w").grid(
            row=0, column=0, sticky="we", padx=20, pady=(24, 0))
        ctk.CTkLabel(side, text=f"v{__version__}", font=font(12), text_color=MUTED, anchor="w").grid(
            row=1, column=0, sticky="we", padx=20, pady=(0, 20))

        self.nav: dict[str, ctk.CTkButton] = {}
        for i, (name, label) in enumerate(PAGES, start=2):
            b = ctk.CTkButton(side, text=label, anchor="w", height=38, corner_radius=6, font=font(14),
                              fg_color="transparent", hover_color=CHIP, text_color=MUTED,
                              command=lambda n=name: self.show_page(n))
            b.grid(row=i, column=0, sticky="we", padx=12, pady=2)
            self.nav[name] = b

        bottom = ctk.CTkFrame(side, fg_color="transparent")
        bottom.grid(row=len(PAGES) + 3, column=0, sticky="we", padx=12, pady=16)
        self.status = ctk.CTkLabel(bottom, text="Sin cambios guardados", font=font(11), text_color=MUTED,
                                   wraplength=190, justify="left", anchor="w")
        self.status.pack(fill="x", pady=(0, 8))
        self.bot_status = ctk.CTkLabel(bottom, text="●  Bot detenido", font=font(12, bold=True), text_color=MUTED,
                                       anchor="w")
        self.bot_status.pack(fill="x", pady=(0, 6))
        button(bottom, "Guardar", self.save, "accent").pack(fill="x", pady=3)
        self.bot_btn = button(bottom, "▶  Guardar e iniciar bot", self._toggle_bot, "green")
        self.bot_btn.pack(fill="x", pady=3)

    def show_page(self, name: str) -> None:
        for page_name, frame in self.pages.items():
            frame.grid_remove()
            self.nav[page_name].configure(fg_color="transparent", text_color=MUTED)
        self.pages[name].grid(row=0, column=1, sticky="nsew")
        self.nav[name].configure(fg_color=CHIP, text_color=TEXT)

    # -- Conexión -----------------------------------------------------------

    def _page_connection(self, page) -> None:
        page_header(page, "Conexión con Discord", "El bot necesita su token y saber en qué servidor y canales trabajar.")
        d = self.config_data.discord
        box = card(page)
        box.pack(fill="x", padx=28)
        box.grid_columnconfigure(0, weight=1)

        self.token = tk.StringVar(value=d.token)
        field_label(box, "Token del bot").grid(row=0, column=0, columnspan=2, sticky="we", padx=18, pady=(16, 4))
        token_entry = entry(box, self.token, show="•")
        token_entry.grid(row=1, column=0, sticky="we", padx=(18, 8))

        def toggle():
            hidden = token_entry.cget("show") == "•"
            token_entry.configure(show="" if hidden else "•")
            show_btn.configure(text="Ocultar" if hidden else "Mostrar")

        show_btn = button(box, "Mostrar", toggle, "gray", width=90)
        show_btn.grid(row=1, column=1, padx=(0, 18))

        self.ids: dict[str, tk.StringVar] = {}
        labels = [("guild_id", "ID del servidor"), ("voice_channel_id", "ID del canal de voz"),
                  ("sounds_channel_id", "ID del canal con los audios (opcional)")]
        for row, (name, label) in enumerate(labels, start=1):
            value = getattr(d, name)
            self.ids[name] = tk.StringVar(value=str(value) if value else "")
            field_label(box, label).grid(row=row * 2, column=0, columnspan=2, sticky="we", padx=18, pady=(14, 4))
            entry(box, self.ids[name], placeholder_text="123456789012345678").grid(
                row=row * 2 + 1, column=0, columnspan=2, sticky="we", padx=18)
        ctk.CTkFrame(box, fg_color="transparent", height=16).grid(row=99, column=0)

        help_box = card(page)
        help_box.pack(fill="x", padx=28, pady=14)
        ctk.CTkLabel(
            help_box, justify="left", anchor="w", font=font(12), text_color=MUTED, wraplength=560,
            text=("¿Dónde encuentro esto?\n"
                  "•  Token: discord.com/developers → tu aplicación → Bot → Reset Token.\n"
                  "•  IDs: en Discord, Ajustes → Avanzado → Modo desarrollador. "
                  "Luego clic derecho en el servidor o canal → Copiar ID.\n"
                  "•  Canal con los audios: déjalo vacío para usar solo el panel de sonidos del servidor. "
                  "Rellénalo si además quieres usar archivos subidos a un canal."),
        ).pack(fill="x", padx=18, pady=14)

    # -- Modos --------------------------------------------------------------

    def _page_modes(self, page) -> None:
        page_header(page, "Modos de activación",
                    "Elige cómo se disparan los sonidos. Puedes activar varios a la vez.")
        grid = ctk.CTkFrame(page, fg_color="transparent")
        grid.pack(fill="x", padx=28)
        grid.grid_columnconfigure((0, 1), weight=1, uniform="modes")

        self.modes: dict[str, tk.BooleanVar] = {}
        for i, (name, icon, title, desc) in enumerate(MODES):
            self.modes[name] = tk.BooleanVar(value=getattr(self.config_data.modes, name))
            box = card(grid)
            box.grid(row=i // 2, column=i % 2, sticky="nsew", padx=(0 if i % 2 == 0 else 7, 7 if i % 2 == 0 else 0), pady=7)
            box.grid_columnconfigure(1, weight=1)
            ctk.CTkLabel(box, text=icon, font=font(26), text_color=TEXT, width=40).grid(
                row=0, column=0, rowspan=2, padx=(16, 8), pady=16)
            ctk.CTkLabel(box, text=title, font=font(15, bold=True), text_color=TEXT, anchor="w").grid(
                row=0, column=1, sticky="we", pady=(16, 0))
            ctk.CTkLabel(box, text=desc, font=font(12), text_color=MUTED, anchor="w", justify="left",
                         wraplength=165).grid(row=1, column=1, sticky="we", pady=(0, 16))
            ctk.CTkSwitch(box, text="", variable=self.modes[name], width=46, progress_color=GREEN,
                          command=self._on_modes_changed).grid(row=0, column=2, rowspan=2, padx=16)

        voice = card(page)
        voice.pack(fill="x", padx=28, pady=(7, 0))
        voice.grid_columnconfigure(0, weight=1)
        field_label(voice, "Modelo de voz en español (para 'Palabra por voz')").grid(
            row=0, column=0, columnspan=2, sticky="we", padx=18, pady=(16, 4))
        self.model_path = tk.StringVar(value=self.config_data.voice_model_path)
        self.model_entry = entry(voice, self.model_path, placeholder_text="Carpeta del modelo Vosk")
        self.model_entry.grid(row=1, column=0, sticky="we", padx=(18, 8))
        self.browse_btn = button(voice, "Examinar…", self._browse_model, "gray", width=110)
        self.browse_btn.grid(row=1, column=1, padx=(0, 18))
        self.download_btn = button(voice, "⬇  Descargar modelo (~40 MB)", self._download_model, "accent")
        self.download_btn.grid(row=2, column=0, sticky="w", padx=18, pady=(10, 16))
        self.download_progress = ctk.CTkProgressBar(voice, progress_color=ACCENT, fg_color=INPUT, width=160)
        self.download_progress.set(0)
        self.download_progress.grid(row=2, column=1, padx=(0, 18), pady=(10, 16))
        self._update_voice_box()

    def _on_modes_changed(self) -> None:
        self._update_voice_box()
        self._refresh_sounds()

    def _update_voice_box(self) -> None:
        state = "normal" if self.modes["voice_keyword"].get() else "disabled"
        for widget in (self.model_entry, self.browse_btn, self.download_btn):
            widget.configure(state=state)

    def _browse_model(self) -> None:
        folder = filedialog.askdirectory(title="Carpeta del modelo Vosk")
        if folder:
            self.model_path.set(folder)

    def _download_model(self, then=None) -> None:
        """Descarga el modelo de voz; ``then`` se llama al terminar bien."""
        self._after_download = then
        self.download_btn.configure(state="disabled", text="Descargando…")
        progress = lambda fraction: self.call_in_ui(self.download_progress.set, fraction)
        done = lambda path, error: self.call_in_ui(self._download_finished, path, error)
        run_in_thread(lambda: download_vosk_model(progress=progress), done)

    def _download_finished(self, path, error) -> None:
        self.download_btn.configure(state="normal", text="⬇  Descargar modelo (~40 MB)")
        if error:
            messagebox.showerror("Error", f"No se pudo descargar el modelo:\n{error}")
            return
        self.download_progress.set(1)
        self.model_path.set(str(path))
        then, self._after_download = getattr(self, "_after_download", None), None
        if then is not None:
            then()

    # -- Sonidos ------------------------------------------------------------

    def _page_sounds(self, page) -> None:
        top = ctk.CTkFrame(page, fg_color="transparent")
        top.pack(fill="x")
        page_header(top, "Sonidos", "Cada sonido sale del panel de sonidos del servidor o del canal de audios. "
                                    "Las palabras clave sirven igual para texto y para voz.", wrap=440)
        button(top, "+  Añadir sonido", self._add_binding, "accent").place(relx=1.0, x=-28, y=28, anchor="ne")
        self.sound_list = ctk.CTkScrollableFrame(page, fg_color="transparent")
        self.sound_list.pack(fill="both", expand=True, padx=20, pady=(0, 16))
        self._refresh_sounds()

    def _refresh_sounds(self) -> None:
        for child in self.sound_list.winfo_children():
            child.destroy()
        if not self.bindings:
            ctk.CTkLabel(self.sound_list, text="Todavía no hay sonidos. Pulsa «Añadir sonido».",
                         font=font(14), text_color=MUTED).pack(pady=40)
            return
        modes = {name: var.get() for name, var in self.modes.items()} if hasattr(self, "modes") else {}
        for index, b in enumerate(self.bindings):
            self._sound_card(index, b, modes)

    def _sound_card(self, index: int, b: Binding, modes: dict[str, bool]) -> None:
        box = card(self.sound_list)
        box.pack(fill="x", padx=8, pady=6)
        box.grid_columnconfigure(0, weight=1)

        title = b.sound.rsplit(".", 1)[0].replace("_", " ").strip().capitalize()
        ctk.CTkLabel(box, text=title, font=font(16, bold=True), text_color=TEXT, anchor="w").grid(
            row=0, column=0, sticky="we", padx=18, pady=(14, 0))
        ctk.CTkLabel(box, text=b.sound, font=font(11), text_color=MUTED, anchor="w").grid(
            row=1, column=0, sticky="we", padx=18)

        chips = ctk.CTkFrame(box, fg_color="transparent")
        chips.grid(row=2, column=0, sticky="w", padx=14, pady=(8, 14))
        items = []
        if modes.get("text_keyword", True) or modes.get("voice_keyword", True):
            items += [f"💬 {k}" for k in b.keywords]
        if modes.get("keyboard", True) and b.hotkey:
            items.append(f"⌨ {pretty_hotkey(b.hotkey)}")
        if modes.get("gamepad", True) and b.gamepad_button is not None:
            items.append(f"🎮 Botón {b.gamepad_button}")
        for text in items or ["Sin disparadores en los modos activos"]:
            chip(chips, text).pack(side="left", padx=4)

        actions = ctk.CTkFrame(box, fg_color="transparent")
        actions.grid(row=0, column=1, rowspan=3, padx=14)
        button(actions, "▶ Probar", lambda: self._preview(b), "gray", width=86).pack(side="left", padx=3)
        button(actions, "Editar", lambda: self._edit_binding(index), "gray", width=70).pack(side="left", padx=3)
        button(actions, "✕", lambda: self._remove_binding(index), "red", width=36).pack(side="left", padx=3)

    def _preview(self, b: Binding) -> None:
        path = find_cached_sound(self.config_data.cache_dir, b.sound)
        if path is None:
            messagebox.showinfo("Probar", f"No encuentro '{b.sound}' entre los sonidos descargados.\n\n"
                                          "Pulsa Editar y elige un nombre del desplegable (los del panel de "
                                          "sonidos del servidor). Si la lista está vacía, inicia el bot una vez "
                                          "para que descargue los sonidos.")
            return
        try:
            play_preview(path, volume=self.volume.get() / 100)
        except Exception as exc:
            messagebox.showerror("Probar", f"No se pudo reproducir:\n{exc}")

    def _add_binding(self) -> None:
        result = BindingDialog(self, None).result
        if result:
            self.bindings.append(result)
            self._refresh_sounds()

    def _edit_binding(self, index: int) -> None:
        result = BindingDialog(self, self.bindings[index]).result
        if result:
            self.bindings[index] = result
            self._refresh_sounds()

    def _remove_binding(self, index: int) -> None:
        if messagebox.askyesno("Quitar", f"¿Quitar '{self.bindings[index].sound}'?"):
            del self.bindings[index]
            self._refresh_sounds()

    # -- Ajustes ------------------------------------------------------------

    def _page_settings(self, page) -> None:
        page_header(page, "Ajustes", "Cómo suenan los sonidos en el canal de voz.")
        box = card(page)
        box.pack(fill="x", padx=28)
        box.grid_columnconfigure(0, weight=1)

        self.volume = tk.IntVar(value=round(self.config_data.volume * 100))
        field_label(box, "Volumen").grid(row=0, column=0, sticky="we", padx=18, pady=(16, 4))
        volume_label = ctk.CTkLabel(box, text=f"{self.volume.get()} %", font=font(13, bold=True), text_color=TEXT)
        volume_label.grid(row=1, column=1, padx=18)
        ctk.CTkSlider(box, from_=0, to=200, number_of_steps=40, variable=self.volume, button_color=ACCENT,
                      button_hover_color=ACCENT_HOVER, progress_color=ACCENT,
                      command=lambda v: volume_label.configure(text=f"{round(v)} %")).grid(
            row=1, column=0, sticky="we", padx=18)

        self.cooldown = tk.DoubleVar(value=self.config_data.cooldown_seconds)
        field_label(box, "Tiempo mínimo entre sonidos").grid(row=2, column=0, sticky="we", padx=18, pady=(18, 4))
        cooldown_label = ctk.CTkLabel(box, text=f"{self.cooldown.get():.1f} s", font=font(13, bold=True),
                                      text_color=TEXT)
        cooldown_label.grid(row=3, column=1, padx=18)
        ctk.CTkSlider(box, from_=0, to=10, number_of_steps=20, variable=self.cooldown, button_color=ACCENT,
                      button_hover_color=ACCENT_HOVER, progress_color=ACCENT,
                      command=lambda v: cooldown_label.configure(text=f"{v:.1f} s")).grid(
            row=3, column=0, sticky="we", padx=18, pady=(0, 18))

        files = card(page)
        files.pack(fill="x", padx=28, pady=14)
        field_label(files, "Archivos").pack(fill="x", padx=18, pady=(16, 4))
        ctk.CTkLabel(files, text=str(default_config_path()), font=font(12), text_color=MUTED, anchor="w").pack(
            fill="x", padx=18)
        row = ctk.CTkFrame(files, fg_color="transparent")
        row.pack(fill="x", padx=14, pady=(8, 16))
        button(row, "Abrir carpeta de datos", lambda: open_folder(app_data_dir()), "gray").pack(side="left", padx=4)
        button(row, "Ver registro del bot", self._open_log, "gray").pack(side="left", padx=4)

    def _open_log(self) -> None:
        log = app_data_dir() / "bot.log"
        if not log.exists():
            messagebox.showinfo("Registro", "Todavía no hay registro: el bot no se ha iniciado.")
            return
        open_folder(log.parent)

    # -- Registro -----------------------------------------------------------

    def _page_log(self, page) -> None:
        page_header(page, "Registro", "Lo que va haciendo el bot. Si algo no funciona, mira aquí primero.")
        self.log_box = ctk.CTkTextbox(page, fg_color=INPUT, text_color=TEXT, font=ctk.CTkFont(family="Consolas",
                                      size=12), corner_radius=8, wrap="word")
        self.log_box.pack(fill="both", expand=True, padx=28, pady=(0, 20))
        self.log_box.configure(state="disabled")

    def _append_log(self, line: str) -> None:
        box = self.log_box
        at_bottom = box.yview()[1] > 0.98
        box.configure(state="normal")
        box.insert("end", line + "\n")
        lines = int(box.index("end-1c").split(".")[0])
        if lines > MAX_LOG_LINES:
            box.delete("1.0", f"{lines - MAX_LOG_LINES}.0")
        box.configure(state="disabled")
        if at_bottom:
            box.see("end")

    # -- bot ----------------------------------------------------------------

    def _toggle_bot(self) -> None:
        if self.runner.running:
            self.bot_btn.configure(state="disabled", text="Deteniendo…")
            run_in_thread(self.runner.stop, lambda *_: None)
        else:
            self.save(start=True)

    def _bot_state_changed(self, state: str, detail: str) -> None:
        text, color, button_text = BOT_STATES[state]
        if state == CONNECTED and detail:
            text = f"Conectado como {detail}"
        self.bot_status.configure(text=f"●  {text}", text_color=color)
        if self.bot_btn.cget("text") != "Cerrando…":
            self.bot_btn.configure(state="normal", text=button_text)
        if state == ERROR:
            messagebox.showerror("El bot se detuvo", f"{detail}\n\nMás detalles en la sección Registro.")

    def _on_close(self) -> None:
        """Al cerrar la ventana, el bot sale del canal de voz y se apaga."""
        if not self.runner.running:
            self.destroy()
            return
        self.bot_btn.configure(state="disabled", text="Cerrando…")
        self.status.configure(text="Saliendo del canal de voz…", text_color=MUTED)
        run_in_thread(self.runner.stop, lambda *_: self.call_in_ui(self.destroy))

    # -- guardar ------------------------------------------------------------

    def build_config(self) -> Config:
        problems = []
        ids = {}
        labels = {"guild_id": "Servidor", "voice_channel_id": "Canal de voz", "sounds_channel_id": "Canal de audios"}
        for name, var in self.ids.items():
            if name == "sounds_channel_id" and not var.get().strip():
                ids[name] = 0  # opcional
                continue
            try:
                ids[name] = parse_discord_id(var.get(), labels[name])
            except ConfigError as exc:
                problems += exc.problems
                ids[name] = 0
        id_errors = bool(problems)

        config = Config(bindings=list(self.bindings), volume=self.volume.get() / 100,
                        cooldown_seconds=round(float(self.cooldown.get()), 1),
                        voice_model_path=self.model_path.get().strip())
        config.discord.token = self.token.get().strip()
        for name, value in ids.items():
            setattr(config.discord, name, value)
        for name, var in self.modes.items():
            setattr(config.modes, name, var.get())
        try:
            config.validate()
        except ConfigError as exc:
            # Los IDs mal escritos ya se explicaron arriba con un mensaje más claro.
            problems += [p for p in exc.problems if not (id_errors and p.startswith("discord."))]
        if problems:
            raise ConfigError(list(dict.fromkeys(problems)))
        return config

    def save(self, start: bool = False) -> None:
        if self.modes["voice_keyword"].get() and not self.model_path.get().strip():
            if messagebox.askyesno("Modelo de voz", "Palabra por voz necesita el modelo de voz en español (~40 MB).\n\n"
                                                    "¿Lo descargo ahora y guardo al terminar?"):
                self.show_page("modos")
                self._download_model(then=lambda: self.save(start))
            return
        try:
            config = self.build_config()
        except ConfigError as exc:
            messagebox.showerror("Revisa la configuración", "\n".join(f"• {p}" for p in exc.problems))
            return
        save_config(config, default_config_path())
        config = load_config(default_config_path())  # con la ruta, para que el bot vigile el archivo
        self.status.configure(text="✓ Guardado", text_color=GREEN)
        if self.runner.running:
            if self.runner.needs_restart(config):
                self.status.configure(text="✓ Guardado. Reinicio el bot para usar el nuevo token o servidor.")
                runner = self.runner
                run_in_thread(lambda: (runner.stop(), runner.start(config)), lambda *_: None)
            else:
                self.status.configure(text="✓ Guardado. El bot aplica los cambios en unos segundos.")
        elif start:
            self.runner.start(config)


# -- ventana de sonido ---------------------------------------------------------


class BindingDialog(ctk.CTkToplevel):
    """Ventana para crear o editar un sonido con sus disparadores."""

    def __init__(self, parent: Wizard, binding: Binding | None):
        super().__init__(parent, fg_color=BG)
        self.parent = parent
        self.result: Binding | None = None
        self.title("Editar sonido" if binding else "Añadir sonido")
        self.transient(parent)
        self.resizable(False, False)
        b = binding or Binding(sound="")
        self.hotkey_value = b.hotkey
        self.button_value = b.gamepad_button

        ctk.CTkLabel(self, text=self.title(), font=font(20, bold=True), text_color=TEXT, anchor="w").pack(
            fill="x", padx=24, pady=(20, 10))
        body = card(self)
        body.pack(fill="x", padx=24)
        body.grid_columnconfigure(0, weight=1)

        field_label(body, "Sonido (nombre en el panel de sonidos o archivo del canal)").grid(
            row=0, column=0, columnspan=3, sticky="we", padx=18, pady=(16, 4))
        self.sound = ctk.CTkComboBox(body, values=known_sounds(parent.config_data.cache_dir) or [""], height=36,
                                     fg_color=INPUT, border_width=0, button_color=CHIP, text_color=TEXT,
                                     dropdown_fg_color=INPUT, width=420)
        self.sound.set(b.sound)
        self.sound.grid(row=1, column=0, columnspan=3, sticky="we", padx=18)
        self._load_soundboard_names()

        field_label(body, "Palabras clave · texto y voz (separadas por comas)").grid(
            row=2, column=0, columnspan=3, sticky="we", padx=18, pady=(14, 4))
        self.keywords = tk.StringVar(value=", ".join(b.keywords))
        entry(body, self.keywords, placeholder_text="chiqui tapia, chiqui").grid(
            row=3, column=0, columnspan=3, sticky="we", padx=18)

        field_label(body, "Tecla").grid(row=4, column=0, columnspan=3, sticky="we", padx=18, pady=(14, 4))
        self.hotkey_label = chip(body, "")
        self.hotkey_label.grid(row=5, column=0, sticky="w", padx=18)
        self.hotkey_btn = button(body, "Detectar", self._capture_hotkey, "accent", width=90)
        self.hotkey_btn.grid(row=5, column=1, padx=4)
        button(body, "Quitar", lambda: self._set_hotkey(None), "gray", width=70).grid(row=5, column=2, padx=(4, 18))

        field_label(body, "Botón del mando").grid(row=6, column=0, columnspan=3, sticky="we", padx=18, pady=(14, 4))
        self.button_label = chip(body, "")
        self.button_label.grid(row=7, column=0, sticky="w", padx=18, pady=(0, 18))
        self.button_btn = button(body, "Detectar", self._capture_button, "accent", width=90)
        self.button_btn.grid(row=7, column=1, padx=4, pady=(0, 18))
        button(body, "Quitar", lambda: self._set_button(None), "gray", width=70).grid(
            row=7, column=2, padx=(4, 18), pady=(0, 18))

        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.pack(fill="x", padx=24, pady=16)
        button(actions, "Guardar sonido", self._accept, "accent").pack(side="right", padx=4)
        button(actions, "Cancelar", self.destroy, "gray").pack(side="right", padx=4)

        self._set_hotkey(self.hotkey_value)
        self._set_button(self.button_value)
        self.after(150, self._make_modal)
        self.wait_window()

    def _make_modal(self) -> None:
        if self.winfo_exists():
            self.grab_set()
            self.focus_set()

    def _set_hotkey(self, value: str | None) -> None:
        self.hotkey_value = value
        self.hotkey_label.configure(text=f"  ⌨ {pretty_hotkey(value)}  " if value else "  Sin tecla  ")

    def _set_button(self, value: int | None) -> None:
        self.button_value = value
        self.button_label.configure(text=f"  🎮 Botón {value}  " if value is not None else "  Sin botón  ")

    def _capture_hotkey(self) -> None:
        self.hotkey_label.configure(text="  Pulsa la combinación…  ")
        self.hotkey_btn.configure(state="disabled")

        def on_key(event):
            hotkey = tk_event_to_hotkey(event.keysym, event.state)
            if hotkey is None:
                return  # solo un modificador: seguir esperando
            self.unbind("<KeyPress>")
            self.hotkey_btn.configure(state="normal")
            self._set_hotkey(hotkey)

        self.bind("<KeyPress>", on_key)
        self.focus_set()

    def _load_soundboard_names(self) -> None:
        """Añade al desplegable los sonidos del panel del servidor, sin bloquear la ventana."""
        token = self.parent.token.get().strip()
        guild = self.parent.ids["guild_id"].get().strip()
        if not token or not guild.isdigit():
            return
        done = lambda names, error: self.parent.call_in_ui(self._soundboard_names_loaded, names, error)
        run_in_thread(lambda: fetch_soundboard_names(token, int(guild)), done)

    def _soundboard_names_loaded(self, names, error) -> None:
        if error or not names or not self.winfo_exists():
            return  # sin conexión o sin panel: queda lo que ya había en caché
        current = [v for v in self.sound.cget("values") if v]
        self.sound.configure(values=sorted(set(current) | set(names)))

    def _capture_button(self) -> None:
        self.button_label.configure(text="  Pulsa un botón del mando…  ")
        self.button_btn.configure(state="disabled")
        done = lambda value, error: self.parent.call_in_ui(self._button_captured, value, error)
        run_in_thread(capture_gamepad_button, done)

    def _button_captured(self, value, error) -> None:
        if not self.winfo_exists():
            return
        self.button_btn.configure(state="normal")
        if error or value is None:
            self._set_button(self.button_value)
            messagebox.showwarning("Mando", f"No se detectó ningún botón.\n\n{error or 'Conecta el mando y vuelve a probar.'}",
                                   parent=self)
            return
        self._set_button(value)

    def _accept(self) -> None:
        sound = self.sound.get().strip()
        if not sound:
            messagebox.showerror("Falta el sonido", "Escribe el nombre del archivo de audio.", parent=self)
            return
        button_text = "" if self.button_value is None else str(self.button_value)
        try:
            self.result = binding_from_form(sound, self.hotkey_value or "", button_text, self.keywords.get())
        except ConfigError as exc:
            messagebox.showerror("Error", "\n".join(exc.problems), parent=self)
            return
        self.destroy()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(prog="SonidosBot", description="Bot de sonidos para Discord")
    parser.add_argument("--iniciar", action="store_true", help="Inicia el bot al abrir")
    parser.add_argument("--minimizado", action="store_true", help="Abre la ventana minimizada")
    args = parser.parse_args(argv)
    if already_running():
        root = tk.Tk()
        root.withdraw()
        messagebox.showinfo("Sonidos Bot", "Sonidos Bot ya está abierto. Búscalo en la barra de tareas.")
        root.destroy()
        return
    app = Wizard(autostart=args.iniciar)
    if args.minimizado:
        app.iconify()
    app.mainloop()


if __name__ == "__main__":
    main()
