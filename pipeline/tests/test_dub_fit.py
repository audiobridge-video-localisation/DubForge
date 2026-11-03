import pytest

from dubforge_pipeline.dub_fit import (
    MAX_NATURAL_RATE,
    is_too_long,
    speedup_for,
    tolerance_ms,
)


def test_tolerance_is_the_larger_of_the_absolute_and_relative_allowance() -> None:
    assert tolerance_ms(1000) == 300  # 25% would be 250
    assert tolerance_ms(4000) == 1000  # 25% beats the 300 ms floor


@pytest.mark.parametrize(
    ("current_ms", "target_ms", "expected"),
    [(1300, 1000, False), (1301, 1000, True), (500, 1000, False), (5001, 4000, True)],
)
def test_only_audio_beyond_tolerance_is_too_long(
    current_ms: int, target_ms: int, expected: bool
) -> None:
    assert is_too_long(current_ms, target_ms) is expected


def test_speedup_aims_inside_the_tolerance_not_at_the_edge() -> None:
    # target 2000 -> tolerance 500, aim 2250: 3375 ms needs 1.5x
    assert speedup_for(3375, 2000, max_rate=2.0) == pytest.approx(1.5)


def test_speedup_is_capped_and_never_slows_speech_down() -> None:
    assert speedup_for(9000, 1000, MAX_NATURAL_RATE) == MAX_NATURAL_RATE
    assert speedup_for(500, 1000, MAX_NATURAL_RATE) == 1.0
    assert speedup_for(0, 1000, MAX_NATURAL_RATE) == 1.0
