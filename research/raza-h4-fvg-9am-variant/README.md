# Raza H4 FVG Setup + Mado Model-1 M15 Entry — 9AM Session Variant

A new, explicitly authorized research variant (see `docs/00-checkpoint-and-scope.md` for why this
departs from every prior unit's "no new strategy construction" boundary): after a 9AM NY H4 candle
sweeps one side of the preceding H4 range into a known fair-value gap and closes back inside, does
a fresh M15 Model-1 setup (searched only from 13:00 NY onward, direction fixed by a daily-bias
filter) offer an executable entry toward the opposite side?

**Kept entirely separate** from `research/loss-pattern-discovery/` and
`research/raza-crt-candle2-9am/` -- its own protocol, its own results, its own test suite, reusing
the production D3/C2 pipeline's own functions (never a new price formula) read-only.

## Status

Analysis complete. See `docs/02-results.md` for the full report. **Headline finding: the proposed
five-condition sequence is extremely restrictive** (1.9% of session-days reach a qualifying H4
setup; only 12 trades execute across 12 years, 3 pairs) -- too small a sample for any statistical
conclusion, per the protocol's own pre-declared stop condition. Not yet committed -- pending review.

## Layout

```
research/raza-h4-fvg-9am-variant/
  README.md
  docs/
    00-checkpoint-and-scope.md   verified checkpoint + explicit new-scope authorization record
    01-protocol.md              pre-registered decision sequence + outcome taxonomy
    02-results.md               the full results report
  raza_h4fvg/                   candles.py (generic bucket/sweep-close reconstruction),
                                 daily_bias.py, h4_setup.py, m15_entry.py,
                                 candidate_and_fill.py, orchestrate.py, build_and_save.py
  raza_h4fvg_stats/             report.py (funnel, net R, D3/C2 comparison)
  tests/                        26 tests (synthetic worked examples + real-data smoke tests)
  artifacts/                    gitignored, regenerable JSON
```

## Reproducing

```bash
cd detector && uv sync --extra dev   # once, per worktree
uv run python -m pytest ../research/raza-h4-fvg-9am-variant/tests   # 26 tests

uv run python ../research/raza-h4-fvg-9am-variant/raza_h4fvg/build_and_save.py EURUSD
uv run python ../research/raza-h4-fvg-9am-variant/raza_h4fvg/build_and_save.py USDCAD
uv run python ../research/raza-h4-fvg-9am-variant/raza_h4fvg/build_and_save.py AUDUSD
uv run python ../research/raza-h4-fvg-9am-variant/raza_h4fvg_stats/report.py

uv run lint-imports   # from detector/
```

## Read-only boundary

Never writes to, or depends on side effects from: `docs/` (the Mado charters), `detector/`,
`scanner/`, `research/loss-pattern-discovery/`, `research/raza-crt-candle2-9am/`, the original
D3/C2 pipeline, the original historical ledgers, or `audit/trader-algorithm-fidelity/` (untouched,
unrelated to this authorization).
