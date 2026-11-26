# Deliverable D — Confirmation Path Distribution

Reproduce: `uv run --project detector python research/loss-pattern-discovery/stats/confirmation_path_distribution.py`.
Computed BEFORE any E1 result was inspected (execution order step 8, before step 9's baseline
reproduction) -- this document's numbers were written first, then Deliverable E ran.

## Full confirmed-signal population (all 3 pairs, before any execution/outcome filter)

| | 1AM | 9AM |
|---|---|---|
| Confirmed signals | 1805 | 3311 |
| `internal_invalidation_count == 0` | 1317 (**72.96%**) | 1856 (**56.06%**) |
| `internal_invalidation_count >= 1` | 488 (27.04%) | 1455 (43.94%) |

**9AM has nearly double the share of signals needing at least one internal invalidation before
confirming (43.9% vs. 1AM's 27.0%).** This composition difference is reported descriptively; see
Deliverable E/F for why it is never used to attribute the 1AM/9AM E1 gap causally to window
duration.

## `internal_invalidation_count` full distribution

| Count | 1AM | 9AM |
|---|---|---|
| 0 | 1317 | 1856 |
| 1 | 345 | 731 |
| 2 | 113 | 408 |
| 3 | 26 | 192 |
| 4 | 4 | 78 |
| 5 | 0 | 33 |
| 6 | 0 | 9 |
| 7 | 0 | 3 |
| 8 | 0 | 1 |

9AM's longer confirmation window (240 vs. 120 minutes) structurally gives the SAME unchanged
retry mechanics more room to accumulate restarts before either confirming or exhausting --
consistent with, though not a demonstration of, the window-duration correlate already named in
Phase 9's own structural comparison.

## By instrument (consistency check, zero-invalidation share)

| | 1AM | 9AM |
|---|---|---|
| EURUSD | 73.8% | 56.0% |
| USDCAD | 73.9% | 56.0% |
| AUDUSD | 70.8% | 56.2% |

Stable within 3 percentage points across all three instruments, for both models -- not a
single-pair artifact.

## By period (consistency check, zero-invalidation share)

| Period | 1AM | 9AM |
|---|---|---|
| 2015-2017 | 76.3% | 57.2% |
| 2018-2020 | 74.5% | 56.5% |
| 2021-2023 | 68.6% | 54.4% |
| 2024-2026 | 72.9% | 56.3% |

Stable within 8 percentage points across all four periods for 1AM, within 3 for 9AM -- not a
single-era artifact. No category here was selected by looking at E1 (that result had not yet
been computed when this table was built).
