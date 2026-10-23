import asyncio
import json
import sys
import threading
import time
import types

import numpy as np
import pytest

from sonidos_bot.config import load_config
from sonidos_bot.triggers import gamepad as gamepad_mod
from sonidos_bot.triggers.gamepad import GamepadTrigger
from sonidos_bot.triggers.keyboard import KeyboardTrigger
from sonidos_bot.triggers.keywords import KeywordMatcher
from sonidos_bot.triggers.text_keyword import TextKeywordTrigger
from sonidos_bot.triggers.voice_keyword import VoiceKeywordTrigger, discord_pcm_to_vosk

from .test_config import EXAMPLE


class Recorder:
    """Hace de bucle de eventos: ``fire`` llama directo al callback."""

    def __init__(self):
        self.fired = []

    def make(self, cls, config=None):
        trigger = cls(config or load_config(EXAMPLE), None, None)
        trigger.fire = self.fired.append
        return trigger


@pytest.mark.parametrize(
    "text,expected",
    [
        ("jaja el CHIQUI TAPÍA otra vez", "chiqui tapia"),
        ("ese manda más que nadie", "manda mas"),
        ("que uruguayo che", "uruguayo"),
        ("los uruguayos", None),  # palabra completa
        ("chiqui", None),
        ("", None),
    ],
)
def test_keyword_matcher(text, expected):
    assert KeywordMatcher(load_config(EXAMPLE)).find(text) == expected


def test_new_keyword_from_config_applies_to_text_and_voice():
    config = load_config(EXAMPLE)
    config.bindings[2].keywords.append("charrúa")
    assert KeywordMatcher(config).find("un charrua") == "uruguayo"


def test_text_trigger():
    rec = Recorder()
    t = rec.make(TextKeywordTrigger)
    asyncio.run(t.start())
    t.handle_message("Chiqui Tapia")
    t.handle_message("hola")
    assert rec.fired == ["chiqui tapia"]


def test_pcm_conversion():
    # 480 frames estéreo a 48 kHz -> 160 muestras mono a 16 kHz
    frames = np.full((480, 2), [1000, 3000], dtype=np.int16)
    out = np.frombuffer(discord_pcm_to_vosk(frames.tobytes()), dtype=np.int16)
    assert len(out) == 160 and (out == 2000).all()


def test_voice_trigger_uses_same_keywords(monkeypatch, tmp_path):
    heard = {"text": "", "partial": ""}

    class FakeRecognizer:
        resets = 0

        def __init__(self, model, rate):
            assert rate == 16000

        def AcceptWaveform(self, data):
            return False

        def PartialResult(self):
            return json.dumps({"partial": heard["partial"]})

        def Result(self):
            return json.dumps({"text": heard["text"]})

        def Reset(self):
            FakeRecognizer.resets += 1

    fake_vosk = types.SimpleNamespace(SetLogLevel=lambda n: None, Model=lambda p: object(), KaldiRecognizer=FakeRecognizer)
    monkeypatch.setitem(sys.modules, "vosk", fake_vosk)
    config = load_config(EXAMPLE)
    config.voice_model_path = str(tmp_path)

    rec = Recorder()
    t = rec.make(VoiceKeywordTrigger, config)
    asyncio.run(t.start())
    user = types.SimpleNamespace(id=1, bot=False)
    pcm = np.zeros(960 * 2, dtype=np.int16).tobytes()

    heard["partial"] = "y el uruguayo"
    t._on_audio(user, types.SimpleNamespace(pcm=pcm))
    t._on_audio(types.SimpleNamespace(id=2, bot=True), types.SimpleNamespace(pcm=pcm))  # bots se ignoran
    deadline = time.time() + 2
    while not rec.fired and time.time() < deadline:
        time.sleep(0.01)
    asyncio.run(t.stop())
    assert rec.fired == ["uruguayo"]
    assert FakeRecognizer.resets == 1


def test_voice_trigger_requires_model(monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "vosk", types.SimpleNamespace())
    config = load_config(EXAMPLE)
    config.voice_model_path = str(tmp_path / "no-existe")
    with pytest.raises(FileNotFoundError):
        asyncio.run(Recorder().make(VoiceKeywordTrigger, config).start())


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
