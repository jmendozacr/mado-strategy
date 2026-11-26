# Raza "Close-Back-Inside" Rule — 9AM D3/C2 Experiment

A single, isolated, observational experiment: among the real historical 9AM D3/C2 baseline
activations (same instruments, dates, and production pipeline as the sibling
`research/loss-pattern-discovery` lab's own verified Phase 8-10 baseline), how often does the
09:00-13:00 New York H4 candle ultimately close back inside the 05:00-09:00 New York reference
range after sweeping it (Raza's "candle 2 closes its body back inside" rule), and how do the
ORIGINAL trade outcomes differ across the resulting groups?

**Kept deliberately separate from `research/loss-pattern-discovery/`** -- its own protocol, its own
results, its own test suite, reusing that lab's and the production D3/C2 pipeline's code read-only.
Mado's charters remain this project's own strategy reference; Raza's thread is used here strictly
as a research lens for this one question.

## Status

Analysis complete; stopped at the report for review, per this experiment's own closing instruction.
No commit has been made. See `docs/02-results-and-report.md` for the full report, `docs/00` for the
verified checkpoint this builds on, and `docs/01` for the pre-registered protocol.

## Layout

```
research/raza-crt-candle2-9am/
  README.md
  docs/
    00-checkpoint-handoff.md         verified sibling-lab checkpoint + Phase 8-10 reconciliation
    01-protocol.md                  pre-registered population/classification/comparison plan
    raza-crt-thread.md              full transcription of the attached Raza PDF
    02-results-and-report.md        the full results report
    03-technical-checkpoint.md      files, counts, tests, reproduction commands, limitations
  raza_extract/                     classification + per-symbol orchestration + chart rendering
                                     (named raza_extract, not extract, to avoid a package-name
                                     collision with the sibling lab's own `extract` package)
  raza_stats/                       funnel/outcome/timeline aggregation report
  tests/                            9 tests (synthetic + real-data)
  artifacts/                        gitignored, regenerable JSON (per-symbol classifications +
                                     the merged funnel/outcome report)
  figures/                          gitignored, regenerable PNGs (the 4 pre-declared chart examples)
```

## Reproducing

```bash
cd detector && uv sync --extra dev   # once, per worktree
uv run python -m pytest ../research/raza-crt-candle2-9am/tests   # 9 tests
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save.py EURUSD
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save.py USDCAD
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save.py AUDUSD
uv run python ../research/raza-crt-candle2-9am/raza_stats/funnel_and_outcome_report.py
uv run python ../research/raza-crt-candle2-9am/raza_extract/render_chart_examples.py
uv run lint-imports   # from detector/
```

## Read-only boundary

Never writes to, or depends on side effects from: `docs/` (the Mado charters), `detector/`,
`scanner/`, `research/loss-pattern-discovery/` (read-only reuse of its own already-verified
functions), the original D3/C2 pipeline, or the original historical ledgers.
