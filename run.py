"""Lanzador usado por PyInstaller y para ejecutar sin instalar el paquete."""

import sys

from sonidos_bot.__main__ import main

if __name__ == "__main__":
    sys.exit(main())
