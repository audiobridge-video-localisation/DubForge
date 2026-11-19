"""NLLB TranslationProvider backed by CTranslate2 (int8, CPU).

Same model as providers/nllb.py (facebook/nllb-200-distilled-600M), whose
weights are released under CC-BY-NC 4.0 (non-commercial). This provider is
intended for demo/internal use only - it must not be used in commercial
production without separately licensing the model weights.

The model is converted to CTranslate2 int8 format on first use and cached in
NLLB_CT2_DIR, which makes CPU inference far faster than the torch provider.
"""

import logging
import os
import shutil
import tempfile
import time
from pathlib import Path
from typing import Any

from .base import TranslationProvider
from .nllb import _nllb_lang_code

logger = logging.getLogger(__name__)

_DEFAULT_MODEL_ID = "facebook/nllb-200-distilled-600M"
_DEFAULT_CT2_DIR = "/app/data/.cache/nllb-ct2"
_BEAM_SIZE = 2
_MAX_DECODING_LENGTH = 256


def _convert_model(model_id: str, ct2_dir: Path) -> None:
    """Convert model_id into ct2_dir, atomically.

    Converts into a temp dir beside ct2_dir and renames it into place, so an
    interrupted conversion never leaves a half-written model behind.
    """
    from ctranslate2.converters import TransformersConverter

    start_time = time.monotonic()
    ct2_dir.parent.mkdir(parents=True, exist_ok=True)
    tmp_dir = Path(tempfile.mkdtemp(prefix=f"{ct2_dir.name}.tmp-", dir=ct2_dir.parent))
    try:
        # The converter refuses to write into an existing directory.
        convert_dir = tmp_dir / "model"
        TransformersConverter(model_id).convert(str(convert_dir), quantization="int8")
        try:
            os.replace(convert_dir, ct2_dir)
        except OSError:
            # Another process finished the same conversion first; use theirs.
            if not ct2_dir.exists():
                raise
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    elapsed_s = time.monotonic() - start_time
    logger.info(
        "nllb-ct2 model convert model_id=%s dir=%s elapsed_s=%.2f", model_id, ct2_dir, elapsed_s
    )


class NLLBCT2TranslationProvider(TranslationProvider):
    def __init__(
        self,
        model_id: str = _DEFAULT_MODEL_ID,
        ct2_dir: str | None = None,
        threads: int | None = None,
    ) -> None:
        self.model_id = model_id
        self.ct2_dir = Path(ct2_dir or os.environ.get("NLLB_CT2_DIR") or _DEFAULT_CT2_DIR)
        if threads is None:
            threads = int(os.environ.get("NLLB_CT2_THREADS") or 0) or os.cpu_count() or 1
        self.threads = threads
        self._tokenizer: Any | None = None
        self._translator: Any | None = None

    def _load(self) -> tuple[Any, Any]:
        if self._tokenizer is None or self._translator is None:
            start_time = time.monotonic()

            import ctranslate2
            from transformers import AutoTokenizer

            if not (self.ct2_dir / "model.bin").exists():
                _convert_model(self.model_id, self.ct2_dir)

            self._tokenizer = AutoTokenizer.from_pretrained(self.model_id)
            self._translator = ctranslate2.Translator(
                str(self.ct2_dir),
                device="cpu",
                compute_type="int8",
                intra_threads=self.threads,
            )

            elapsed_s = time.monotonic() - start_time
            logger.info(
                "nllb-ct2 model load model_id=%s threads=%d elapsed_s=%.2f",
                self.model_id,
                self.threads,
                elapsed_s,
            )

        return self._tokenizer, self._translator

    def translate(
        self, text: str, src_lang: str, tgt_lang: str, context: list[str] | None = None
    ) -> str:
        if not text.strip():
            return ""

        src_code = _nllb_lang_code(src_lang)
        tgt_code = _nllb_lang_code(tgt_lang)

        tokenizer, translator = self._load()

        start_time = time.monotonic()

        tokenizer.src_lang = src_code
        source_tokens = tokenizer.convert_ids_to_tokens(tokenizer.encode(text))
        results = translator.translate_batch(
            [source_tokens],
            target_prefix=[[tgt_code]],
            beam_size=_BEAM_SIZE,
            max_decoding_length=_MAX_DECODING_LENGTH,
        )
        target_tokens = list(results[0].hypotheses[0])
        # The decoder echoes the target-language prefix token; drop it.
        if target_tokens and target_tokens[0] == tgt_code:
            target_tokens = target_tokens[1:]
        translated = str(
            tokenizer.decode(
                tokenizer.convert_tokens_to_ids(target_tokens), skip_special_tokens=True
            )
        ).strip()

        elapsed_s = time.monotonic() - start_time
        logger.info(
            "nllb-ct2 translate src_lang=%s tgt_lang=%s elapsed_s=%.2f",
            src_lang,
            tgt_lang,
            elapsed_s,
        )
        return translated
