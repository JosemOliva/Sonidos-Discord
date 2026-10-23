"""Búsqueda de palabras clave en un texto, compartida por texto y voz."""

from __future__ import annotations

import re

from ..config import Config, normalize_text


class KeywordMatcher:
    """Encuentra la primera palabra clave del config que aparece en un texto.

    Compara sin mayúsculas ni tildes y por palabras completas: "uruguayo"
    coincide en "que uruguayo che" pero no en "uruguayos". Las frases más
    largas se prueban primero, así "manda mas" gana sobre un "mas" suelto.
    """

    def __init__(self, config: Config):
        pairs = [(normalize_text(kw), b.sound_key) for b in config.bindings for kw in b.keywords]
        pairs = [(kw, key) for kw, key in pairs if kw]
        pairs.sort(key=lambda p: len(p[0]), reverse=True)
        self._patterns = [(re.compile(rf"(?<!\w){re.escape(kw)}(?!\w)"), key) for kw, key in pairs]

    def __bool__(self) -> bool:
        return bool(self._patterns)

    def find(self, text: str) -> str | None:
        """Devuelve la clave del sonido o None."""
        text = normalize_text(text)
        for pattern, key in self._patterns:
            if pattern.search(text):
                return key
        return None
