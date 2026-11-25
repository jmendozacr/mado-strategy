# Deliverable B — Pre-Stop Trajectory Reconstruction

Implementation: `behavior/pre_stop_trajectory.py`, applied to the 1262 `CONFIRMED_STOP`/
`STOP_AFTER_PARTIAL` events only (the same eligible population as Phase 2/3's own Atlas).

## How each trajectory is reconstructed

1. `entry_index`/`exit_index` located via `bisect_left` on the M15 series (exact match, since
   `entry_ts`/`exit_ts` are themselves M15 bar timestamps).
2. `duration_bars = exit_index - entry_index`; `duration_s = exit_ts - entry_ts`.
3. The PRIMARY MFE/MAE-pre-SL window is bars strictly between `entry_index` and `exit_index`
   (`entry_index+1 .. exit_index-1`) -- both the entry and exit bar are excluded, because each has
   an unresolvable intrabar order relative to the trade's own fill/stop instant.
4. If that window is empty (`duration_bars <= 1`): `integrity = INSUFFICIENT` (same bar,
   `duration_bars == 0`) or `AMBIGUOUS` (adjacent bars, `duration_bars == 1`) -- MFE/MAE-pre-SL are
   `None`, never 0.
5. Otherwise `integrity = RECONSTRUCTIBLE`: MFE/MAE-pre-SL, the best-favorable price and its
   retracement down to the ACTUAL executed `exit_price` (never the planned `stop_loss` -- verified
   under a gap-fill scenario), the share of middle bars closing favorably/adversely, and an average
   adverse-speed figure are all computed from that window alone.
6. Two SEPARATE, always-computed sensitivity variants (`mfe_including_entry_bar_r`,
   `mfe_including_exit_bar_r`) report what the primary number would look like if the entry or exit
   bar's own range were (wrongly) included -- never blended into the primary figure.

## Cases that cannot be evaluated completely

| Integrity | n | % of 1262 | Meaning |
|---|---|---|---|
| `reconstructible` | 1009 | 79.95% | >=1 unambiguous bar between entry and exit |
| `ambiguous` | 161 | 12.76% | entry and exit are adjacent bars -- zero observable middle bars, but at least distinguishable |
| `insufficient` | 92 | 7.29% | entry and exit are the SAME bar (immediate fill-and-stop) -- no path structure at all |

Combined, **20.05% of confirmed stops cannot have a primary MFE/MAE-pre-SL computed** -- reported
as `excursion_class = UNKNOWN` throughout Deliverable D, never silently folded into "no favorable
excursion."

## Real-data results (reconstructible population only, n=1009)

| Metric | Median | P10 | P25 | P75 | P90 |
|---|---|---|---|---|---|
| Duration (bars, full 1262 population) | 6 | 1 | 2 | 19 | 45 |
| MFE pre-SL (R) | 0.55 | 0.00 | 0.21 | 0.94 | 1.35 |
| MAE pre-SL (ATR) | 1.10 | 0.54 | 0.82 | 1.36 | 1.64 |
| Retracement from best favorable price (price units) | 0.002 | 0.001 | 0.001 | 0.003 | 0.004 |
| % middle bars closed favorably | 42.9% | 0.0% | 28.6% | 50.0% | 56.5% |

Duration is heavily right-skewed: a tenth of failures resolve within 1 bar, but a tenth take 45+
bars (11+ hours). The median MFE-pre-SL (0.55R) is ABOVE the 0.25R "material excursion" threshold --
most reconstructible failures show at least some real favorable movement before failing, not a
straight slide to the stop. See `docs/26-...` for the full cross-tabulation with duration.
