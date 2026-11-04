import sys
import types

import pytest

import dubforge_pipeline.providers.nllb as nllb_module
from dubforge_pipeline.providers.nllb import NLLBTranslationProvider

_TOKEN_IDS = {"eng_Latn": 1, "hin_Deva": 2, "ben_Beng": 3}


class FakeTokenizer:
    def __init__(self) -> None:
        self.src_lang: str | None = None

    def __call__(self, text: str, return_tensors: str = "pt") -> dict[str, object]:
        return {"input_ids": [[0]]}

    def convert_tokens_to_ids(self, token: str) -> int:
        return _TOKEN_IDS[token]

    def batch_decode(self, generated: object, skip_special_tokens: bool = True) -> list[str]:
        return [f" decoded:{generated} "]


class FakeModel:
    def __init__(self) -> None:
        self.last_forced_bos_token_id: int | None = None

    def generate(self, **kwargs: object) -> str:
        self.last_forced_bos_token_id = kwargs.get("forced_bos_token_id")  # type: ignore[assignment]
        return "GENERATED"


class FakeAutoTokenizer:
    load_count = 0
    instance: FakeTokenizer | None = None

    @classmethod
    def from_pretrained(cls, model_id: str) -> FakeTokenizer:
        cls.load_count += 1
        cls.instance = FakeTokenizer()
        return cls.instance


class FakeAutoModelForSeq2SeqLM:
    load_count = 0
    instance: FakeModel | None = None

    @classmethod
    def from_pretrained(cls, model_id: str) -> FakeModel:
        cls.load_count += 1
        cls.instance = FakeModel()
        return cls.instance


class _NoGrad:
    def __enter__(self) -> "_NoGrad":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _fake_no_grad() -> _NoGrad:
    return _NoGrad()


@pytest.fixture(autouse=True)
def _reset_fake_counters() -> None:
    FakeAutoTokenizer.load_count = 0
    FakeAutoTokenizer.instance = None
    FakeAutoModelForSeq2SeqLM.load_count = 0
    FakeAutoModelForSeq2SeqLM.instance = None


@pytest.fixture
def mock_ml_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = FakeAutoTokenizer  # type: ignore[attr-defined]
    fake_transformers.AutoModelForSeq2SeqLM = FakeAutoModelForSeq2SeqLM  # type: ignore[attr-defined]

    fake_torch = types.ModuleType("torch")
    fake_torch.no_grad = _fake_no_grad  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)


def test_module_docstring_states_licence() -> None:
    assert nllb_module.__doc__ is not None
    assert "CC-BY-NC" in nllb_module.__doc__
    assert "not" in nllb_module.__doc__.lower()
    assert "commercial" in nllb_module.__doc__.lower()


def test_lang_code_mapping_translates(mock_ml_deps: None) -> None:
    provider = NLLBTranslationProvider()
    result = provider.translate("Hello", "en", "hi")

    assert result == "decoded:GENERATED"
    assert FakeAutoTokenizer.instance is not None
    assert FakeAutoTokenizer.instance.src_lang == "eng_Latn"
    assert FakeAutoModelForSeq2SeqLM.instance is not None
    assert FakeAutoModelForSeq2SeqLM.instance.last_forced_bos_token_id == _TOKEN_IDS["hin_Deva"]


def test_bengali_lang_code_mapping(mock_ml_deps: None) -> None:
    provider = NLLBTranslationProvider()
    provider.translate("Hello", "en", "bn")

    assert FakeAutoModelForSeq2SeqLM.instance is not None
    assert FakeAutoModelForSeq2SeqLM.instance.last_forced_bos_token_id == _TOKEN_IDS["ben_Beng"]


def test_unsupported_src_lang_raises_value_error(mock_ml_deps: None) -> None:
    provider = NLLBTranslationProvider()
    with pytest.raises(ValueError, match="fr"):
        provider.translate("Hello", "fr", "hi")
    assert FakeAutoTokenizer.load_count == 0


def test_unsupported_tgt_lang_raises_value_error(mock_ml_deps: None) -> None:
    provider = NLLBTranslationProvider()
    with pytest.raises(ValueError, match="fr"):
        provider.translate("Hello", "en", "fr")
    assert FakeAutoTokenizer.load_count == 0


def test_empty_text_short_circuits_without_loading_model(mock_ml_deps: None) -> None:
    provider = NLLBTranslationProvider()
    result = provider.translate("   ", "en", "hi")

    assert result == ""
    assert FakeAutoTokenizer.load_count == 0
    assert FakeAutoModelForSeq2SeqLM.load_count == 0


def test_lazy_load_happens_once_across_two_calls(mock_ml_deps: None) -> None:
    provider = NLLBTranslationProvider()

    provider.translate("Hello", "en", "hi")
    provider.translate("Goodbye", "en", "hi")

    assert FakeAutoTokenizer.load_count == 1
    assert FakeAutoModelForSeq2SeqLM.load_count == 1
