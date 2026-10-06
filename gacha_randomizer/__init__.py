"""gacha-randomizer — a transparent, auditable random picker.

This package is the exact selection algorithm Gachasik (https://gacha.gustamadh.my.id)
uses to pick items from a pool. It is published so anyone can verify how a
draw is chosen: the pick is uniform over the pool's drawable units, it comes
from a cryptographic source (``secrets``), and it can never return an empty
result. Nothing here is game-specific plumbing — it is plain, dependency-free
math plus a single call to a random source you can substitute in tests.

Two pool modes:

- ``weighted``  — every item has a weight; P(item) = weight / sum(weights).
- ``finite``    — every item has a remaining count; P(item) = count / sum(counts),
                  and a batch draws without replacement so it can never oversell.

Public API:

    from gacha_randomizer import choose_index, select, weights, odds

    index = choose_index("weighted", items)        # one draw, returns an index
    ids   = select("finite", items, 3)             # three draws, no replacement
    rows  = odds("weighted", items)                # per-item probability + display
"""
from __future__ import annotations

import secrets

__all__ = ["DrawError", "choose_index", "select", "odds", "weights", "SOURCE"]

#: The default random source. ``secrets.randbelow`` draws from the operating
#: system CSPRNG — unpredictable and not seeded by Python's ``random``.
SOURCE = secrets.randbelow

#: The pool modes this library understands.
MODES = ("weighted", "finite")


class DrawError(ValueError):
    """A pool cannot be drawn from, in operator terms.

    ``code`` carries the machine-readable reason, matching the flash codes the
    host application shows: ``pool_empty``, ``not_enough_stock``,
    ``count_invalid``, ``mode_invalid``.
    """

    def __init__(self, message: str, code: str = "draw_error"):
        super().__init__(message)
        self.code = code


def _units(item, mode: str) -> int:
    """One item's drawable units for the mode; a bad value counts as 0.

    Missing fields, non-numbers, and negatives all read as 0 rather than
    raising: a malformed row must never make the whole picker throw. If every
    row reads 0 the pool is simply empty, which :func:`choose_index` refuses.
    """
    field = "weight" if mode == "weighted" else "remaining_count"
    value = item.get(field)
    if value is None:
        return 0
    try:
        number = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, number)


def _check_mode(mode: str) -> None:
    if mode not in MODES:
        raise DrawError(f"unknown pool mode {mode!r}", code="mode_invalid")


def weights(mode: str, items) -> list[int]:
    """The drawable units per item, in order (weights or remaining stock)."""
    _check_mode(mode)
    return [_units(item, mode) for item in items]


def choose_index(mode: str, items, randbelow=SOURCE) -> int:
    """The index of the item one draw lands on; never empty.

    ``randbelow`` receives the total drawable units and must return an integer
    in ``[0, total)``; the default is ``secrets.randbelow``. Because the pick
    is uniform over the total, every unit of weight (or every unit of stock)
    is equally likely, so P(item) = units(item) / total.

    Raises :class:`DrawError` with code ``pool_empty`` when nothing can be
    drawn (empty pool, all weights zero, all stock gone).
    """
    totals = weights(mode, items)
    total = sum(totals)
    if total <= 0:
        raise DrawError("nothing to draw from this pool", code="pool_empty")
    pick = randbelow(total)
    cumulative = 0
    for index, units in enumerate(totals):
        cumulative += units
        if pick < cumulative:
            return index
    # Unreachable for a correct randbelow; kept as a guard, not a fallback.
    raise DrawError("nothing to draw from this pool", code="pool_empty")


def select(mode: str, items, count: int, randbelow=SOURCE) -> list:
    """Pick ``count`` items' ``id`` values.

    For ``finite`` pools, draws are **without replacement within the batch**:
    each pick is removed from the running totals before the next, so a batch
    can never oversell an item and drawing the whole remaining stock returns
    exactly the stock left. For ``weighted`` pools items can repeat.

    Raises :class:`DrawError` with code ``count_invalid`` for a non-positive
    count, or ``not_enough_stock`` when a finite pool cannot cover ``count``.
    """
    try:
        number = int(count)
    except (TypeError, ValueError):
        number = None
    if number is None or number < 1:
        raise DrawError("count must be a positive whole number", code="count_invalid")

    if mode == "finite":
        remaining = sum(weights(mode, items))
        if remaining <= 0:
            raise DrawError("nothing to draw from this pool", code="pool_empty")
        if number > remaining:
            raise DrawError("not enough stock remaining", code="not_enough_stock")
        working = [dict(item) for item in items]
        picks = []
        for _ in range(number):
            index = choose_index(mode, working, randbelow)
            picks.append(working[index]["id"])
            working[index]["remaining_count"] = _units(working[index], mode) - 1
        return picks

    return [items[choose_index(mode, items, randbelow)]["id"] for _ in range(number)]


def _format_probability(probability: float) -> str:
    """Percent at 1% and above, else the "1 in N" form; zero shows as "0%"."""
    if probability <= 0:
        return "0%"
    if probability >= 0.01:
        text = f"{probability * 100:.1f}".rstrip("0").rstrip(".")
        return f"{text}%"
    return f"1 in {round(1 / probability)}"


def odds(mode: str, items) -> list[dict]:
    """Per-item probability and display form, in the items' order.

    ``{"item": item, "probability": float, "display": "12.5%" | "1 in 1000"}``.
    Probabilities sum to 1. Raises :class:`DrawError` when nothing is drawable.
    """
    items = list(items)
    units = weights(mode, items)
    total = sum(units)
    if total <= 0:
        raise DrawError("nothing to draw from: all weights or stock are zero",
                        code="pool_empty")
    return [
        {"item": items[i], "probability": units[i] / total,
         "display": _format_probability(units[i] / total)}
        for i in range(len(items))
    ]
