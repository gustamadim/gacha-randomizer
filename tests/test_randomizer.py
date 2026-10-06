"""Correctness tests for the gacha-randomizer picker.

The picker's whole promise is "uniform, auditable, never empty". These tests
pin that with a deterministic stub source, so boundary behaviour is provable
without depending on chance.
"""
from __future__ import annotations

import pytest

from gacha_randomizer import DrawError, choose_index, odds, select, weights


def stub(value):
    """A randbelow stand-in that always returns a fixed value."""
    return lambda total: value


# -- weights ----------------------------------------------------------------

def test_weights_reads_the_field_for_each_mode():
    items = [{"weight": 3}, {"weight": 7}]
    assert weights("weighted", items) == [3, 7]
    finite = [{"remaining_count": 2}, {"remaining_count": 0}]
    assert weights("finite", finite) == [2, 0]


def test_bad_values_read_as_zero():
    items = [{"weight": None}, {"weight": "x"}, {"weight": -5}, {"weight": 4}]
    assert weights("weighted", items) == [0, 0, 0, 4]


# -- choose_index -----------------------------------------------------------

def test_choose_index_is_cumulative_and_never_misses():
    items = [{"weight": 1}, {"weight": 1}, {"weight": 1}]
    # total 3: 0 -> first, 1 -> second, 2 -> third
    assert choose_index("weighted", items, stub(0)) == 0
    assert choose_index("weighted", items, stub(1)) == 1
    assert choose_index("weighted", items, stub(2)) == 2


def test_choose_index_respects_weight_boundaries():
    items = [{"weight": 2}, {"weight": 3}]  # total 5
    assert choose_index("weighted", items, stub(0)) == 0
    assert choose_index("weighted", items, stub(1)) == 0  # last unit of item 0
    assert choose_index("weighted", items, stub(2)) == 1  # first unit of item 1
    assert choose_index("weighted", items, stub(4)) == 1


def test_choose_index_on_an_empty_pool_refuses():
    with pytest.raises(DrawError) as error:
        choose_index("weighted", [{"weight": 0}, {"weight": 0}])
    assert error.value.code == "pool_empty"


def test_choose_index_rejects_an_unknown_mode():
    with pytest.raises(DrawError) as error:
        choose_index("nope", [{"weight": 1}])
    assert error.value.code == "mode_invalid"


# -- select -----------------------------------------------------------------

def test_select_weighted_allows_repeats():
    items = [{"id": "a", "weight": 1}, {"id": "b", "weight": 1}]
    # always lands on the first item -> repeats
    assert select("weighted", items, 3, stub(0)) == ["a", "a", "a"]


def test_select_finite_draws_without_replacement():
    items = [{"id": "a", "remaining_count": 1}, {"id": "b", "remaining_count": 2}]
    # draw the whole stock (3); the algorithm simulates decrements, so a single
    # constant pick still returns each unit exactly once
    picks = select("finite", items, 3, stub(0))
    assert sorted(picks) == ["a", "b", "b"]


def test_select_finite_never_oversells():
    items = [{"id": "a", "remaining_count": 1}]
    with pytest.raises(DrawError) as error:
        select("finite", items, 2, stub(0))
    assert error.value.code == "not_enough_stock"


def test_select_rejects_a_bad_count():
    items = [{"id": "a", "weight": 1}]
    for bad in (0, -1, "x", None):
        with pytest.raises(DrawError) as error:
            select("weighted", items, bad, stub(0))
        assert error.value.code == "count_invalid"


# -- odds -------------------------------------------------------------------

def test_odds_match_the_weights():
    items = [{"weight": 1}, {"weight": 3}]
    rows = odds("weighted", items)
    assert [round(r["probability"], 4) for r in rows] == [0.25, 0.75]
    assert [r["display"] for r in rows] == ["25%", "75%"]


def test_odds_use_one_in_n_below_one_percent():
    items = [{"weight": 1}, {"weight": 1000}]
    rows = odds("weighted", items)
    assert rows[0]["display"] == "1 in 1001"


def test_odds_refuse_an_undrawable_pool():
    with pytest.raises(DrawError):
        odds("weighted", [{"weight": 0}])


# -- uniformity (statistical, seeded) ---------------------------------------

def test_choose_index_is_uniform_over_units():
    import random
    rng = random.Random(1234)
    items = [{"weight": 1}, {"weight": 2}, {"weight": 7}]  # total 10
    counts = [0, 0, 0]
    for _ in range(20000):
        counts[choose_index("weighted", items, lambda total: rng.randrange(total))] += 1
    # expected ~2000 / 4000 / 14000; allow generous slack
    assert 1800 < counts[0] < 2200
    assert 3700 < counts[1] < 4300
    assert 13500 < counts[2] < 14500
