import json

import pytest

from sonidos_bot.config import ConfigError
from sonidos_bot.wizard_helpers import (
    binding_from_form,
    describe_no_button,
    known_sounds,
    parse_discord_id,
    parse_keywords,
    tk_event_to_hotkey,
)

CTRL, ALT_WIN, ALT_X11, SHIFT = 0x4, 0x20000, 0x8, 0x1


@pytest.mark.parametrize(
    "keysym,state,expected",
    [
        ("1", CTRL | ALT_WIN, "<ctrl>+<alt>+1"),
        ("A", SHIFT, "<shift>+a"),
        ("F9", 0, "<f9>"),
        ("space", ALT_X11, "<alt>+<space>"),
        ("Prior", CTRL, "<ctrl>+<page_up>"),
        ("Control_L", CTRL, None),  # solo modificador
        ("KP_Enter", 0, None),  # no soportada
    ],
)
def test_tk_event_to_hotkey(keysym, state, expected):
    assert tk_event_to_hotkey(keysym, state) == expected


def test_parse_keywords():
    assert parse_keywords(" chiqui tapia, manda más ;uruguayo,, ") == ["chiqui tapia", "manda más", "uruguayo"]


def test_parse_discord_id():
    assert parse_discord_id(" 123 ", "Servidor") == 123
    with pytest.raises(ConfigError, match="Servidor"):
        parse_discord_id("abc", "Servidor")


def test_binding_from_form():
    b = binding_from_form(" uruguayo.mp3 ", "", "2", "uruguayo, charrúa")
    assert (b.sound, b.hotkey, b.gamepad_button, b.keywords) == ("uruguayo.mp3", None, 2, ["uruguayo", "charrúa"])
    with pytest.raises(ConfigError):
        binding_from_form("x.mp3", "", "A", "")


def test_known_sounds(tmp_path):
    assert known_sounds(tmp_path) == []
    (tmp_path / "index.json").write_text(json.dumps([{"filename": "uruguayo.mp3"}, {"filename": "Chiqui_Tapia.mp3"}]))
    assert known_sounds(tmp_path) == ["Chiqui_Tapia.mp3", "uruguayo.mp3"]


def test_pretty_hotkey():
    from sonidos_bot.wizard_helpers import pretty_hotkey

    assert pretty_hotkey("<ctrl>+<alt>+1") == "Ctrl + Alt + 1"
    assert pretty_hotkey("<f9>") == "F9"
    assert pretty_hotkey("<shift>+<page_up>") == "Shift + RePág"
    assert pretty_hotkey(None) == ""


def test_find_cached_sound(tmp_path):
    from sonidos_bot.wizard_helpers import find_cached_sound

    (tmp_path / "55.mp3").write_bytes(b"x")
    (tmp_path / "index.json").write_text(json.dumps([{"key": "chiqui tapia", "file": "55.mp3", "filename": "Chiqui Tapia.mp3"}]))
    assert find_cached_sound(tmp_path, "chiqui_tapia.mp3") == tmp_path / "55.mp3"
    assert find_cached_sound(tmp_path, "uruguayo.mp3") is None


def test_describe_no_button_sin_mandos():
    assert "ningún mando" in describe_no_button([])


def test_describe_no_button_con_mando():
    msg = describe_no_button([("Xbox 360 Controller", 11)])
    assert "Xbox 360 Controller (11 botones)" in msg
    assert "cruceta" in msg


def test_soundboard_names():
    from sonidos_bot.wizard_helpers import soundboard_names

    data = {"items": [{"name": "El Manda Mas"}, {"name": "Angel"}, {"name": ""}, {"name": "Angel"}]}
    assert soundboard_names(data) == ["Angel", "El Manda Mas"]
    assert soundboard_names([]) == []
