from pathlib import Path

import pytest

from dubforge_pipeline.speech_rate import (
    DEFAULT_MS_PER_CHAR,
    SMOOTHING,
    get_ms_per_char,
    record_take,
)


def test_unknown_voice_uses_the_default(tmp_path: Path) -> None:
    assert get_ms_per_char(str(tmp_path), "V:hi") == DEFAULT_MS_PER_CHAR


def test_first_take_sets_the_rate_at_natural_pace(tmp_path: Path) -> None:
    # 20 chars in 1000 ms spoken at 2x means 100 ms per char at natural pace
    record_take(str(tmp_path), "V:hi", "x" * 20, 1000, speech_rate=2.0)

    assert get_ms_per_char(str(tmp_path), "V:hi") == pytest.approx(100.0)


def test_later_takes_move_the_average_gradually(tmp_path: Path) -> None:
    record_take(str(tmp_path), "V:hi", "x" * 10, 1000, speech_rate=1.0)  # 100 ms/char
    record_take(str(tmp_path), "V:hi", "x" * 10, 500, speech_rate=1.0)  # 50 ms/char

    assert get_ms_per_char(str(tmp_path), "V:hi") == pytest.approx(100 + SMOOTHING * (50 - 100))


def test_voices_are_kept_apart(tmp_path: Path) -> None:
    record_take(str(tmp_path), "A:hi", "x" * 10, 1000, speech_rate=1.0)

    assert get_ms_per_char(str(tmp_path), "B:hi") == DEFAULT_MS_PER_CHAR


@pytest.mark.parametrize(
    ("text", "duration_ms", "rate"), [("", 1000, 1.0), ("x", 0, 1.0), ("x", 5, 0)]
)
def test_meaningless_takes_are_ignored(
    tmp_path: Path, text: str, duration_ms: int, rate: float
) -> None:
    record_take(str(tmp_path), "V:hi", text, duration_ms, rate)

    assert get_ms_per_char(str(tmp_path), "V:hi") == DEFAULT_MS_PER_CHAR


def test_a_damaged_file_falls_back_to_the_default(tmp_path: Path) -> None:
    (tmp_path / ".speech_rate.json").write_text("{not json")

    assert get_ms_per_char(str(tmp_path), "V:hi") == DEFAULT_MS_PER_CHAR
