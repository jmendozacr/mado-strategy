# Results — Raza Close-Back-Inside Rule Applied to the 9AM D3/C2 Reference Candle

Checkpoint, source paths, and protocol: `docs/00-checkpoint-handoff.md`, `docs/01-protocol.md`.
Source material: `docs/raza-crt-thread.md` (full transcription of the attached PDF). All numbers
below come from `artifacts/raza_9am_funnel_and_outcome_report.json`, produced by
`raza_stats/funnel_and_outcome_report.py` over the three per-symbol classification artifacts
(`raza_extract/build_and_save.py`, one process per symbol -- same OOM workaround as the sibling
lab's own Phases 9/10).

## A. Data coverage and reconciliation

Population: **8,712 9AM D3/C2 baseline activations** (EURUSD/USDCAD/AUDUSD, 2015-01-01+) --
identical in count to the already-verified Phase 8-10 baseline (`docs/00`). Zero reconciliation
gaps: every funnel total below (3,311 confirmed; 1,806 candidates; 1,427 filled/executed; 4... -- 3
open for 9AM specifically, 1,424 evaluable) matches that baseline exactly. Zero ledger-join
mismatches (`n_ledger_mismatches: 0`).

## B. Funnel by close-position group

| Group | Activations | Confirmed | Candidate | Filled/executed | Evaluable (closed) | Open |
|---|---|---|---|---|---|---|
| **INSIDE** | 3,537 (40.6%) | 1,689 (47.8% of act.) | 791 (46.8% of conf.) | 531 (67.1% of cand.) | 530 | 1 |
| **OUTSIDE** | 5,149 (59.1%) | 1,612 (31.3% of act.) | 1,012 (62.8% of conf.) | 894 (88.3% of cand.) | 892 | 2 |
| **EXACT_BOUNDARY** | 25 (0.3%) | 10 (40.0% of act.) | 3 (30.0% of conf.) | 2 (66.7% of cand.) | 2 | 0 |
| **MISSING_OR_INCOMPLETE** | 1 (0.01%) | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | **8,712** | **3,311** | **1,806** | **1,427** | **1,424** | **3** |

Sweep-side breakdown (a separate dimension, not collapsed into close-position): `LOW_ONLY` 3,187
(36.6%), `HIGH_ONLY` 3,240 (37.2%), `BOTH` (double sweep) 2,284 (26.2%), `MISSING_OR_INCOMPLETE` 1.
8,712 signals come from 7,888 distinct candles -- 824 candles produced a credited trigger on BOTH
directions.

**MISSING_OR_INCOMPLETE is negligible (1 of 8,712)** -- the stop-and-document degenerate-contrast
condition from the protocol does not apply. **EXACT_BOUNDARY is rare (25 of 8,712, 0.3%)**, exactly
as expected on continuous FX prices -- reported on its own, never merged into INSIDE or OUTSIDE.

**A striking funnel-shape difference between groups, visible well before any outcome**: INSIDE
activations confirm Model-1 MORE often (47.8%) than OUTSIDE ones (31.3%), but OUTSIDE confirmed
signals survive Stage 6's RR floor MORE often (62.8% vs. 46.8%) and fill MORE often once a
candidate (88.3% vs. 67.1%) -- the two groups reach similar END-TO-END activation-to-filled rates
(INSIDE 15.0%, OUTSIDE 17.4%) through genuinely different intermediate shapes. This is reported as
a structural observation, not attributed to any single mechanism in this first comparison.

## C. Original closed-trade outcomes by group

**Pooled (3 pairs, closed trades only, open excluded):**

| Group | n | Mean R | Win rate |
|---|---|---|---|
| INSIDE | 530 | **+0.492** | **55.1%** |
| OUTSIDE | 892 | **-0.212** | **27.2%** |
| EXACT_BOUNDARY | 2 | -1.086 | 0.0% (n too small for any inference) |

**By instrument:**

| | EURUSD | USDCAD | AUDUSD |
|---|---|---|---|
| INSIDE mean R (n) | +0.445 (191) | +0.675 (174) | +0.354 (165) |
| OUTSIDE mean R (n) | -0.282 (300) | -0.227 (313) | -0.120 (279) |
| INSIDE win rate | 51.8% | 60.9% | 52.7% |
| OUTSIDE win rate | 25.7% | 26.8% | 29.4% |

**The INSIDE-vs-OUTSIDE direction is the same sign in all three instruments** -- not a single-pair
artifact.

**Uncertainty on the pooled INSIDE-minus-OUTSIDE mean-R difference** (block bootstrap, 2,000
resamples, clustered by `(symbol, NY trading date)` -- the same block-bootstrap discipline the
sibling lab has used since Phase 3, with a block defined so that two signals sharing a current H4
candle always share the same block):

**+0.704R, 95% CI [+0.530R, +0.867R]** -- comfortably excludes zero, and the point estimate is far
larger in magnitude than any association found across the sibling lab's own ten phases (the E1
model gap there was +5.38pp on a probability scale; this is +0.70R on a per-trade return scale --
not directly comparable units, but illustrating that this split separates a large fraction of this
population's own variance).

## D. Chart examples (selection rule stated in `docs/01-protocol.md`, before any outcome was inspected)

First EURUSD trigger chronologically (by `current_open_ts`) within each category:

| File | `stable_id` | `current_open_ts` (UTC) | Category |
|---|---|---|---|
| `figures/example_inside.png` | `EURUSD\|d3_c2\|9am\|2015-01-07T14:00:00\|bullish` | 2015-01-07 14:00 | INSIDE |
| `figures/example_outside.png` | `EURUSD\|d3_c2\|9am\|2015-01-02T14:00:00\|bullish` | 2015-01-02 14:00 | OUTSIDE |
| `figures/example_exact_boundary.png` | `EURUSD\|d3_c2\|9am\|2016-09-22T13:00:00\|bearish` | 2016-09-22 13:00 | EXACT_BOUNDARY |
| `figures/example_double_sweep_ambiguous.png` | `EURUSD\|d3_c2\|9am\|2015-01-29T14:00:00\|bearish` | 2015-01-29 14:00 | DOUBLE_SWEEP_AMBIGUOUS |

Each chart plots the reference candle's own 16 M15 bars (05:00-09:00 NY) followed by the current
candle's own 16 M15 bars (09:00-13:00 NY), with the reference range shaded. The vertical dotted
line at 09:00 NY marks the boundary between "observable progressively from here" (every bar after
it, as the original system itself observed them one M15 bar at a time) and the solid horizontal
line marking the 13:00 NY final close -- explicitly labeled "observable only at close," since that
value is the retrospective label this experiment adds, never information the original system had
while confirming or placing the order.

## E. Timeline and causal availability -- the decisive finding for Section 3's own question

**For 9AM, an order is NEVER placed strictly after the current candle's own 13:00 NY close becomes
available, under the window design Phase 7-10 already verified**: of the 1,427 executed 9AM
trades, `order_placed_ts` is before 13:00 for 1,308 (91.7%), exactly AT 13:00 for 119 (8.3%, the
boundary M15 bar), and after 13:00 for **zero**. This follows directly from the 9AM confirmation
window's own design (Phase 7): its search window is 09:00-13:00 NY -- the SAME span as the current
H4 candle -- so the window's own deadline can never extend past the candle's own close.

**Consequence**: the "close back inside the range" classification this experiment adds is, for
every single 9AM trade, either contemporaneous with (119 trades) or already AFTER (1,308 trades)
the moment the original order was placed. **It was never, for any of the 1,427 executed trades,
genuinely available information BEFORE the order-placement decision.** This is the central reason
this comparison stays retrospective, exactly as the brief frames it -- a prospective variant is not
simply "add this filter" but requires a DIFFERENT confirmation-window design entirely (one whose
own deadline extends past 13:00), which is explicitly out of this experiment's scope.

Separately, by EXIT timing (not order placement): of the 1,427 executed trades, the trade's own
exit was already known before 13:00 for 285 (20.0%), after 13:00 for 1,101 (77.2%), exactly tied
(`ORDERING_INDETERMINATE`) for 38 (2.7%), and still open at the data's end for 3. This is a
separate fact from the order-placement finding above -- a trade can be ENTERED before 13:00 (as
every one of them is) and still EXIT after 13:00, which is what happens for the large majority.

## F. Conclusion

**Question 1 -- how often do D3/C2 9AM signals satisfy this particular Raza rule?** Among 8,712
baseline activations, 40.6% ultimately close back inside the reference range (`INSIDE`), 59.1%
close through it (`OUTSIDE`), 0.3% close exactly on a boundary, and a negligible 0.01% have
incomplete data. Raza's own direction rule is inapplicable (both sides swept) for 26.2% of all
activations -- retained as its own category, never forced into a direction.

**Question 2 -- what does the retrospective grouping tell us about the original trades?** Within
the SAME original entry/stop/target/cost/RR rules, the 530 closed trades whose current candle
ultimately closed back inside the reference range show a markedly better original outcome
(+0.492 mean R, 55.1% win rate) than the 892 closed trades whose candle closed through it (-0.212
mean R, 27.2% win rate) -- a +0.704R difference (95% CI [+0.530R, +0.867R]), consistent in sign
across all three instruments. This is a genuine, well-supported RETROSPECTIVE association within
the executed population -- it does NOT establish that this information could have improved any of
these specific trades' own results, because (Section E) the order for every one of them was
already placed at or before the exact instant this label becomes knowable.

**What would justify testing a prospective, post-close variant**: (1) a REDESIGNED confirmation
window whose own deadline extends meaningfully past 13:00 NY, so the close-back-inside label
genuinely precedes some new order-placement instant -- not merely a filter bolted onto the
EXISTING window, which structurally cannot use it prospectively; (2) a pre-registered, OWN set of
entry/fill rules for that redesigned window (RR floor, Stop Loss/Take Profit placement, cost
model) -- explicitly left for a future review per the brief, never assumed to be the same
unchanged rules evaluated here; (3) a genuinely independent temporal holdout, since 2015-2026
remains previously examined by the sibling lab's own phases; (4) given the magnitude found here
(+0.70R, a much larger split than anything the sibling lab's ten phases found), this association
clears a materiality bar worth that investment -- but materiality alone does not establish that a
redesigned, prospective version would reproduce it, since the REASON today's trades split this way
may be inseparable from information that only existed because the order was ALREADY placed.

## Explicit scope boundary (restated)

Daily bias, FVG exceptions, rejection-block exits, RR tuning, and the 1AM model are all outside
this first comparison, per the brief. No rule was changed; no new backtest ran; every number above
comes from the ORIGINAL executed-trade ledger and the ORIGINAL D3/C2 detection pipeline, both
read-only.
