import sys
import types
import wave
from pathlib import Path

import numpy as np
import pytest

from dubforge_pipeline.providers.mms_tts import MMSTTSProvider, _resolve_model_id

_SAMPLE_RATE = 16000


class FakeTensor:
    def __init__(self, array: np.ndarray) -> None:
        self._array = array

    def squeeze(self) -> "FakeTensor":
        return FakeTensor(self._array.squeeze())

    def cpu(self) -> "FakeTensor":
        return self

    def numpy(self) -> np.ndarray:
        return self._array


class FakeModelOutput:
    def __init__(self, waveform: FakeTensor) -> None:
        self.waveform = waveform


class FakeConfig:
    sampling_rate = _SAMPLE_RATE


class FakeVitsModelInstance:
    def __call__(self, **inputs: object) -> FakeModelOutput:
        num_samples = max(len(inputs.get("input_ids", [[0]])[0]) * 1000, 100)  # type: ignore[index]
        array = np.zeros(num_samples, dtype=np.float32)
        return FakeModelOutput(FakeTensor(array))

    config = FakeConfig()


class FakeTokenizer:
    def __call__(self, text: str, return_tensors: str = "pt") -> dict[str, object]:
        return {"input_ids": [[0] * max(len(text), 1)]}


class FakeAutoTokenizer:
    load_count = 0

    @classmethod
    def from_pretrained(cls, model_id: str) -> FakeTokenizer:
        cls.load_count += 1
        return FakeTokenizer()


class FakeVitsModel:
    load_count = 0

    @classmethod
    def from_pretrained(cls, model_id: str) -> FakeVitsModelInstance:
        cls.load_count += 1
        return FakeVitsModelInstance()


class _NoGrad:
    def __enter__(self) -> "_NoGrad":
        return self

    def __exit__(self, *args: object) -> None:
        return None


def _fake_no_grad() -> _NoGrad:
    return _NoGrad()


def _fake_wavfile_write(path: str, rate: int, data: np.ndarray) -> None:
    with wave.open(path, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(rate)
        pcm = (np.clip(data, -1.0, 1.0) * 32767).astype(np.int16)
        wav_file.writeframes(pcm.tobytes())


@pytest.fixture(autouse=True)
def _reset_fake_counters() -> None:
    FakeAutoTokenizer.load_count = 0
    FakeVitsModel.load_count = 0


@pytest.fixture
def mock_ml_deps(monkeypatch: pytest.MonkeyPatch) -> None:
    fake_transformers = types.ModuleType("transformers")
    fake_transformers.AutoTokenizer = FakeAutoTokenizer  # type: ignore[attr-defined]
    fake_transformers.VitsModel = FakeVitsModel  # type: ignore[attr-defined]

    fake_torch = types.ModuleType("torch")
    fake_torch.no_grad = _fake_no_grad  # type: ignore[attr-defined]

    fake_wavfile = types.ModuleType("scipy.io.wavfile")
    fake_wavfile.write = _fake_wavfile_write  # type: ignore[attr-defined]

    fake_scipy_io = types.ModuleType("scipy.io")
    fake_scipy_io.wavfile = fake_wavfile  # type: ignore[attr-defined]

    fake_scipy = types.ModuleType("scipy")
    fake_scipy.io = fake_scipy_io  # type: ignore[attr-defined]

    monkeypatch.setitem(sys.modules, "transformers", fake_transformers)
    monkeypatch.setitem(sys.modules, "torch", fake_torch)
    monkeypatch.setitem(sys.modules, "scipy", fake_scipy)
    monkeypatch.setitem(sys.modules, "scipy.io", fake_scipy_io)


def test_resolve_model_id_language_mapping() -> None:
    assert _resolve_model_id("hi") == "facebook/mms-tts-hin"
    assert _resolve_model_id("bn") == "facebook/mms-tts-ben"


def test_resolve_model_id_unsupported_raises_value_error() -> None:
    with pytest.raises(ValueError, match="fr"):
        _resolve_model_id("fr")


def test_synthesize_produces_wav(tmp_path: Path, mock_ml_deps: None) -> None:
    provider = MMSTTSProvider(output_dir=str(tmp_path))
    result = provider.synthesize("Hello there.", "hi")

    assert Path(result.audio_path).exists()
    assert Path(result.audio_path).stat().st_size > 0
    assert result.actual_duration_ms > 0


def test_synthesize_ignores_target_duration_ms(tmp_path: Path, mock_ml_deps: None) -> None:
    provider = MMSTTSProvider(output_dir=str(tmp_path))
    result = provider.synthesize("Hello there.", "hi", target_duration_ms=999_999)

    assert result.actual_duration_ms != 999_999


def test_synthesize_empty_text_does_not_raise(tmp_path: Path, mock_ml_deps: None) -> None:
    provider = MMSTTSProvider(output_dir=str(tmp_path))
    result = provider.synthesize("   ", "hi")

    assert Path(result.audio_path).exists()


def test_synthesize_unsupported_language_raises_value_error(
    tmp_path: Path, mock_ml_deps: None
) -> None:
    provider = MMSTTSProvider(output_dir=str(tmp_path))
    with pytest.raises(ValueError, match="fr"):
        provider.synthesize("Hello.", "fr")
    assert FakeAutoTokenizer.load_count == 0


def test_lazy_load_happens_once_across_two_calls(tmp_path: Path, mock_ml_deps: None) -> None:
    provider = MMSTTSProvider(output_dir=str(tmp_path))

    provider.synthesize("Hello.", "hi")
    provider.synthesize("Goodbye.", "hi")

    assert FakeAutoTokenizer.load_count == 1
    assert FakeVitsModel.load_count == 1


def test_lazy_load_happens_per_language(tmp_path: Path, mock_ml_deps: None) -> None:
    provider = MMSTTSProvider(output_dir=str(tmp_path))

    provider.synthesize("Hello.", "hi")
    provider.synthesize("Hello.", "bn")

    assert FakeAutoTokenizer.load_count == 2
    assert FakeVitsModel.load_count == 2
