import asyncio
from pathlib import Path

import discord
import pytest

from sonidos_bot import player as player_mod
from sonidos_bot.config import load_config

from .test_config import EXAMPLE


class FakeVoice:
    def __init__(self):
        self.played = []
        self.stopped = 0
        self.playing = False

    def is_connected(self):
        return True

    def is_playing(self):
        return self.playing

    def stop(self):
        self.stopped += 1

    def play(self, source, after=None):
        self.played.append(source)
        self.playing = True


@pytest.fixture
def player(monkeypatch):
    monkeypatch.setattr(player_mod, "find_ffmpeg", lambda: "ffmpeg")
    monkeypatch.setattr(discord, "FFmpegPCMAudio", lambda path, executable: object())
    monkeypatch.setattr(discord, "PCMVolumeTransformer", lambda src, volume: ("vol", volume))
    p = player_mod.Player(load_config(EXAMPLE))
    p.voice = FakeVoice()
    return p


def test_cooldown_and_interrupt(player):
    path = Path("x.mp3")
    assert asyncio.run(player.play(path))
    assert not asyncio.run(player.play(path))  # dentro del cooldown
    assert asyncio.run(player.play(path, ignore_cooldown=True))
    assert player.voice.stopped == 1  # cortó el anterior
    assert player.voice.played[0] == ("vol", 0.8)


def test_not_connected(player):
    player.voice = None
    assert not asyncio.run(player.play(Path("x.mp3")))
