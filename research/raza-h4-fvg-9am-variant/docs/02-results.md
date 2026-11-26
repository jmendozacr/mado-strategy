# Results — Raza H4 FVG Setup + Mado Model-1 M15 Entry, 9AM Session

Protocol: `docs/01-protocol.md` (committed before any outcome below was computed). Source:
`artifacts/h4fvg_report.json`, produced by `raza_h4fvg_stats/report.py` over the three per-symbol
session artifacts (`raza_h4fvg/build_and_save.py`, one process per symbol, full 2015+ history).

## Headline finding: the proposed sequence is extremely restrictive

Of **13,002 NY-session-days** (3 pairs x 4,334 days each), only **242 (1.9%) reach a qualifying
H4 setup**, and only **12 (0.09%) ever produce an executed trade** -- roughly one trade per
instrument per YEAR. The daily-bias filter alone removes 81.8% of all days (`NO_DAILY_BIAS`,
10,638 of 13,002) -- this is the single largest attrition point by far, consistent with the
brief's own framing of it as "a deliberately narrow definition."

## Funnel (pooled, 3 pairs)

| Stage / outcome | n | % of all sessions |
|---|---|---|
| Total sessions | 13,002 | 100% |
| `NO_DAILY_BIAS` | 10,638 | 81.8% |
| `NOT_INSIDE` (H4) | 931 | 7.2% |
| `MISSING_DATA` | 628 | 4.8% |
| `DISAGREES_WITH_DAILY_BIAS` | 280 | 2.2% |
| `NO_SWEEP` (H4) | 154 | 1.2% |
| `DOUBLE_SWEEP` (H4) | 127 | 1.0% |
| `NO_MATCHING_GAP` | 2 | 0.02% |
| **Qualifying H4 setup** | **242** | **1.9%** |
| &nbsp;&nbsp;`EXPIRED` | 129 | (53.3% of qualifying) |
| &nbsp;&nbsp;`DISCARD_SWEPT_EXTREME_BREACH` | 36 | (14.9%) |
| &nbsp;&nbsp;`DISCARD_TARGET_BEFORE_ENTRY` | 31 | (12.8%) |
| &nbsp;&nbsp;`RR_FLOOR_REJECTED` | 21 | (8.7%) |
| &nbsp;&nbsp;`UNFILLED_ORDER` | 13 | (5.4%) |
| &nbsp;&nbsp;**`ENTERED`** | **12** | **(5.0%)** |

**By instrument**: EURUSD 3/80 qualifying setups entered, USDCAD 4/82, AUDUSD 5/80 -- consistent,
narrow across all three pairs, not a single-pair artifact.

## Net R per qualifying H4 setup (the brief's own primary metric)

Pooled: **mean +0.0276R per qualifying setup** (n=242, including the 230 that never enter and
contribute 0), **total net R = +6.67R** across all 12 years, 3 pairs combined.

**The 12 `ENTERED` trades' own R values**: -1.22, -1.22, -1.17, -1.15, -1.14, -1.13, -1.13, -1.09,
+0.59, +1.72, +1.92, **+11.68**.

**The entire positive total result depends on a single outlier.** Verified directly (not assumed):
the +11.68R trade (EURUSD, 2015-10-28) is a genuine large intrabar price gap -- the exit candle's
own open already lay far beyond the planned take-profit level, resolved by `_exit_gap_beyond`'s own
existing, already-tested gap-fill logic (reused unmodified; `gap_filled=True` on the real `Trade`
object). **Removing that single trade, the remaining 11 trades sum to -5.01R** -- the strategy's
own total result flips sign depending on one tail event, out of 12 years of data. This is reported
plainly, not smoothed over: with n=12, a single data point determines the pooled sign.

By instrument: EURUSD +9.38R total (entirely the one outlier -- the other 2 EURUSD trades sum to
-2.30R), USDCAD -4.51R total (all 4 losses), AUDUSD +1.80R total (2 losses, 3 wins).

## Comparison with the original D3/C2 9AM population (same instruments, same dates)

| | Both execute | Only this variant | Only D3/C2 | Neither |
|---|---|---|---|---|
| EURUSD | 0 | 3 | 493 | 3,838 |
| USDCAD | 1 | 3 | 488 | 3,842 |
| AUDUSD | 2 | 3 | 443 | 3,886 |
| **Pooled** | **3** | **9** | **1,424** | **11,566** |

**This variant and the original D3/C2 9AM population are almost entirely disjoint.** Of D3/C2's own
1,427 executed 9AM sessions, only 3 also produce a variant entry (0.2%); of this variant's 12
entries, 9 occur on days D3/C2 never executes at all. This is expected, not surprising: the two
systems use structurally different trigger conditions (no daily-bias or FVG-gap requirement in
D3/C2; a 09:00-13:00 M15 search window there vs. this variant's 13:00-15:00 window) -- the overlap
being this small is itself informative about how little these two selection mechanisms share.

## Pre-declared stop condition applied

Per `docs/01`'s own pre-registration: **with only 12 `ENTERED` trades pooled across 12 years and 3
pairs, this sample is too small for a useful statistical conclusion about the variant's own edge.**
No confidence interval, significance test, or win-rate claim is computed on n=12 -- doing so would
manufacture false precision. The funnel counts and the R values are reported descriptively, exactly
as observed, with the single-outlier dependency stated plainly above.

## Conclusion

**How restrictive is the proposed sequence?** Extremely -- about 1 entered trade per instrument
per year, driven mostly by the daily-bias filter (removes 82% of all days by itself), with the H4
FVG-gap-sweep-back-inside requirement and the fresh 13:00-15:00 Model-1 search each removing most of
what little remains.

**What does the data show for the 12 historical opportunities that did qualify and fill?** A small,
inconclusive sample whose aggregate sign depends entirely on one large intrabar gap -- 8 of 12 are
ordinary ~-1.1R stop losses, 3 are modest wins, and 1 is an extreme outlier that alone turns a
negative total into a positive one.

**What does the evidence support about this specific decision sequence?** That it is reproducible
and mechanically sound (every stage reuses already-verified production logic; the funnel counts are
internally consistent and reconcile against the sibling lab's own established D3/C2 baseline where
they overlap) -- but the evidence does **not** support any claim about whether this five-condition
sequence has a real edge, positive or negative. Twelve trades, mostly disjoint from the existing
D3/C2 population, is not enough to say. Adoption, wider trading hours, and any detector/scanner
change are explicitly left for review, per the brief's own closing instruction.
