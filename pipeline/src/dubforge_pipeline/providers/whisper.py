import logging
import math
import time
from pathlib import Path
from typing import Any

from dubforge_contracts.models import TranscriptSegment

from .base import STTProvider

logger = logging.getLogger(__name__)


class WhisperSTTProvider(STTProvider):
    def __init__(
        self,
        model_size: str = "small.en",
        device: str = "cpu",
        compute_type: str = "int8",
        language: str | None = "en",
        beam_size: int = 5,
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self.language = language
        self.beam_size = beam_size
        self._model: Any | None = None

    def _get_model(self) -> Any:
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(
                self.model_size, device=self.device, compute_type=self.compute_type
            )
        return self._model

    def transcribe(self, audio_path: str) -> list[TranscriptSegment]:
        if not Path(audio_path).exists():
            raise RuntimeError(f"audio file not found: {audio_path}")

        model = self._get_model()

        start_time = time.monotonic()
        segments, _info = model.transcribe(
            audio_path,
            language=self.language,
            beam_size=self.beam_size,
            word_timestamps=True,
            vad_filter=True,
        )

        results: list[TranscriptSegment] = []
        for seg in segments:
            text = seg.text.strip()
            if not text:
                continue
            start_ms = round(seg.start * 1000)
            end_ms = round(seg.end * 1000)
            if end_ms <= start_ms:
                continue
            results.append(
                TranscriptSegment(
                    start_ms=start_ms,
                    end_ms=end_ms,
                    text=text,
                    confidence=round(math.exp(seg.avg_logprob), 4),
                )
            )

        elapsed_s = time.monotonic() - start_time
        logger.info(
            "whisper transcribe model=%s audio_path=%s segments=%d elapsed_s=%.2f",
            self.model_size,
            audio_path,
            len(results),
            elapsed_s,
        )
        return results
