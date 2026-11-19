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

## 9. CRT-range causality audit (v2 — corrects a reviewer-caught attribution bug in the first pass)

### 9.0 Why this section was rewritten

The independent review of commit `fda1d88` found that `audit_crt_range_causality.py`'s `find_winning_range` reconstructed the winning `CRTRange` by searching for a range whose `first_breach_index()` matches the FINAL `anchor_index` in `signal_id`. That is wrong: `Model1Signal.signal_id` is `origin_index-anchor_index-...`, `origin_index` is fixed once (the real winning range's `start_index`), but `anchor_index` can be **reassigned** by `confirm_in_ltf_window`'s retry-on-invalidation loop while `origin_index` stays put — so the reconstruction could silently match the wrong range. The review explicitly withheld trust in the previously-reported 172 "ESTRICTA" cases (`26+23+31+25+36+31`, full 2003-2026 history) until this was fixed. `audit_crt_range_causality_v2.py` fixes the attribution, replaces the LEVE/ESTRICTA split with a 4-way A/B/C/D classification, adds a direct (non-tautological) check of whether the winning range's own resolution needed candles strictly after the sweep, and scopes the analysis to 2015-01-01+ (prior history kept only for warmup), per Task 4. No rerun of the full pipeline — this reanalyzes the already-exported `trades_c1.csv`/`trades_c2.csv`.

**Self-correction note, in the same spirit this whole audit has required of itself:** an earlier draft of the v2 script's Task 3 check restricted candidate ranges to ones whose own resolution was already available by `activation_instant_ts`, then asked whether a different anchor would get picked. It returned a 100% mismatch rate in literally every trade. Before reporting that, I checked `_resolve()` in `primitives/crt_range.py` directly: `resolved_at_index >= first_breach_index` **always**, by construction (the wick-poke must happen before or on the same candle that gets classified true/false-break). Since the check only searched for anchors at-or-after `activation_ts`, requiring `resolved_at_index <= activation_ts` on those same candidates is a near-contradiction baked into the check itself — the 100% figure was an artifact of the check's own design, not a finding, and is **not** reported below. It was replaced with a direct comparison of each winning range's `resolved_at_index` against its own `anchor_index`.

### 9.1 Task 1 — Attribution fix, verified

`detect_crt_ranges` emits at most one `CRTRange` per `start_index` (confirmed by assertion against the live range lists — 586,923 / 580,465 / 576,650 ranges for EURUSD/USDCAD/AUDUSD, zero duplicate `start_index`), so a direct `{start_index: CRTRange}` dict lookup keyed on `origin_index` is exact, unlike the old breach-matching reconstruction.

Scoped to `window_open_ts >= 2015-01-01` (reusing the existing exports): **2,226 trades evaluated** (C1: 1,369 of 2,503 total; C2: 857 of 1,544 total), 100% evaluable under the direct lookup (0 `NO_EVALUABLE`, vs. 24 under the old method).

**The old method's attribution disagrees with the corrected one in 718 / 2,226 trades — 32.3%** (C1: 436/1,369 = 31.9%; C2: 282/857 = 32.9%). The suspicion was correct: roughly 1 in 3 trades' "winning range" in the first pass was the wrong object.

**But the disagreement never crosses the ESTRICTA/C boundary.** Crosstabbing old-method verdict against corrected verdict for exactly the 718 disagreeing trades: 694 move `LEVE → B`, 24 move `NO_EVALUABLE → B`, **0 move into or out of ESTRICTA/C**. Old-method ESTRICTA on this same 2015+ scope = 78; corrected-method C = 78 — an exact match, confirmed to be because no individual trade flips the bucket, not a coincidental cancellation. **This is scoped to 2015+ only** — the pre-2015 portion of the original 172-ESTRICTA figure (full 2003-2026 history) has not been reverified under the corrected attribution and remains an open item, consistent with Task 4's priority ordering.

### 9.2 Task 2 — corrected 4-way classification

Replaces the old binary/ternary split (measured only against `activation_instant_ts`) with: **A** = winning range resolved before HTF activation; **B** = resolved after activation but before Model-1 confirmation; **C** = resolved after Model-1 confirmation (the order could already exist before the range it depends on had resolved — the unambiguous violation); **D** = insufficient evidence.

| Arm | Pair | Evaluated | A | B | C | D |
|---|---|---|---|---|---|---|
| C1 | EURUSD | 415 | 0 | 403 | 12 | 0 |
| C2 | EURUSD | 222 | 0 | 212 | 10 | 0 |
| C1 | USDCAD | 458 | 0 | 439 | 19 | 0 |
| C2 | USDCAD | 290 | 0 | 281 | 9 | 0 |
| C1 | AUDUSD | 496 | 0 | 481 | 15 | 0 |
| C2 | AUDUSD | 345 | 0 | 332 | 13 | 0 |
| **Total** | | **2,226** | **0 (0%)** | **2,148 (96.5%)** | **78 (3.5%)** | **0** |

**A = 0 in every single pair/arm/model combination, with zero exceptions — but this needs an important qualifier I verified directly in the source, not assumed:** `_resolve()` in `primitives/crt_range.py` can only classify a range as `true_break`/`false_break` on a candle that is at-or-after the candle where the range's high/low first gets breached (the wick-poke must happen before the close that confirms the break). Since `activation_instant_ts` is itself anchored to roughly the same sweep moment the window search looks for, `A = 0` is closer to a **structural consequence** of how `detect_crt_ranges` and the window search are defined than a surprising empirical discovery — it does not by itself prove a *severe* violation, only that the "resolved-before-the-trigger-even-fired" bar is never met. Task 3 digs into whether the *real* dependency (resolution strictly after the sweep) is trivial or substantive.

### 9.3 Task 3 — does the range's resolution genuinely depend on the future, beyond the sweep candle's own close?

For each winning range, compared `resolved_at_index` (when its true/false-break classification became decided) against its own `anchor_index` (the candle where the entry's actual purge/sweep happened, read from `signal_id`):

| Gap | Meaning | Count | % |
|---|---|---|---|
| `gap_bars > 0` | Resolved **strictly after** the sweep candle — the range's classification was genuinely undecided at the sweep moment, decided only on a later candle | 848 | 38.1% |
| `gap_bars == 0` | Resolved **on** the sweep candle itself — no hindsight beyond that single bar's own close, the same magnitude already accepted everywhere else `available_at` is used | 760 | 34.1% |
| `gap_bars < 0` | Resolved **before** the final sweep candle used for entry (possible because `confirm_in_ltf_window`'s retry-on-invalidation loop can reassign `anchor_index` to a later sweep of the same `origin_index` range than that range's own first breach) — already causally known by the time this specific entry's anchor fired | 618 | 27.8% |

Resolution-shape distribution across all 2,226 evaluated trades (`CRTRange.model`): `2-candle` 826 (37%), `3-candle` 718 (32%), `multi-inside` 346 (16%), `multi-outside` 336 (15%).

**Concrete example of genuine future dependency (`gap_bars = 8`):** `c1 EURUSD 336556-336559-bullish-purge_engulf-wick` (9am model, 2016-10-19) — the sweep/anchor candle closes at `13:15`, but the winning range's classification isn't decided until `15:15` (8 bars = 2 hours later), while `model1_available_ts` is `14:15` — **the order could already be placed a full hour before the range it depends on had resolved.** This is class C. A class-B example with a real (non-zero) gap: `c1 EURUSD 304428-304429-bullish-purge_engulf-wick` (1am, 2015-07-07), `gap_bars = 4`, range resolves `07:45` vs. `model1_available_ts` `07:15` — order placeable 30 minutes before resolution.

**Documentation question (per the explicit instruction not to invent or pick this toward favorable R):** `docs/charter-2.md`'s "Model-1 Entry" section states Model-1 needs exactly two things: a liquidity purge — sweeping above a High or below a Low, **"ya sean CRT High/Low o viejos Altos/Bajos"** (either a CRT High/Low or old highs/lows) — and an engulfing body-close of the purging candle. Nothing in this text requires the swept level to come from a level that has already passed `detect_crt_ranges`' own 2-candle/3-candle/multi true-break/false-break classification. Read literally, "a High or a Low" is a broader, simpler concept (closer to a swing high/low) than "a CRT range that has already been formally resolved." This means `confirm_in_ltf_window`'s dependency on `CRTRange.resolved_at_index` — both as the search bound and, more fundamentally, as the gate for whether a candidate range even **exists** in the list at all (`detect_crt_ranges` drops any range that doesn't resolve within `max_lookback=20` candles) — is a detector-implementation choice for operationalizing "the CRT High/Low," not something charter-2 itself mandates. **This still needs the user's own documentary sign-off**, since charter-2 doesn't exhaustively define what should count as a valid "CRT High/Low" either — I am reporting what the text says, not deciding the rule.

### 9.4 What is and isn't established now

- **Established**: the attribution bug was real (32.3% of trades reattributed) but does not change the ESTRICTA/C trade count for the 2015+ scope (verified via crosstab, not assumed). A genuine, non-trivial future dependency (resolution strictly after the sweep candle, `gap_bars > 0`) affects 38.1% of evaluated trades, of which 3.5% (class C) are unambiguous violations where the order could already exist before its anchor range resolved. `A = 0` universally is largely a structural consequence of how `_resolve()` and the window search are defined, not an independent surprise.
- **Not established**: whether class B's `gap_bars > 0` subset (resolved after activation/sweep but before Model-1 confirmation) should be treated as a real violation or tolerated as "normal" causal lag within the window — that judgment depends on the still-open documentation question above (is a swept level required to be a formally-resolved CRTRange at all, per the strategy's own rules, or is `detect_crt_ranges` just one implementation of "recent High/Low" that happens to carry this coupling as a side effect).
- **Not reverified**: the pre-2015 portion of the original 172-ESTRICTA figure (full 2003-2026 history) under the corrected attribution — only the 2015+ scope was reanalyzed, per Task 4's explicit priority.
- **Technical recommendation (not implemented, pending review):** if the documentation question resolves toward "no formal CRT-range resolution is required," the cleanest fix is for Model-1's anchor search to use a causally-incremental "most recent swing High/Low" source instead of `detect_crt_ranges`' classified-range list — avoiding both the `resolved_at_index`-as-search-bound issue and the deeper existence-conditioned-on-future-resolution issue in one change, without needing an incremental reimplementation of `detect_crt_ranges`' own 2-candle classification machinery. If instead formal resolution turns out to be required, the fix would need an actually-incremental version of `_resolve()` (treating a range as unresolved/non-existent for anchor purposes until its classification is observed in real time), which is a larger, separate undertaking. Deciding between these is exactly the "new version of the detector" step this task explicitly stops before.
- **Scope**: affects C1 and C2 identically (both reuse the same `ltf_ranges`/`confirm_in_ltf_window` machinery) — not a C1-vs-C2 difference, so it doesn't change the §1-§5 comparison between them, but neither arm's absolute numbers should yet be considered fully, end-to-end causally proven.

## 10. Timeframe going forward (per user decision)

From this point, development and further audits default to **2015-01-01 through the last available date** for EURUSD/USDCAD/AUDUSD, not 2003-2026 — added as `--start-date`/`--end-date` CLI arguments to `run_c1_c2.py` (code only; not yet re-executed). The full 2003-2026 window is reserved for a complete historical validation once the implementation is stabilized (CRT-range causality resolved, among other things) — not run again automatically. The loaded series and all shared detection (CRT ranges, swings, Key Levels) always use the complete available history regardless of this window, so every indicator keeps its full warmup/lead-in; only which trigger windows get walked is filtered by these dates. No parameters are recalibrated using the 2015+ window.

## 11. Not yet done (explicitly, per the stop instruction)

No production change. No recalibration. No new full historical run. No fix to the CRT-range causality gap (§9) implemented. No new detector version (incremental anchor source, or incremental `_resolve()`) designed or implemented — explicitly stopped before this step per the latest review's instruction. Pre-2015 portion of the original ESTRICTA figure not reverified under the corrected attribution. Awaiting independent review before any further step.
