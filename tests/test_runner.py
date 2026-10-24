import asyncio
import time

from sonidos_bot import bot as bot_mod
from sonidos_bot.config import load_config
from sonidos_bot.runner import CONNECTED, ERROR, STARTING, STOPPED, BotRunner, describe_error

from .test_config import EXAMPLE


class FakeBot:
    """Imita SoundBot: 'conecta' al arrancar y espera hasta close()."""

    fail_with = None

    def __init__(self, config, on_connected=None):
        self.user = "Bot#0001"
        self.on_connected = on_connected
        self.closed = asyncio.Event()

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def start(self, token):
        if FakeBot.fail_with:
            raise FakeBot.fail_with
        self.on_connected(self)
        await self.closed.wait()

    async def close(self):
        self.closed.set()


def wait_for(states, wanted, timeout=2.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if states and states[-1][0] == wanted:
            return
        time.sleep(0.01)
    raise AssertionError(f"estado {wanted} no llegó: {states}")


def test_start_and_stop(monkeypatch):
    monkeypatch.setattr(bot_mod, "SoundBot", FakeBot)
    FakeBot.fail_with = None
    states = []
    runner = BotRunner(on_state=lambda s, d: states.append((s, d)))
    runner.start(load_config(EXAMPLE))
    wait_for(states, CONNECTED)
    assert runner.running and states[0][0] == STARTING and states[-1][1] == "Bot#0001"
    runner.stop()
    assert not runner.running and states[-1][0] == STOPPED


def test_error_is_reported(monkeypatch):
    monkeypatch.setattr(bot_mod, "SoundBot", FakeBot)
    FakeBot.fail_with = type("LoginFailure", (Exception,), {})("bad token")
    states = []
    runner = BotRunner(on_state=lambda s, d: states.append((s, d)))
    runner.start(load_config(EXAMPLE))
    wait_for(states, ERROR)
    assert "token" in states[-1][1]
    FakeBot.fail_with = None


def test_needs_restart_only_for_token_or_server():
    runner = BotRunner()
    runner.config = load_config(EXAMPLE)
    other = load_config(EXAMPLE)
    other.volume = 0.1
    assert not runner.needs_restart(other)
    other.discord.guild_id += 1
    assert runner.needs_restart(other)


def test_describe_error_generic():
    assert describe_error(ValueError("x")) == "ValueError: x"
