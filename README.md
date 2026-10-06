# gacha-randomizer

A small, dependency-free, **transparent random picker** — the exact selection
algorithm used by [Gachasik](https://gacha.gustamadh.my.id) to draw items from
a pool. It is published so anyone can verify how a draw is decided: the pick is
**uniform** over the pool's drawable units, comes from a **cryptographic**
source, and **can never return an empty result**.

This is not a game of chance engine. It is a recorded, auditable picker: one
call in, one item out, deterministic maths you can read end to end.

## Why it is auditable

- **Uniform.** `choose_index` picks one integer in `[0, total)` and walks the
  cumulative weights, so every unit of weight (or stock) is equally likely.
  P(item) = units(item) / total.
- **Cryptographic.** The default source is `secrets.randbelow` — the operating
  system CSPRNG, never Python's seeded `random`.
- **Never empty.** An undrawable pool (no items, all weights zero, all stock
  gone) raises a typed `DrawError` instead of returning nothing.
- **Testable.** The random source is a parameter, so boundaries are provable
  with a stub and uniformity is testable with a seeded generator.
- **~150 lines.** No dependencies, no I/O, no hidden state.

## Install

```bash
pip install gacha-randomizer
# or, from source:
git clone <this repo> && cd gacha-randomizer && pip install -e .
```

## Use

```python
from gacha_randomizer import choose_index, select, odds

# one draw from a weighted pool -> the index that was picked
items = [{"id": "common", "weight": 70}, {"id": "rare", "weight": 30}]
i = choose_index("weighted", items)

# a batch of 3 from a finite-stock pool -> ids, drawn WITHOUT replacement
stock = [{"id": "A", "remaining_count": 2}, {"id": "B", "remaining_count": 5}]
ids = select("finite", stock, 3)

# the odds a buyer would see, per item
for row in odds("weighted", items):
    print(row["item"]["id"], row["display"])   # common 70%  /  rare 30%
```

### Modes

| Mode | Field | Rule |
|---|---|---|
| `weighted` | `weight` | P(item) = weight / Σweights; repeats allowed |
| `finite` | `remaining_count` | P(item) = count / Σcounts; a batch draws **without replacement** so it can never oversell |

### API

- `choose_index(mode, items, randbelow=secrets.randbelow) -> int`
- `select(mode, items, count, randbelow=...) -> list` (item `id`s)
- `odds(mode, items) -> [{"item", "probability", "display"}]`
- `weights(mode, items) -> list[int]`
- `DrawError(message, code)` — codes: `pool_empty`, `not_enough_stock`,
  `count_invalid`, `mode_invalid`

## Verify it yourself

```bash
python -m pytest -q
```

The tests prove the boundary behaviour with a stub source, prove finite draws
never oversell, and check uniformity statistically with a seeded generator.

### CI

A GitHub Actions workflow (`.github/workflows/tests.yml`) runs the suite on
push/PR across Python 3.9 and 3.12. **Actions is currently disabled at the
account level on GitHub**, so it will not run until that is re-enabled in the
owner's account settings. Until then, a **pre-push hook** (`.githooks/pre-push`,
wired via `git config core.hooksPath .githooks`) runs the suite locally before
any push — the same tests, no account needed.

## Design notes

`choose_index` sums the drawable units, asks the source for a number below that
total, then walks a cumulative sum and stops where the number lands. The item
whose cumulative band contains the pick wins. This is the standard inverse-CDF
method for a discrete distribution; it is exact and needs no floating point in
the selection path.

Finite batches simulate the stock decrement in memory before each subsequent
pick, so the whole batch is consistent even though the caller's rows are not
mutated.

## License

MIT — see [LICENSE](LICENSE).
