"""Registro de disparadores disponibles, indexados por el nombre del modo."""

from __future__ import annotations

from .base import PlayCallback, Trigger
from .gamepad import GamepadTrigger
from .keyboard import KeyboardTrigger
from .text_keyword import TextKeywordTrigger
from .voice_keyword import VoiceKeywordTrigger

TRIGGERS: dict[str, type[Trigger]] = {
    cls.name: cls for cls in (KeyboardTrigger, GamepadTrigger, TextKeywordTrigger, VoiceKeywordTrigger)
}

__all__ = ["TRIGGERS", "PlayCallback", "Trigger"]
