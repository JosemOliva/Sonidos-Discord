"""Palabras clave dichas por voz en el canal.

Recibe el audio de cada persona del canal (``discord-ext-voice-recv``), lo
convierte a 16 kHz mono y lo pasa por Vosk, que reconoce voz en español sin
conexión a internet. Cuando el texto reconocido contiene una palabra clave se
dispara el sonido y se reinicia el reconocedor de esa persona para no
dispararlo dos veces por la misma frase.

El modelo se descarga aparte (vosk-model-small-es, ~40 MB) y su carpeta va en
``voice_model_path``. Las palabras clave son las mismas que en el modo texto
(la lista ``keywords`` de cada sonido): no hay una lista aparte para la voz.
"""

from __future__ import annotations

import json
import queue
import threading
from pathlib import Path

import numpy as np

from .base import Trigger
from .keywords import KeywordMatcher

DISCORD_RATE = 48000
VOSK_RATE = 16000


def discord_pcm_to_vosk(pcm: bytes) -> bytes:
    """48 kHz estéreo 16 bits (Discord) -> 16 kHz mono 16 bits (Vosk)."""
    samples = np.frombuffer(pcm, dtype=np.int16)
    mono = samples.reshape(-1, 2).mean(axis=1)
    step = DISCORD_RATE // VOSK_RATE
    usable = len(mono) - len(mono) % step
    down = mono[:usable].reshape(-1, step).mean(axis=1)  # promedio = filtro paso bajo simple
    return down.astype(np.int16).tobytes()


class VoiceKeywordTrigger(Trigger):
    name = "voice_keyword"

    async def start(self) -> None:
        import vosk

        model_path = Path(self.config.voice_model_path)
        if not model_path.is_dir():
            raise FileNotFoundError(f"No encuentro el modelo de Vosk en {model_path}")
        vosk.SetLogLevel(-1)
        self.log.info("Cargando modelo de voz %s", model_path.name)
        self._vosk = vosk
        self._model = vosk.Model(str(model_path))
        self.matcher = KeywordMatcher(self.config)
        self._recognizers: dict[int, object] = {}
        self._queue: queue.Queue = queue.Queue(maxsize=500)
        self._stop = threading.Event()
        self._worker = threading.Thread(target=self._run, name="voice-keyword", daemon=True)
        self._worker.start()
        self._voice = None

    async def stop(self) -> None:
        self._detach()
        if getattr(self, "_worker", None):
            self._stop.set()
            self._queue.put(None)
            self._worker.join(timeout=2)
            self._worker = None

    def voice_connected(self, voice) -> None:
        from discord.ext import voice_recv

        self._detach()
        if not isinstance(voice, voice_recv.VoiceRecvClient):
            self.log.error("La conexión de voz no permite recibir audio")
            return
        self._voice = voice
        voice.listen(voice_recv.BasicSink(self._on_audio))
        self.log.info("Escuchando el canal de voz")

    def _detach(self) -> None:
        voice = getattr(self, "_voice", None)
        if voice is not None and voice.is_listening():
            voice.stop_listening()
        self._voice = None

    def _on_audio(self, user, data) -> None:
        # Llamado desde el hilo de recepción: solo encola, el trabajo pesado va aparte.
        if user is None or user.bot or not data.pcm:
            return
        try:
            self._queue.put_nowait((user.id, data.pcm))
        except queue.Full:
            pass  # si Vosk no da abasto, mejor perder audio que acumular retraso

    def _run(self) -> None:
        while not self._stop.is_set():
            item = self._queue.get()
            if item is None:
                break
            user_id, pcm = item
            rec = self._recognizers.get(user_id)
            if rec is None:
                rec = self._recognizers[user_id] = self._vosk.KaldiRecognizer(self._model, VOSK_RATE)
            final = rec.AcceptWaveform(discord_pcm_to_vosk(pcm))
            text = json.loads(rec.Result() if final else rec.PartialResult())
            heard = text.get("text") or text.get("partial") or ""
            key = self.matcher.find(heard) if heard else None
            if key:
                self.log.info("Oído '%s'", heard)
                self.fire(key)
                rec.Reset()
