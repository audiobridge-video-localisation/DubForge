import pytest

from dubforge_pipeline.providers.mock import MockSTTProvider, MockTranslationProvider
from dubforge_pipeline.providers.nllb import NLLBTranslationProvider
from dubforge_pipeline.providers.registry import get_stt_provider, get_translation_provider
from dubforge_pipeline.providers.whisper import WhisperSTTProvider


def test_default_provider_is_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STT_PROVIDER", raising=False)
    provider = get_stt_provider()
    assert isinstance(provider, MockSTTProvider)


def test_whisper_provider_uses_env_config(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STT_PROVIDER", "whisper")
    monkeypatch.setenv("WHISPER_MODEL", "medium")
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "float16")

    provider = get_stt_provider()

    assert isinstance(provider, WhisperSTTProvider)
    assert provider.model_size == "medium"
    assert provider.device == "cuda"
    assert provider.compute_type == "float16"


def test_provider_name_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STT_PROVIDER", "WHISPER")
    provider = get_stt_provider()
    assert isinstance(provider, WhisperSTTProvider)


def test_unknown_provider_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STT_PROVIDER", "nonexistent")
    with pytest.raises(ValueError, match="nonexistent"):
        get_stt_provider()


def test_default_translation_provider_is_mock(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("TRANSLATION_PROVIDER", raising=False)
    provider = get_translation_provider()
    assert isinstance(provider, MockTranslationProvider)


def test_translation_provider_nllb(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATION_PROVIDER", "nllb")
    provider = get_translation_provider()
    assert isinstance(provider, NLLBTranslationProvider)


def test_translation_provider_name_is_case_insensitive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATION_PROVIDER", "NLLB")
    provider = get_translation_provider()
    assert isinstance(provider, NLLBTranslationProvider)


def test_unknown_translation_provider_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("TRANSLATION_PROVIDER", "nonexistent")
    with pytest.raises(ValueError, match="nonexistent"):
        get_translation_provider()
