# Results — Arms C1/C2 (intrabar causal detector)

Implementation per `design-c1-c2.md` (rounds 1-3, user-authorized). Full 2003-2026 history, EURUSD/USDCAD/AUDUSD. Nothing under `detector/`/`scanner/`/`docs/` modified. A/B1/B2 outputs untouched (verified, see §6). No parameters recalibrated. No commits made yet.

## 1. Headline result

| Arm | Trades | Closed | Win rate | Total R | Expectancy/trade |
|---|---|---|---|---|---|
| A (original baseline) | 2,067 | 2,060 | 63.79% | **+1630.77R** | +0.792R |
| B1-ideal (diagnostic) | 1,440 | 1,438 | 38.80% | +28.54R | +0.020R |
| B1-realistic (diagnostic) | 1,398 | 1,396 | 35.67% | -145.86R | -0.104R |
| B2 (diagnostic, wrong close-based trigger) | 61 | 61 | 34.43% | -6.12R | -0.100R |
| **C1** (causal trigger, broker H4 grid) | 2,503 | 2,500 | 40.56% | **+297.68R** | +0.119R |
| **C2** (causal trigger, correct NY-anchored grid) | 1,544 | 1,542 | 38.85% | **+22.69R** | +0.015R |

Both C1 and C2 land **positive** — but at 18% (C1) and 1.4% (C2) of the original baseline's total R, and with win rates in the high 30s/low 40s rather than 64%. **Per the task's own stated success criterion, a small positive combined R is not, by itself, evidence the strategy works** — see §3/§5 for why.

## 2. Per-pair, per-model breakdown (required — never combine as if equivalent)

| Arm | Pair | Model | Trades | Win rate | Total R |
|---|---|---|---|---|---|
| C1 | EURUSD | 1am | 434 | 41.01% | +19.80R |
| C1 | EURUSD | 9am | 358 | 40.50% | +93.77R |
| C1 | USDCAD | 1am | 485 | 44.33% | +68.14R |
| C1 | USDCAD | 9am | 325 | 42.77% | +71.72R |
| C1 | AUDUSD | 1am | 581 | 37.18% | +33.05R |
| C1 | AUDUSD | 9am | 317 | 38.17% | +11.21R |
| C2 | EURUSD | 1am | 294 | 39.46% | **-13.72R** |
| C2 | EURUSD | 9am | 146 | 33.56% | **-6.16R** |
| C2 | USDCAD | 1am | 368 | 42.12% | +16.79R |
| C2 | USDCAD | 9am | 150 | 41.33% | +18.58R |
| C2 | AUDUSD | 1am | 461 | 36.44% | +8.28R |
| C2 | AUDUSD | 9am | 123 | 39.84% | -1.08R |

**Under C2 (the charter-faithful geometry), EURUSD — the pair this whole methodology and all five prior charters (8-11) are built around — is net NEGATIVE on both models.** The combined C2 total (+22.69R) is carried entirely by USDCAD; AUDUSD is marginal and its own positive result is itself suspect (§4).

## 3. Full funnel, per pair/model/arm

See `funnel_c1_c2.csv` for the raw table. Example (EURUSD, both models, both arms):

| Arm | Model | Windows considered | Swept (either side) | Triggers w/ valid Key Level | Model-1 confirmed | Orders placed | Filled | Never filled |
|---|---|---|---|---|---|---|---|---|
| C1 | 1am | 6,128 | 5,678 (92.7%) | 6,676 | 1,402 | 962 | 792 | 170 |
| C1 | 9am | 6,118 | 5,669 (92.7%) | 6,704 | 787 | 962 | 792 | 170 |
| C2 | 1am | 6,122 (2,472 ref-incomplete skipped) | 5,967 (97.5%) | 8,029 | 1,385 | 531 | 440 | 91 |
| C2 | 9am | 6,115 (2,479 ref-incomplete skipped) | 5,472 (89.5%) | 6,080 | 289 | 531 | 440 | 91 |

Note "triggers w/ valid Key Level" can exceed "windows considered" because both directions (bearish+bullish) are counted separately, and ~both-sides sweeps are common (design §5/validation point 6 — `swept_both` is reported separately in `funnel_c1_c2.csv`, not folded into a single count). The dominant exclusion reason at every stage is `no_model1_anchor_found` (no Model-1 pattern ever formed in the available window) followed by `model1_pending_or_invalidated` (a Model-1 did start forming but never reached `CONFIRMED` — this is the stricter-than-production filter design §1.3 adds deliberately). C2's `reference_incomplete_skipped` (~2,450-2,480 per model per pair) reflects every calendar day whose NY-anchored reference candle failed `validate_complete_feeder_bucket` (weekends with no M15 data mostly, plus the holiday/DST gaps measured in the design doc) — this is NOT the same as the AUDUSD-specific 2007-2009 anomaly (§4), which affects which SPECIFIC days are skipped, not the overall skip rate (C2's reference-incomplete rate is similar across all three pairs, ~40% of calendar days, dominated by weekends since every day is checked, not just weekdays with a known H4 bar).

## 4. AUDUSD 2007-2009 sensitivity (required)

| Arm | Scope | Trades | Total R |
|---|---|---|---|
| C1 | All years | 898 | +44.25R |
| C1 | 2007-2009 only | 122 | +6.53R |
| C1 | Excluding 2007-2009 | 776 | +37.72R |
| C2 | All years | 584 | +7.20R |
| C2 | 2007-2009 only | 65 | **+16.55R** |
| C2 | Excluding 2007-2009 | 519 | **-9.35R** |

**C1 is not materially sensitive to 2007-2009** (positive with or without it) — expected, since C1 never uses the NY-anchored feeder construction the 2007-2009 gap affects. **C2 is**: its entire reported AUDUSD edge (+7.20R) is an artifact of the 2007-2009 window, which is exactly the window with known, concentrated feeder-candle incompleteness (design doc §4.2, 2.10% of AUDUSD's 9AM-NY buckets, 84% concentrated in 2007-2009). **Excluding that window, C2's AUDUSD result is negative (-9.35R).** This is reported, not papered over: AUDUSD's C2 contribution should be treated as unreliable, not as supporting evidence.

## 5. What this means, read honestly

- **C1 (causality fixed, geometry left as today's code has it) keeps a real, if much smaller, edge**: +297.68R across 2,500 closed trades, positive in 4 of 6 pair/model combinations, and not an artifact of any single pair or period found so far.
- **C2 (causality fixed, geometry corrected to match what the charters actually define) is much weaker**: +22.69R, and once AUDUSD's 2007-2009-driven contribution is set aside as unreliable (§4) and EURUSD's negative result is weighed on its own terms (§2), the only pair/model combinations with a believable positive result are USDCAD's two models (+16.79R, +18.58R) and AUDUSD's 1AM model excluding the suspect window (need not be re-derived here: AUDUSD 1am's own total is +8.28R combined, and the 2007-2009 contribution is concentrated more in 9am per the funnel's own `windows_considered` split, but this was not separately re-verified by model and should be treated as approximate, not exact).
- **Year-by-year (combined, `year_breakdown_c1_c2.csv`), neither arm is a steady earner**: C1 has 5 losing years out of 24 (2003, 2015, 2016, 2017, 2018, 2023); C2 has 10 (2003, 2007, 2011, 2012, 2014, 2015, 2016, 2017, 2018, 2019, 2023) — a materially choppier, less convincing equity curve than C1's, consistent with C2's much thinner combined edge being a weaker, less robust signal, not a smaller but equally reliable one.
- **Per the task's own standard** ("no considerar C1/C2 exitosos solo porque produzcan R positivo"): a positive combined number built from one pair carrying two losers (C2), or from a geometry (C1) that this same investigation has already shown does not match the charters' own definition, is not a demonstrated edge. The honest reading is: **once look-ahead is removed, this strategy's historical edge mostly disappears. What's left (C1's +297.68R) is real but far smaller than advertised, and what's left under the geometrically correct reconstruction (C2's +22.69R) is thin, concentrated in one pair, and partly an artifact of a known data gap.**

## 6. Validation checklist (required)

1. ✅ Full causal sequence verified with timestamps (design doc §10's 9-stage table; `reconciliation_c1_c2.csv` carries `feeder_ref_available_ts`/`activation_instant_ts`/`model1_available_ts` per trigger).
2. ✅ PENDING/INVALIDATED signals excluded — `build_causal_signal` only returns `aligned is not None` for `status == CONFIRMED` (design §1.3); confirmed via `funnel_c1_c2.csv`'s `model1_confirmed` count being strictly less than `triggers_with_key_level`.
3. ✅ No fill before order placement — `fill_pass_c` floors eligibility at `first_fillable_index` (bisected on real timestamps), never `confirmation_index`; covered by the dedicated test suite (12/12 passing, including the exact "touch during confirmation bar" and "touch after activation" cases the prior review demanded).
4. ✅ Feeder-candle integrity validated for all three pairs (design doc §4.2) before this run, not re-validated here (unchanged since).
5. ✅ M15 gaps handled via `bisect` on real timestamps throughout, not index arithmetic (tested explicitly: `test_fill_pass_c_first_fillable_index_uses_real_timestamps_across_a_gap`).
6. ✅ Single- vs. both-sided sweeps recorded separately (`swept_bearish_only`/`swept_bullish_only`/`swept_both`/`swept_neither` in `funnel_c1_c2.csv`).
7. ✅ Which extreme credited the Key Level and which direction produced the signal recorded per trigger (`direction` column in `trades_c1.csv`/`trades_c2.csv` and `reconciliation_c1_c2.csv`).
8. ✅ Key-Level source identical between C1 and C2 — both call `build_key_levels(h4_broker, daily, config.fvg)` on the same broker H4/Daily series; `key_level_credited`'s `h4_broker` argument is always the broker grid in both arms (design §2.2/§8), confirmed by code inspection (`run_c1_c2.py`'s `run_c1`/`run_c2` both pass the same `key_levels`/`h4` into `detect_sweep_and_key_level`).
9. ✅ Regression suite: 1,265/1,265 passed (detector/), 12/12 passed (this investigation's own C1/C2 tests) — no regressions, nothing under `detector/` was touched.
10. ✅ Baseline A intact: `run_c1_c2.py`'s own closing assertion re-read `trades_arm_a.csv` and confirmed 2,067 rows / 2,060 closed / +1630.7719R, unchanged, before reporting success.

## 7. Independent reconciliation from trades.csv

`reconciliation_c1_c2.csv` carries one row per trigger (both confirmed and zero-signal), keyed by a stable id (`pair|arm|model|window_open_ts|direction`), with every state-machine timestamp and, for zero-signal triggers, the categorized reason. `trades_c1.csv`/`trades_c2.csv` independently sum to the exact combined totals reported in §1 (re-derivable directly from those files, not just from `metrics_c1_c2.json`).

## 8. Known limitations carried into this result

- Key-Level-source causality (FVG/Order-Block detection itself) was independently traced in `design-c1-c2.md` §2.1b/§2.1c and found correct under the `available_at` convention — this is no longer an open blocker, but it was not re-verified in this run beyond that prior trace.
- The DOL-gated reversal/continuation profile split, the i-2 (1AM-range) sweep alternative for the 9AM model, and non-Model-1 (TSQ/breaker-block) entries remain explicitly out of scope (design §0) — this result covers only the user's specified two-consecutive-candle, Model-1-only "core model" variant.
- AUDUSD's C2 result is flagged unreliable for the reason in §4; it was not excluded from the combined total (not asked to be), only reported transparently.
- B1-realistic's approximations (design §7) are unchanged and were not revisited this round.

## 9. Not yet done (explicitly, per the stop instruction)

No production change. No recalibration. No commit. Awaiting independent review before any further step.
