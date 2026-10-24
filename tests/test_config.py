import json

import pytest

from sonidos_bot.config import (
    TOKEN_ENV_VAR,
    Binding,
    Config,
    ConfigError,
    load_config,
    normalize_text,
    save_config,
    sound_key,
)

EXAMPLE = __import__("pathlib").Path(__file__).parent.parent / "config.example.json"


def test_example_config_is_valid():
    config = load_config(EXAMPLE)
    assert config.modes.enabled() == ["keyboard", "gamepad"]
    assert [b.sound_key for b in config.bindings] == ["chiqui tapia", "manda mas", "uruguayo"]
    assert config.bindings[0].sound_key == "chiqui tapia"


def test_normalize_and_sound_key():
    assert normalize_text("  Chiqui   TAPÍA ") == "chiqui tapia"
    assert sound_key("Chiqui_Tapia.mp3") == sound_key("chiqui tapia.ogg") == "chiqui tapia"


def test_env_token_overrides_file(tmp_path, monkeypatch):
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["discord"]["token"] = ""
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(ConfigError, match="token"):
        load_config(path)
    monkeypatch.setenv(TOKEN_ENV_VAR, "abc")
    assert load_config(path).discord.token == "abc"


def test_detects_duplicates_and_empty_bindings():
    config = load_config(EXAMPLE)
    config.bindings.append(Binding(sound="otro.mp3", hotkey="<CTRL>+<alt>+1", gamepad_button=0))
    config.bindings.append(Binding(sound="vacio.mp3"))
    with pytest.raises(ConfigError) as exc:
        config.validate()
    text = str(exc.value)
    assert "tecla" in text and "botón 0" in text and "vacio.mp3" in text


def test_old_config_with_keywords_still_loads(tmp_path):
    data = json.loads(EXAMPLE.read_text(encoding="utf-8"))
    data["modes"].update(text_keyword=True, voice_keyword=True)
    data["bindings"][0]["keywords"] = ["chiqui tapia"]
    data["voice_model_path"] = "C:\\modelo"
    path = tmp_path / "config.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    config = load_config(path)
    assert config.modes.enabled() == ["keyboard", "gamepad"]
    assert "keywords" not in config.to_dict()["bindings"][0]


def test_unknown_key_is_reported(tmp_path):
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"discord": {"tokn": "x"}}), encoding="utf-8")
    with pytest.raises(ConfigError, match="Formato"):
        load_config(path)


def test_save_roundtrip(tmp_path):
    config = load_config(EXAMPLE)
    saved = save_config(config, tmp_path / "sub" / "config.json")
    again = load_config(saved)
    assert again.to_dict() == config.to_dict()
    assert again.cache_dir == tmp_path / "sub" / "sonidos"


def test_default_config_is_invalid_until_filled():
    with pytest.raises(ConfigError):
        Config().validate()


def test_sound_key_keeps_dots_in_soundboard_names():
    assert sound_key("El Manda Mas") == "el manda mas"
    assert sound_key("Sr. Tapia") == "sr. tapia"


def test_sounds_channel_is_optional():
    config = load_config(EXAMPLE)
    config.discord.sounds_channel_id = 0
    config.validate()
