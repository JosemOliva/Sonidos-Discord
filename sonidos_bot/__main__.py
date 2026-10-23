"""Punto de entrada: ``python -m sonidos_bot [--config RUTA] [--check]``."""

from __future__ import annotations

import argparse
import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from . import __version__
from .config import ConfigError, app_data_dir, default_config_path, load_config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="sonidos_bot", description="Bot de sonidos para Discord")
    parser.add_argument("--config", type=Path, default=None, help=f"Ruta del config (por defecto {default_config_path()})")
    parser.add_argument("--check", action="store_true", help="Solo valida la configuración y sale")
    parser.add_argument("--debug", action="store_true", help="Logs detallados")
    parser.add_argument("--version", action="version", version=__version__)
    args = parser.parse_args(argv)

    handlers: list[logging.Handler] = [logging.StreamHandler()]
    try:
        log_dir = app_data_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(log_dir / "bot.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8"))
    except OSError:
        pass  # sin log en archivo, pero el bot funciona igual
    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        handlers=handlers,
    )
    log = logging.getLogger("sonidos_bot")

    try:
        config = load_config(args.config)
    except (FileNotFoundError, ConfigError) as exc:
        log.error("%s", exc)
        log.error("Abre 'Configurar Sonidos Bot' para corregirlo.")
        if getattr(sys, "frozen", False):
            input("Pulsa Enter para cerrar...")
        return 2

    log.info("Configuración OK (%s). Modos activos: %s", config.path, ", ".join(config.modes.enabled()))
    if args.check:
        return 0

    from .bot import SoundBot  # importa discord.py solo cuando hace falta

    SoundBot(config).run()
    return 0


if __name__ == "__main__":
    sys.exit(main())
