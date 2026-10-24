"""Lanzador de la app (``SonidosBot.exe``): el menú con el bot dentro."""

import os
import sys

# El .exe sin consola no tiene stdout/stderr; algunas librerías escriben ahí igual.
if sys.stdout is None:
    sys.stdout = open(os.devnull, "w")
if sys.stderr is None:
    sys.stderr = open(os.devnull, "w")

from sonidos_bot.wizard import main  # noqa: E402

if __name__ == "__main__":
    main(sys.argv[1:])
