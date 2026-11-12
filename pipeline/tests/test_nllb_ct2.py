import sys
import types
from pathlib import Path
from typing import Any

import pytest

import dubforge_pipeline.providers.nllb_ct2 as ct2_module
from dubforge_pipeline.providers.nllb_ct2 import NLLBCT2TranslationProvider


class FakeTokenizer:
    def __init__(self) -> None:
        self.src_lang: str | None = None
        self.src_lang_at_encode: str | None = None
        self.decoded_ids: list[int] | None = None

    def encode(self, text: str) -> list[int]:
        self.src_lang_at_encode = self.src_lang
        return [10, 11]

    def convert_ids_to_tokens(self, ids: list[int]) -> list[str]:
        return [f"tok{i}" for i in ids]

    def convert_tokens_to_ids(self, tokens: list[str]) -> list[int]:
        return [len(token) for token in tokens]

    def decode(self, ids: list[int], skip_special_tokens: bool = True) -> str:
        self.decoded_ids = ids
        return " translated "


class FakeAutoTokenizer:
    load_count = 0
    instance: FakeTokenizer | None = None

    @classmethod
    def from_pretrained(cls, model_id: str) -> FakeTokenizer:
        cls.load_count += 1
        cls.instance = FakeTokenizer()
        return cls.instance


class FakeResult:
    def __init__(self, hypotheses: list[list[str]]) -> None:
        self.hypotheses = hypotheses


class FakeTranslator:
    instances: list["FakeTranslator"] = []
    hypothesis: list[str] = ["hin_Deva", "ab", "cde"]

    def __init__(self, model_path: str, **kwargs: Any) -> None:
        self.model_path = model_path
        self.init_kwargs = kwargs
        self.calls: list[dict[str, Any]] = []
        FakeTranslator.instances.append(self)

    def translate_batch(self, batch: list[list[str]], **kwargs: Any) -> list[FakeResult]:
        self.calls.append({"batch": batch, **kwargs})
        return [FakeResult([list(FakeTranslator.hypothesis)])]


class FakeConverter:
    instances: list["FakeConverter"] = []

    def __init__(self, model_id: str) -> None:
        self.model_id = model_id
        self.output_dir: str | None = None
        self.quantization: str | None = None
        FakeConverter.instances.append(self)

    def convert(self, output_dir: str, quantization: str | None = None) -> str:
        self.output_dir = output_dir
        self.quantization = quantization
        out = Path(output_dir)
        out.mkdir(parents=True)
        (out / "model.bin").write_bytes(b"fake")
        return output_dir


@pytest.fixture(autouse=True)
def _reset_fakes() -> None:
    FakeAutoTokenizer.load_count = 0
    FakeAutoTokenizer.instance = None
    FakeTranslator.instances = []
    FakeTranslator.hypothesis = ["hin_Deva", "ab", "cde"]
    FakeConverter.instances = []


@pytest.fixture
def mock_ml_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = FakeAutoTokenizer  # type: ignore[attr-defined]

    fake_ct2 = types.ModuleType("ctranslate2")
    fake_ct2.Translator = FakeTranslator  # type: ignore[attr-defined]
    fake_converters = types.ModuleType("ctranslate2.converters")
    fake_converters.TransformersConverter = FakeConverter  # type: ignore[attr-defined]
    fake_ct2.converters = fake_converters  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setitem(sys.modules, "ctranslate2", fake_ct2)
    monkeypatch.setitem(sys.modules, "ctranslate2.converters", fake_converters)


def _converted_dir(tmp_path: Path) -> Path:
    ct2_dir = tmp_path / "nllb-ct2"
    ct2_dir.mkdir()
    (ct2_dir / "model.bin").write_bytes(b"fake")
    return ct2_dir


def test_module_docstring_states_licence() -> None:
    assert ct2_module.__doc__ is not None
    assert "CC-BY-NC" in ct2_module.__doc__
    assert "commercial" in ct2_module.__doc__.lower()


def test_translate_prefixes_target_lang_and_drops_it_from_output(
    mock_ml_deps: None, tmp_path: Path
) -> None:
    provider = NLLBCT2TranslationProvider(ct2_dir=str(_converted_dir(tmp_path)), threads=3)

    result = provider.translate("Hello", "en", "hi")

    assert result == "translated"
    tokenizer = FakeAutoTokenizer.instance
    assert tokenizer is not None
    assert tokenizer.src_lang_at_encode == "eng_Latn"
    # Language token dropped before decoding: only the two real tokens remain.
    assert tokenizer.decoded_ids == [2, 3]

    translator = FakeTranslator.instances[0]
    assert translator.calls == [
        {
            "batch": [["tok10", "tok11"]],
            "target_prefix": [["hin_Deva"]],
            "beam_size": 2,
            "max_decoding_length": 256,
        }
    ]


def test_translator_is_created_for_cpu_int8_with_threads(
    mock_ml_deps: None, tmp_path: Path
) -> None:
    ct2_dir = _converted_dir(tmp_path)
    provider = NLLBCT2TranslationProvider(ct2_dir=str(ct2_dir), threads=3)

    provider.translate("Hello", "en", "bn")

    translator = FakeTranslator.instances[0]
    assert translator.model_path == str(ct2_dir)
    assert translator.init_kwargs == {
        "device": "cpu",
        "compute_type": "int8",
        "intra_threads": 3,
    }
    assert FakeTranslator.instances[0].calls[0]["target_prefix"] == [["ben_Beng"]]


def test_threads_default_from_env_then_cpu_count(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("NLLB_CT2_THREADS", "5")
    assert NLLBCT2TranslationProvider(ct2_dir=str(tmp_path)).threads == 5

    monkeypatch.delenv("NLLB_CT2_THREADS")
    monkeypatch.setattr(ct2_module.os, "cpu_count", lambda: 7)
    assert NLLBCT2TranslationProvider(ct2_dir=str(tmp_path)).threads == 7


def test_ct2_dir_defaults_from_env(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setenv("NLLB_CT2_DIR", str(tmp_path / "custom"))
    assert NLLBCT2TranslationProvider().ct2_dir == tmp_path / "custom"

    monkeypatch.delenv("NLLB_CT2_DIR")
    assert NLLBCT2TranslationProvider().ct2_dir == Path("/app/data/.cache/nllb-ct2")


def test_existing_model_is_not_reconverted(mock_ml_deps: None, tmp_path: Path) -> None:
    provider = NLLBCT2TranslationProvider(ct2_dir=str(_converted_dir(tmp_path)), threads=1)

    provider.translate("Hello", "en", "hi")

    assert FakeConverter.instances == []


def test_first_use_converts_to_int8_atomically(mock_ml_deps: None, tmp_path: Path) -> None:
    ct2_dir = tmp_path / "cache" / "nllb-ct2"
    provider = NLLBCT2TranslationProvider(ct2_dir=str(ct2_dir), threads=1)

    provider.translate("Hello", "en", "hi")

    assert len(FakeConverter.instances) == 1
    converter = FakeConverter.instances[0]
    assert converter.model_id == "facebook/nllb-200-distilled-600M"
    assert converter.quantization == "int8"
    # Converted into a temp dir, then renamed into place.
    assert converter.output_dir is not None
    assert Path(converter.output_dir) != ct2_dir
    assert (ct2_dir / "model.bin").exists()
    # No temp leftovers beside the final dir.
    assert [p.name for p in ct2_dir.parent.iterdir()] == ["nllb-ct2"]


def test_failed_conversion_leaves_no_partial_model(
    mock_ml_deps: None, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def boom(self: FakeConverter, output_dir: str, quantization: str | None = None) -> str:
        Path(output_dir).mkdir(parents=True)
        (Path(output_dir) / "model.bin").write_bytes(b"partial")
        raise RuntimeError("convert failed")

    monkeypatch.setattr(FakeConverter, "convert", boom)
    ct2_dir = tmp_path / "cache" / "nllb-ct2"
    provider = NLLBCT2TranslationProvider(ct2_dir=str(ct2_dir), threads=1)

    with pytest.raises(RuntimeError, match="convert failed"):
        provider.translate("Hello", "en", "hi")

    assert not ct2_dir.exists()
    assert list(ct2_dir.parent.iterdir()) == []


def test_lazy_load_happens_once_across_two_calls(mock_ml_deps: None, tmp_path: Path) -> None:
    provider = NLLBCT2TranslationProvider(ct2_dir=str(_converted_dir(tmp_path)), threads=1)

    provider.translate("Hello", "en", "hi")
    provider.translate("Goodbye", "en", "hi")

    assert FakeAutoTokenizer.load_count == 1
    assert len(FakeTranslator.instances) == 1
    assert len(FakeTranslator.instances[0].calls) == 2


def test_output_without_language_prefix_is_kept_whole(mock_ml_deps: None, tmp_path: Path) -> None:
    FakeTranslator.hypothesis = ["ab", "cde"]
    provider = NLLBCT2TranslationProvider(ct2_dir=str(_converted_dir(tmp_path)), threads=1)

    provider.translate("Hello", "en", "hi")

    assert FakeAutoTokenizer.instance is not None
    assert FakeAutoTokenizer.instance.decoded_ids == [2, 3]


def test_empty_text_short_circuits_without_loading(mock_ml_deps: None, tmp_path: Path) -> None:
    provider = NLLBCT2TranslationProvider(ct2_dir=str(_converted_dir(tmp_path)), threads=1)

    assert provider.translate("   ", "en", "hi") == ""
    assert FakeAutoTokenizer.load_count == 0
    assert FakeTranslator.instances == []


@pytest.mark.parametrize(("src", "tgt"), [("fr", "hi"), ("en", "fr")])
def test_unsupported_language_raises_value_error(
    mock_ml_deps: None, tmp_path: Path, src: str, tgt: str
) -> None:
    provider = NLLBCT2TranslationProvider(ct2_dir=str(_converted_dir(tmp_path)), threads=1)

    with pytest.raises(ValueError, match="fr"):
        provider.translate("Hello", src, tgt)
    assert FakeAutoTokenizer.load_count == 0


def test_translate_logs_elapsed_seconds(
    mock_ml_deps: None, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    provider = NLLBCT2TranslationProvider(ct2_dir=str(_converted_dir(tmp_path)), threads=1)

    with caplog.at_level("INFO", logger=ct2_module.logger.name):
        provider.translate("Hello", "en", "hi")

    assert any(
        "nllb-ct2 translate" in r.getMessage() and "elapsed_s=" in r.getMessage()
        for r in caplog.records
    )
