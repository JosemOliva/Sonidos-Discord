import asyncio
from types import SimpleNamespace

from sonidos_bot.config import load_config
from sonidos_bot.sound_library import SoundLibrary

from .test_config import EXAMPLE


class FakeAttachment:
    def __init__(self, id, filename, data=b"audio", content_type="audio/mpeg"):
        self.id = id
        self.filename = filename
        self.content_type = content_type
        self.data = data
        self.saves = 0

    async def save(self, path):
        self.saves += 1
        path.write_bytes(self.data)


class FakeChannel:
    def __init__(self, messages):
        self.messages = messages  # del más nuevo al más viejo

    async def history(self, limit=None, oldest_first=False):
        for m in self.messages:
            yield m


def msg(*attachments):
    return SimpleNamespace(attachments=list(attachments))


def make_library(tmp_path):
    config = load_config(EXAMPLE)
    config.path = tmp_path / "config.json"
    return SoundLibrary(config)


def test_sync_downloads_newest_and_skips_non_audio(tmp_path):
    lib = make_library(tmp_path)
    new = FakeAttachment(3, "Chiqui_Tapia.mp3", b"nuevo")
    old = FakeAttachment(1, "chiqui tapia.mp3", b"viejo")
    channel = FakeChannel([
        msg(new),
        msg(FakeAttachment(2, "foto.png", content_type="image/png")),
        msg(old, FakeAttachment(4, "uruguayo.ogg", content_type=None)),
    ])
    asyncio.run(lib.sync(channel))

    assert lib.names() == ["chiqui tapia", "uruguayo"]
    assert lib.get("chiqui tapia").read_bytes() == b"nuevo"
    assert old.saves == 0
    assert lib.missing_bindings() == ["manda_mas.mp3"]


def test_resync_reuses_cache_and_removes_deleted(tmp_path):
    lib = make_library(tmp_path)
    a = FakeAttachment(1, "manda_mas.mp3")
    b = FakeAttachment(2, "uruguayo.mp3")
    asyncio.run(lib.sync(FakeChannel([msg(a, b)])))

    lib2 = make_library(tmp_path)
    lib2.load_cached()
    assert lib2.names() == ["manda mas", "uruguayo"]
    asyncio.run(lib2.sync(FakeChannel([msg(a)])))
    assert a.saves == 1  # no se volvió a descargar
    assert lib2.names() == ["manda mas"]
    assert not (lib2.cache_dir / "2.mp3").exists()


def test_add_from_message_replaces_sound(tmp_path):
    lib = make_library(tmp_path)
    asyncio.run(lib.sync(FakeChannel([msg(FakeAttachment(1, "uruguayo.mp3", b"v1"))])))
    added = asyncio.run(lib.add_from_message(msg(FakeAttachment(9, "Uruguayo.wav", b"v2"))))
    assert added == ["uruguayo"]
    assert lib.get("uruguayo").read_bytes() == b"v2"
    assert not (lib.cache_dir / "1.mp3").exists()
