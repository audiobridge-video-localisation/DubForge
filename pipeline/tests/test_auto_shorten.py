from dubforge_pipeline.auto_shorten import MAX_REWRITE_TRIES, shorter_alternatives


def test_only_clearly_shorter_wordings_are_considered() -> None:
    current = "x" * 40
    candidates = [current, "y" * 39, "z" * 36, "w" * 10]  # same, barely shorter, 90%, much shorter

    result = shorter_alternatives(candidates, current, room_ms=1000, ms_per_char=90.0)

    assert "y" * 39 not in result and current not in result
    assert set(result) <= {"z" * 36, "w" * 10}


def test_wordings_predicted_to_fit_keep_the_translators_ranking() -> None:
    # room 1000 ms -> up to 1300 ms; at 100 ms per char that is 13 characters
    current = "x" * 40
    candidates = [current, "a" * 12, "b" * 8, "c" * 20]

    assert shorter_alternatives(candidates, current, 1000, 100.0) == ["a" * 12, "b" * 8]


def test_when_none_fit_the_shortest_come_first() -> None:
    current = "x" * 60
    candidates = [current, "a" * 50, "b" * 30, "c" * 40]

    assert shorter_alternatives(candidates, current, 1000, 100.0) == ["b" * 30, "c" * 40]


def test_the_number_of_tries_is_capped() -> None:
    current = "x" * 60
    candidates = [current] + ["a" * n for n in range(5, 15)]

    assert len(shorter_alternatives(candidates, current, 1000, 100.0)) == MAX_REWRITE_TRIES


def test_repeats_and_blanks_are_ignored() -> None:
    current = "x" * 40

    assert shorter_alternatives(["", "a" * 5, "a" * 5], current, 1000, 100.0) == ["a" * 5]
