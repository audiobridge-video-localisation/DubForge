"""MMSTTSProvider: Meta MMS (Massively Multilingual Speech) text-to-speech.

Uses the facebook/mms-tts-hin (Hindi) and facebook/mms-tts-ben (Bengali)
VitsModel checkpoints via transformers, run fully offline on CPU after the
first download. MMS weights are released under CC-BY-NC 4.0
(non-commercial) - this provider is for demo/internal use only, not for
commercial production.

If target_duration_ms is supplied it is ignored - this provider does not
perform time-stretching or duration matching against a target; that is
handled later in the pipeline.
"""

import logging
import os
import tempfile
import time
from typing import Any

from dubforge_contracts.models import MAX_SPEEDUP, AudioResult
from dubforge_pipeline.dub_fit import is_too_long, speedup_for

from .base import TTSProvider

logger = logging.getLogger(__name__)

_MODEL_BY_LANGUAGE = {
    "hi": "facebook/mms-tts-hin",
    "bn": "facebook/mms-tts-ben",
}


def _resolve_model_id(language: str) -> str:
    try:
        return _MODEL_BY_LANGUAGE[language]
    except KeyError:
        valid_options = ", ".join(sorted(_MODEL_BY_LANGUAGE))
        raise ValueError(
            f"Unsupported language '{language}'; valid options: {valid_options}"
        ) from None


# takes tried at the faster rate; the shortest is kept
TAKES_AT_RATE = 2


class MMSTTSProvider(TTSProvider):
    def __init__(self, output_dir: str | None = None) -> None:
        self.output_dir = output_dir or tempfile.gettempdir()
        self._tokenizers: dict[str, Any] = {}
        self._models: dict[str, Any] = {}

    def _load(self, model_id: str) -> tuple[Any, Any]:
        if model_id not in self._models:
            start_time = time.monotonic()

            from transformers import AutoTokenizer, VitsModel

            self._tokenizers[model_id] = AutoTokenizer.from_pretrained(model_id)
            self._models[model_id] = VitsModel.from_pretrained(model_id)

            elapsed_s = time.monotonic() - start_time
            logger.info("mms-tts model load model_id=%s elapsed_s=%.2f", model_id, elapsed_s)

        return self._tokenizers[model_id], self._models[model_id]

    def synthesize(
        self,
        text: str,
        voice_profile: str,
        target_duration_ms: int | None = None,
        speaker_index: int | None = None,
    ) -> AudioResult:
        # MMS has one model/voice per language; no pool to pick speaker_index from.
        model_id = _resolve_model_id(voice_profile)
        tokenizer, model = self._load(model_id)

        import numpy as np
        import torch
        from scipy.io import wavfile

        start_time = time.monotonic()

        inputs = tokenizer(text, return_tensors="pt")
        sample_rate = int(model.config.sampling_rate)

        def take(rate: float) -> Any:
            # VITS reads the rate when the model is built, so it is set on the model itself
            # (setting model.config.speaking_rate afterwards does nothing). Larger = faster.
            model.speaking_rate = rate
            try:
                with torch.no_grad():
                    return model(**inputs).waveform.squeeze().cpu().numpy().astype(np.float32)
            finally:
                model.speaking_rate = 1.0

        audio = take(1.0)
        used_rate = 1.0
        if target_duration_ms is not None and is_too_long(
            round(len(audio) / sample_rate * 1000), target_duration_ms
        ):
            # Too long for its room: ask the voice itself to speak faster (cleaner than
            # stretching the finished audio). Takes vary by several percent, so keep the
            # shortest of a couple of tries.
            rate = speedup_for(
                round(len(audio) / sample_rate * 1000), target_duration_ms, MAX_SPEEDUP
            )
            if rate > 1.0:
                faster = min((take(rate) for _ in range(TAKES_AT_RATE)), key=len)
                if len(faster) < len(audio):
                    audio, used_rate = faster, rate

        fd, out_path = tempfile.mkstemp(suffix=".wav", dir=self.output_dir)
        os.close(fd)
        wavfile.write(out_path, rate=sample_rate, data=audio)

        duration_ms = round(len(audio) / sample_rate * 1000)

        elapsed_s = time.monotonic() - start_time
        logger.info(
            "mms-tts synthesize language=%s text_len=%d rate=%.2f elapsed_s=%.2f",
            voice_profile,
            len(text),
            used_rate,
            elapsed_s,
        )
        return AudioResult(
            audio_path=out_path, actual_duration_ms=duration_ms, speech_rate=used_rate
        )
