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

from dubforge_contracts.models import AudioResult

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
        self, text: str, voice_profile: str, target_duration_ms: int | None = None
    ) -> AudioResult:
        model_id = _resolve_model_id(voice_profile)
        tokenizer, model = self._load(model_id)

        import numpy as np
        import torch
        from scipy.io import wavfile

        start_time = time.monotonic()

        inputs = tokenizer(text, return_tensors="pt")
        with torch.no_grad():
            waveform = model(**inputs).waveform

        audio = waveform.squeeze().cpu().numpy().astype(np.float32)
        sample_rate = int(model.config.sampling_rate)

        fd, out_path = tempfile.mkstemp(suffix=".wav", dir=self.output_dir)
        os.close(fd)
        wavfile.write(out_path, rate=sample_rate, data=audio)

        duration_ms = round(len(audio) / sample_rate * 1000)

        elapsed_s = time.monotonic() - start_time
        logger.info(
            "mms-tts synthesize language=%s text_len=%d elapsed_s=%.2f",
            voice_profile,
            len(text),
            elapsed_s,
        )
        return AudioResult(audio_path=out_path, actual_duration_ms=duration_ms)
