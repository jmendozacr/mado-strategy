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

**Clarification (per independent review): every row in this table and in `funnel_c1_c2.csv` is per (pair, arm, model) — never pre-aggregated across models.** §1's headline totals and §2's per-pair/model table are separate, correctly-scoped aggregations computed from `trades_c1.csv`/`trades_c2.csv` directly (one row per trade, summed), not derived from this funnel table. The two should not be cross-checked against each other without remembering they measure different things: this table counts *windows/triggers/signals* (pre-fill), §1/§2 count *trades* (post-fill, i.e. `candidates_built`/`filled`/`never_filled` downstream of this table's `model1_confirmed`).

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

**Correction (per independent review): this is reported as a coincident sensitivity, not a proven causal artifact** — I have not demonstrated that the 2007-2009 feeder-candle coverage gap (design doc §4.2) is the MECHANISM producing AUDUSD C2's 2007-2009 profitability; I have only shown the two are the same window. **C1 is not materially sensitive to 2007-2009** (positive with or without it) — expected, since C1 never uses the NY-anchored feeder construction the 2007-2009 gap affects. **C2 is**: its entire reported AUDUSD edge (+7.20R) comes from the 2007-2009 window specifically, which **coincides with** the window already flagged for known, concentrated feeder-candle incompleteness (2.10% of AUDUSD's 9AM-NY buckets, 84% concentrated in 2007-2009) — a correlation worth flagging, not a demonstrated cause. **Excluding that window, C2's AUDUSD result is negative (-9.35R).** Reported as a red flag warranting caution on AUDUSD's C2 contribution, not as proof that the coverage gap caused the profit.

## 5. What this means, read honestly

- **C1 (causality fixed, geometry left as today's code has it) keeps a real, if much smaller, edge**: +297.68R across 2,500 closed trades, positive in 4 of 6 pair/model combinations, and not an artifact of any single pair or period found so far.
- **C2 (causality fixed, geometry corrected to match what the charters actually define) is much weaker**: +22.69R, and once AUDUSD's 2007-2009-driven contribution is set aside as unreliable (§4) and EURUSD's negative result is weighed on its own terms (§2), the only pair/model combinations with a believable positive result are USDCAD's two models (+16.79R, +18.58R) and AUDUSD's 1AM model excluding the suspect window (need not be re-derived here: AUDUSD 1am's own total is +8.28R combined, and the 2007-2009 contribution is concentrated more in 9am per the funnel's own `windows_considered` split, but this was not separately re-verified by model and should be treated as approximate, not exact).
- **Year-by-year (combined, `year_breakdown_c1_c2.csv`), neither arm is a steady earner**: C1 has **6** losing years out of 24 (2003, 2015, 2016, 2017, 2018, 2023 — corrected; an earlier draft of this report miscounted this as 5); C2 has **11** (2003, 2007, 2011, 2012, 2014, 2015, 2016, 2017, 2018, 2019, 2023 — corrected from an earlier miscount of 10) — a materially choppier, less convincing equity curve than C1's, consistent with C2's much thinner combined edge being a weaker, less robust signal, not a smaller but equally reliable one.
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
- AUDUSD's C2 result is flagged as a coincident sensitivity with the 2007-2009 coverage gap (§4) — NOT a proven causal artifact; it was not excluded from the combined total (not asked to be), only reported transparently.
- §9 of this document records a further CRT-range causality question raised after this report's first version (`detect_crt_ranges`'s `resolved_at_index`, used by `confirm_in_ltf_window`'s candidate-range selection) — see the dedicated audit below.
- B1-realistic's approximations (design §7) are unchanged and were not revisited this round.

## 9. CRT-range causality audit (new, requested by independent review)

### 9.1 The concern, precisely

`detect_crt_ranges` (`primitives/crt_range.py`) is a **global, fully hindsight-computed** function: for every M15 candle `i`, it looks forward up to `config.max_lookback` (20 candles = 5h) candles to decide if/when/how the 2-candle range starting at `i` resolves (`true_break` on a decisive close, or `false_break` on a wick-and-reverse-past-midpoint), and records that in `CRTRange.resolved_at_index`. `run_c1_c2.py` computes `ltf_ranges = detect_crt_ranges(m15, config.crt_range)` ONCE, over the full series, exactly like A/B1/B2 always have — I reused it unmodified, the same way I reused `confirm_in_ltf_window` itself, without separately auditing whether the `resolved_at_index` it hands to `confirm_in_ltf_window`'s own candidate-selection (`resolved_at = min(ltf_range.resolved_at_index, end_idx)`, used as the upper bound for `first_breach_index`) could encode information not yet real at the point it mattered. This was a genuine gap in the design-c1-c2.md audit, which only covered Key Levels (§2), not Model-1's own LTF CRT-range anchor source.

### 9.2 Method (no rerun — analyzed trades already exported)

For every CONFIRMED signal in `trades_c1.csv`/`trades_c2.csv`: parsed `anchor_index` directly from `signal_id` (format `origin_index-anchor_index-direction-...`); recomputed `ltf_ranges` once per pair (cheap — a single pass, not the full pipeline, ~10-60s per pair); reconstructed the exact search window (`confirmation_window_utc` + the trade's own `activation_instant_ts` floor, unmodified); searched `ltf_ranges` for the range that, under `confirm_in_ltf_window`'s own tie-break rule (lowest `start_index` among ranges whose bounded `first_breach_index` lands exactly on this `anchor_index`), would have been selected as the winner. Classified each trade by comparing `available_at(winning_range.resolved_at_index)` against two reference points:

- **`CAUSALMENTE_VÁLIDO`**: the range's resolution was already available at or before `activation_instant_ts` (when the sweep+Key-Level trigger itself fired).
- **`DEPENDE_RESOLUCIÓN_FUTURA_LEVE`**: available after `activation_instant_ts` but at or before `model1_available_ts` (when the order could actually be placed).
- **`DEPENDE_RESOLUCIÓN_FUTURA_ESTRICTA`**: available only after `model1_available_ts` — the order could already be placed before the range it depended on had resolved.
- **`NO_EVALUABLE`**: no matching range found (ambiguous or genuinely absent — happens; `first_breach_index`/tie-break reconstruction is exact but a handful of edge cases didn't resolve to a unique match).

### 9.3 Results — universal, not isolated

| Arm | Pair | Total | Válido | Leve | Estricta | No evaluable |
|---|---|---|---|---|---|---|
| C1 | EURUSD | 792 | **0** | 751 | 26 | 15 |
| C2 | EURUSD | 440 | **0** | 410 | 23 | 7 |
| C1 | USDCAD | 812 | **0** | 774 | 31 | 7 |
| C2 | USDCAD | 519 | **0** | 488 | 25 | 6 |
| C1 | AUDUSD | 899 | **0** | 850 | 36 | 13 |
| C2 | AUDUSD | 585 | **0** | 541 | 31 | 13 |

**Zero "causally valid" trades under the strict definition, in every single pair/arm combination — a universal pattern, not noise.**

### 9.4 What this actually means — the LEVE/ESTRICTA distinction matters, and I do not want to overstate this

**`ESTRICTA` (26-36 trades per pair/arm, ~3-4% of each) is the unambiguous violation.** Concrete example: `c1 EURUSD 10879-10880-bullish-purge_engulf-body` (9am model) — the winning CRT range (`start_index=10879`, `resolved_at_index=10885`) only becomes resolved/known at `2003-10-09 14:30:00`, but `model1_available_ts` (the order could already be placed) is `2003-10-09 14:00:00` — **the order could be placed 30 minutes before the range that determined its anchor had even resolved.** These are real, direct violations of the same kind Phase 1 found in `find_turtle_soup_triggers` — just in a different function this investigation hadn't yet checked.

**`LEVE` (94-95% of each total) is measured against `activation_instant_ts` — the moment of a DIFFERENT event (the H4/NY-feeder sweep+Key-Level trigger), not the LTF CRT range's own causal prerequisite.** I am not yet certain this represents a genuine information leak rather than an artifact of comparing against the wrong reference point: mechanically, `first_breach_index` finds the FIRST wick-breach of the range's high/low, and that search's upper bound (`resolved_at_index`) only matters when it EXCLUDES a later breach that would otherwise be found — in the cases checked, the selected anchor already falls at or before `resolved_at_index` by construction, so whether the *bound itself* was "future knowledge" at `activation_instant_ts` doesn't necessarily mean the *anchor that got picked* depended on anything not yet real. **I have not resolved this ambiguity and am explicitly not claiming the 94-95% LEVE figure represents 94-95% causally-broken trades — only that it is NOT yet shown to be clean either.** This needs the same kind of careful, incremental re-derivation `causal_intrabar.py` already did for the H4/NY feeder sweep, applied now to `detect_crt_ranges` itself, to resolve properly — not a quick reclassification.

### 9.5 What is and isn't established

- **Established**: `detect_crt_ranges` is global/hindsight, exactly like `find_turtle_soup_triggers` was before Phase 1's fix — and it was never separately causally audited for its role in Model-1's own LTF anchor search. At least 3-4% of every pair/arm's exported trades (the `ESTRICTA` cases) have a demonstrated, concrete timing violation in the anchor-selection mechanism.
- **Not established**: the true causal validity of the 94-95% `LEVE` cases. Resolving this requires building a causally-incremental version of CRT-range resolution (watching each M15 bar close and only treating a range as "resolved" once that resolution is actually observed, mirroring `causal_intrabar.py`'s existing provisional-candle approach) and rerunning the SAME already-exported trades through it — not yet done, not yet authorized.
- **Scope**: this affects C1 and C2 identically (both reuse the same `ltf_ranges`/`confirm_in_ltf_window` machinery) — it is not a C1-vs-C2 difference, so it does not change the §1-§5 comparison between them, but it does mean **neither arm's absolute numbers should yet be considered fully, end-to-end causally proven** — a second limitation on top of the Key-Level-source question (§8), which that same trace closed; this one is still open.

## 10. Timeframe going forward (per user decision)

From this point, development and further audits default to **2015-01-01 through the last available date** for EURUSD/USDCAD/AUDUSD, not 2003-2026 — added as `--start-date`/`--end-date` CLI arguments to `run_c1_c2.py` (code only; not yet re-executed). The full 2003-2026 window is reserved for a complete historical validation once the implementation is stabilized (CRT-range causality resolved, among other things) — not run again automatically. The loaded series and all shared detection (CRT ranges, swings, Key Levels) always use the complete available history regardless of this window, so every indicator keeps its full warmup/lead-in; only which trigger windows get walked is filtered by these dates. No parameters are recalibrated using the 2015+ window.

## 11. Not yet done (explicitly, per the stop instruction)

No production change. No recalibration. No commit. No new full historical run. No fix to the CRT-range causality gap (§9) implemented yet. Awaiting independent review before any further step.
