import asyncio
import sys
import time
import types

from sonidos_bot.config import load_config
from sonidos_bot.triggers import gamepad as gamepad_mod
from sonidos_bot.triggers.gamepad import GamepadTrigger
from sonidos_bot.triggers.keyboard import KeyboardTrigger

from .test_config import EXAMPLE


class Recorder:
    """Hace de bucle de eventos: ``fire`` llama directo al callback."""

    def __init__(self):
        self.fired = []

    def make(self, cls, config=None):
        trigger = cls(config or load_config(EXAMPLE), None, None)
        trigger.fire = self.fired.append
        return trigger


def test_keyboard_trigger_registers_hotkeys(monkeypatch):
    created = {}

    class FakeGlobalHotKeys:
        def __init__(self, mapping):
            created.update(mapping)

        def start(self):
            pass

        def stop(self):
            created["stopped"] = True

    def parse(hotkey):
        if "??" in hotkey:
            raise ValueError(hotkey)

    keyboard = types.SimpleNamespace(GlobalHotKeys=FakeGlobalHotKeys, HotKey=types.SimpleNamespace(parse=parse))
    monkeypatch.setitem(sys.modules, "pynput", types.SimpleNamespace(keyboard=keyboard))
    monkeypatch.setitem(sys.modules, "pynput.keyboard", keyboard)

    config = load_config(EXAMPLE)
    config.bindings[1].hotkey = "<ctrl>+??"
    rec = Recorder()
    t = rec.make(KeyboardTrigger, config)
    asyncio.run(t.start())
    assert set(created) == {"<ctrl>+<alt>+1", "<ctrl>+<alt>+3"}  # el inválido se ignora
    created["<ctrl>+<alt>+3"]()
    asyncio.run(t.stop())
    assert rec.fired == ["uruguayo"] and created["stopped"]


def test_gamepad_trigger_fires_once_per_press(monkeypatch):
    state = {"buttons": [0, 0, 0]}

    class FakeStick:
        def get_name(self):
            return "Mando falso"

        def get_instance_id(self):
            return 7

        def get_numbuttons(self):
            return 3

        def get_button(self, i):
            return state["buttons"][i]

    fake_pygame = types.SimpleNamespace(
        event=types.SimpleNamespace(pump=lambda: None),
        joystick=types.SimpleNamespace(get_count=lambda: 1, Joystick=lambda i: FakeStick(), quit=lambda: None),
    )
    monkeypatch.setattr(gamepad_mod, "init_pygame_joystick", lambda: fake_pygame)

    rec = Recorder()
    t = rec.make(GamepadTrigger)
    asyncio.run(t.start())
    time.sleep(0.05)
    state["buttons"] = [0, 1, 0]  # botón 1 mantenido
    time.sleep(0.1)
    state["buttons"] = [0, 0, 0]
    time.sleep(0.05)
    state["buttons"] = [1, 0, 0]
    time.sleep(0.05)
    asyncio.run(t.stop())
    assert rec.fired == ["manda mas", "chiqui tapia"]


def test_xinput_buttons_from_mask():
    from sonidos_bot.triggers.xinput import buttons_from_mask

    assert buttons_from_mask(0) == set()
    assert buttons_from_mask(0x1000) == {0}  # A
    assert buttons_from_mask(0x0010 | 0x0200) == {5, 7}  # RB + Start


def test_gamepad_prefers_xinput_numbering(monkeypatch):
    monkeypatch.setattr(gamepad_mod.xinput, "pressed_buttons", lambda: {0})

    class Stick:
        def get_numbuttons(self):
            return 3

        def get_button(self, i):
            return i == 2  # el mismo botón con otra numeración

    assert gamepad_mod.buttons_down([Stick()]) == {0}
    monkeypatch.setattr(gamepad_mod.xinput, "pressed_buttons", set)
    assert gamepad_mod.buttons_down([Stick()]) == {2}
