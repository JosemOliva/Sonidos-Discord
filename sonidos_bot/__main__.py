"""Bot sin ventana: ``python -m sonidos_bot [--config RUTA] [--check]``.

La app normal (``SonidosBot.exe``) es el menú de ``wizard.py``, que lleva el
bot dentro; esto queda para ejecutarlo en consola o en un servidor.
"""

from __future__ import annotations

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__
from .config import ConfigError, app_data_dir, default_config_path, load_config


def setup_logging(debug: bool = False, extra: list[logging.Handler] | None = None) -> None:
    """Log a ``bot.log`` en la carpeta de datos, a la consola si la hay y a ``extra``."""
    handlers: list[logging.Handler] = list(extra or [])
    if sys.stderr is not None:  # el .exe sin consola no tiene stderr
        handlers.append(logging.StreamHandler())
    try:
        log_dir = app_data_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(log_dir / "bot.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
    except OSError:
        pass  # sin log en archivo, pero el bot funciona igual
    logging.basicConfig(
        level=logging.DEBUG if debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
        force=True,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sonidos_bot", description="Bot de sonidos para Discord")
    parser.add_argument("--config", type=Path, default=None, help=f"Ruta del config (por defecto {default_config_path()})")
    parser.add_argument("--check", action="store_true", help="Solo valida la configuración y sale")
    parser.add_argument("--debug", action="store_true", help="Logs detallados")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    setup_logging(debug=args.debug)
    log = logging.getLogger("sonidos_bot")

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ConfigError) as exc:
        log.error("%s", exc)
        log.error("Abre Sonidos Bot para corregirlo.")
        return 2

    log.info("Configuración OK (%s). Modos activos: %s", config.path, ", ".join(config.modes.enabled()))
    if args.check:
        return 0

    from .bot import SoundBot  # importa discord.py solo cuando hace falta

    SoundBot(config).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
