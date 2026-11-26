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

Two units complete; stopped at the report for review each time, per this experiment's own closing
instruction. See `docs/02-results-and-report.md` for the first experiment's full report (with its
`docs/05` correction), and `docs/08-thirteen-oclock-results.md` for the second unit -- which asks a
narrower, corrected question: among 9AM confirmations that resolve EXACTLY at 13:00 NY (where the
close and the order-placement decision are the same event), what would requiring a strictly-inside
close have changed historically? `docs/00` is the verified sibling-lab checkpoint; `docs/01` and
`docs/07` are this experiment's two pre-registered protocols.

## Layout

```
research/raza-crt-candle2-9am/
  README.md
  docs/
    00-checkpoint-handoff.md         verified sibling-lab checkpoint + Phase 8-10 reconciliation
    01-protocol.md                  Unit 1 pre-registered protocol
    raza-crt-thread.md              full transcription of the attached Raza PDF
    02-results-and-report.md        Unit 1 results report (see its own correction banner)
    03-technical-checkpoint.md      Unit 1 files, counts, tests, reproduction commands
    04-commit-record.md             Unit 1 commit SHA
    05-correction-2026-11-26.md     dated correction to Unit 1's interpretation
    06-session-trace.md             one real session traced end-to-end; the event-ordering check
    07-thirteen-oclock-protocol.md  Unit 2 pre-registered protocol (committed before its outcomes)
    08-thirteen-oclock-results.md   Unit 2 results report
  raza_extract/                     classification + per-symbol orchestration + chart rendering +
                                     the 13:00-confirmation baseline/variant instrumentation
                                     (named raza_extract, not extract, to avoid a package-name
                                     collision with the sibling lab's own `extract` package)
  raza_stats/                       funnel/outcome/timeline aggregation reports (both units)
  tests/                            16 tests (synthetic + real-data)
  artifacts/                        gitignored, regenerable JSON
  figures/                          gitignored, regenerable PNGs (Unit 1's 4 chart examples)
```

## Reproducing

```bash
cd detector && uv sync --extra dev   # once, per worktree
uv run python -m pytest ../research/raza-crt-candle2-9am/tests   # 16 tests

# Unit 1
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save.py EURUSD
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save.py USDCAD
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save.py AUDUSD
uv run python ../research/raza-crt-candle2-9am/raza_stats/funnel_and_outcome_report.py
uv run python ../research/raza-crt-candle2-9am/raza_extract/render_chart_examples.py

# Unit 2 (13:00-exact confirmations, baseline vs. close-gated variant)
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save_thirteen_oclock.py EURUSD
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save_thirteen_oclock.py USDCAD
uv run python ../research/raza-crt-candle2-9am/raza_extract/build_and_save_thirteen_oclock.py AUDUSD
uv run python ../research/raza-crt-candle2-9am/raza_stats/thirteen_oclock_report.py

uv run lint-imports   # from detector/
```

## Read-only boundary

Never writes to, or depends on side effects from: `docs/` (the Mado charters), `detector/`,
`scanner/`, `research/loss-pattern-discovery/` (read-only reuse of its own already-verified
functions), the original D3/C2 pipeline, or the original historical ledgers.
