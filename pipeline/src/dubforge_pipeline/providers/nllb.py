"""NLLB-based TranslationProvider.

Uses Meta's facebook/nllb-200-distilled-600M model, whose weights are
released under CC-BY-NC 4.0 (non-commercial). This provider is intended for
demo/internal use only - it must not be used in commercial production
without separately licensing the model weights.
"""

import logging
import time
from typing import Any

from .base import TranslationProvider

logger = logging.getLogger(__name__)

_LANG_CODE_MAP = {
    "en": "eng_Latn",
    "hi": "hin_Deva",
    "bn": "ben_Beng",
}


def _nllb_lang_code(lang: str) -> str:
    try:
        return _LANG_CODE_MAP[lang]
    except KeyError:
        valid_options = ", ".join(sorted(_LANG_CODE_MAP))
        raise ValueError(
            f"Unsupported language code '{lang}'; valid options: {valid_options}"
        ) from None


class NLLBTranslationProvider(TranslationProvider):
    def __init__(self, model_id: str = "facebook/nllb-200-distilled-600M") -> None:
        self.model_id = model_id
        self._tokenizer: Any | None = None
        self._model: Any | None = None

    def _load(self) -> tuple[Any, Any]:
        if self._tokenizer is None or self._model is None:
            start_time = time.monotonic()

            from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            self._model = AutoModelForSeq2SeqLM.from_pretrained(self.model_id)

            elapsed_s = time.monotonic() - start_time
            logger.info("nllb model load model_id=%s elapsed_s=%.2f", self.model_id, elapsed_s)

        return self._tokenizer, self._model

    def translate(
        self, text: str, src_lang: str, tgt_lang: str, context: list[str] | None = None
    ) -> str:
        if not text.strip():
            return ""

        src_code = _nllb_lang_code(src_lang)
        tgt_code = _nllb_lang_code(tgt_lang)

        tokenizer, model = self._load()

        import torch

        start_time = time.monotonic()

        tokenizer.src_lang = src_code
        inputs = tokenizer(text, return_tensors="pt")
        forced_bos_token_id = tokenizer.convert_tokens_to_ids(tgt_code)

        with torch.no_grad():
            generated = model.generate(
                **inputs, forced_bos_token_id=forced_bos_token_id, max_length=256
            )

        translated = str(tokenizer.batch_decode(generated, skip_special_tokens=True)[0]).strip()

        elapsed_s = time.monotonic() - start_time
        logger.info(
            "nllb translate src_lang=%s tgt_lang=%s elapsed_s=%.2f",
            src_lang,
            tgt_lang,
            elapsed_s,
        )
        return translated
