import os
from collections.abc import Callable

from .base import STTProvider, TranslationProvider
from .mock import MockSTTProvider, MockTranslationProvider
from .nllb import NLLBTranslationProvider
from .whisper import WhisperSTTProvider

_STT_FACTORIES: dict[str, Callable[[], STTProvider]] = {
    "mock": lambda: MockSTTProvider(),
    "whisper": lambda: WhisperSTTProvider(
        model_size=os.environ.get("WHISPER_MODEL", "small.en"),
        device=os.environ.get("WHISPER_DEVICE", "cpu"),
        compute_type=os.environ.get("WHISPER_COMPUTE_TYPE", "int8"),
    ),
}

_TRANSLATION_FACTORIES: dict[str, Callable[[], TranslationProvider]] = {
    "mock": lambda: MockTranslationProvider(),
    "nllb": lambda: NLLBTranslationProvider(),
}


def get_stt_provider() -> STTProvider:
    provider_name = os.environ.get("STT_PROVIDER", "mock").lower()
    factory = _STT_FACTORIES.get(provider_name)
    if factory is None:
        valid_options = ", ".join(sorted(_STT_FACTORIES))
        raise ValueError(f"Unknown STT_PROVIDER '{provider_name}'; valid options: {valid_options}")
    return factory()


def get_translation_provider() -> TranslationProvider:
    provider_name = os.environ.get("TRANSLATION_PROVIDER", "mock").lower()
    factory = _TRANSLATION_FACTORIES.get(provider_name)
    if factory is None:
        valid_options = ", ".join(sorted(_TRANSLATION_FACTORIES))
        raise ValueError(
            f"Unknown TRANSLATION_PROVIDER '{provider_name}'; valid options: {valid_options}"
        )
    return factory()
