"""Palabras clave escritas en el chat de texto del servidor.

A diferencia de los otros disparadores no abre ningún dispositivo: el bot le
pasa cada mensaje recibido a ``handle_message``.
"""

from __future__ import annotations

from .base import Trigger
from .keywords import KeywordMatcher


class TextKeywordTrigger(Trigger):
    name = "text_keyword"

    async def start(self) -> None:
        self.matcher = KeywordMatcher(self.config)
        if not self.matcher:
            self.log.warning("No hay palabras clave configuradas")

    async def stop(self) -> None:
        pass

    def handle_message(self, content: str) -> None:
        key = self.matcher.find(content)
        if key:
            self.fire(key)
