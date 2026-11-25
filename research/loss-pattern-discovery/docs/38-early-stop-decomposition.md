# Deliverable B — Early-Stop Decomposition (E0/E1/E2/E3/E4)

Same primary population and denominator as Phase 5 (2043 evaluable executed trades: 619 1AM, 1424
9AM). Reproduce: `uv run --project detector python
research/loss-pattern-discovery/stats/stop_timing_decomposition.py`.

## By model

| Category | 9AM n (%) | 1AM n (%) |
|---|---|---|
| Total evaluable | 1424 | 619 |
| E0 same-bar SL | 47 (3.30%) | 45 (7.27%) |
| E1 next-bar SL | 89 (6.25%) | 72 (11.63%) |
| E2 later SL | 751 (52.74%) | 258 (41.68%) |
| E3 otras salidas (win + ambiguous_stop) | 537 (37.71%) | 244 (39.42%) |
| Abiertas/censuradas (own denominator, n_total=1427/620) | 3 | 1 |

Identity check passed exactly: `rate(E0) + rate(E1) == rate(E0 OR E1)` for both models (floating-point
exact, `identity_holds=True` for both).

## Decomposing Phase 5's +9.35pp gap

| | Diff (1AM − 9AM) | 95% CI | Excludes 0? | ≥ 5pp relevance bar? |
|---|---|---|---|---|
| Gap_early (E0 ∪ E1, = Phase 5's endpoint) | **+9.35pp** | [5.85, 12.77] | Yes | Yes |
| Gap_E0 (same-bar only) | +3.97pp | [1.79, 6.27] | Yes | **No** (below 5pp) |
| Gap_E1 (next-bar only) | **+5.38pp** | [2.52, 8.26] | Yes | **Yes** |

`Gap_early` reproduces Phase 5's own `+9.35pp` number exactly (0.0935089... vs. the pre-registered
0.0935 -- matches to the reported precision). `sum_of_parts_matches_combined = True`:
`Gap_E0 + Gap_E1 == Gap_early` exactly, as an arithmetic identity (verified by test, not assumed).

**The gap is not concentrated in the same-bar (E0) component.** If anything, `Gap_E1` (+5.38pp) is
numerically larger than `Gap_E0` (+3.97pp), and only `Gap_E1` clears BOTH the statistical (CI
excludes 0) and the relevance (>=5pp) bars on its own. `Gap_E0`, while its CI also excludes 0, falls
short of the 5pp relevance bar by itself. This is the opposite of what a same-bar-engine-artifact
story alone would predict, and it is the central input to Unit D's sensitivity scenarios and the
Deliverable F verdict.

## By model and instrument (one-way, not a combined grid)

| 9AM | n | E0 % | E1 % | E2 % |
|---|---|---|---|---|
| EURUSD | 492 | 2.85% | 5.69% | 55.49% |
| USDCAD | 488 | 3.07% | 6.35% | 51.64% |
| AUDUSD | 444 | 4.05% | 6.76% | 50.90% |

| 1AM | n | E0 % | E1 % | E2 % |
|---|---|---|---|---|
| EURUSD | 143 | 9.79% | 16.78% | 30.77% |
| USDCAD | 207 | 8.70% | 13.53% | 38.16% |
| AUDUSD | 269 | 4.83% | 7.43% | 50.19% |

Consistent with Phase 5's own instrument heterogeneity (`docs/32`): AUDUSD's 1AM E0/E1 rates sit much
closer to its 9AM counterpart than EURUSD/USDCAD do, reinforcing that AUDUSD is where the whole
1AM/9AM association is weakest, in both the combined endpoint and its E0/E1 parts individually.
