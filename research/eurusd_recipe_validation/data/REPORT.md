# EURUSD recipe validation - aggregate statistics vs. rolling-window survival

GENERATED FILE. Produced by `uv run --project detector python -m research.eurusd_recipe_validation.compare` from the repository root. Do not hand-edit; re-run the command instead.

Read `README.md` next to this file first: it states which parameters below are VERIFIED historical facts and which are RECONSTRUCTIONS of parameters whose original values are lost. This is a REPRODUCTION of a comparison whose own data was never committed, not a replay of it.

## The question

Three quality-over-quantity filters were once tested against the unfiltered baseline recipe, and all three were rejected. The reason recorded at the time is the thing worth showing: on aggregate, whole-period statistics the filters looked GOOD, and on a rolling-window prop-firm survival simulation they looked WORSE. Fewer, higher-quality trades improve the average and concentrate the risk, and it is the concentration that fails an account.

Every fail_dd% below is measured over 1240-1251 overlapping 250-day windows (the exact count varies a little per variant) - one notional account started on every possible historical day, each run against a static Phase-1 cap of 10% from its own initial balance.

## What reproduced and what did not

- **Trade counts: reproduced.** All three surviving historical counts land within 0.7% to 5.9% of this rebuild, depending on the exit model. That is close enough to confirm the signal pipeline, the session, the two account-level gates and lever B's 25-pip threshold, and close enough to PIN lever A's lost R:R value at 2.5.
- **Aggregate-vs-windowed direction: reproduced, conditionally.** On the static-from-initial-balance basis with a pure natural-take-profit exit, the historical verdict holds where it matters: the baseline is the safest variant at 0.75% and 1.00% risk, and A+B is the most dangerous everywhere - A+B fails 15.9% of windows at 0.75% risk against the baseline's 4.3%, nearly four times as often. At 0.50% risk every variant is effectively safe (0.0-6.2%) and the baseline's 0.1% is one single window out of 1251, so the 0.50% row ranks noise. With the detector's current 50% partial-exit default the ordering weakens further: lever B overtakes the baseline at 0.75% risk. The exit model is load-bearing for the conclusion, so both are published below rather than one being chosen quietly.
- **The `peak_to_trough` basis inverts the ranking, and should not be read as a contradiction.** It measures giving back a run-up, so it structurally punishes whichever variant made the most money - the baseline, with the most trades and the largest total R, looks worst by it. A cap that is static from the account's INITIAL balance is simply not that measurement: an account that doubled and then halved never breached a static 10% floor. The basis is published for completeness because the surviving record's wording ('worst-case drawdown within any window') literally describes it, but `initial_balance_floor` is the basis that matches the rule the user confirmed.
- **Absolute fail_dd% levels: NOT reproduced.** This rebuild is 7 to 19 percentage points more optimistic than the historical figures at every point of comparison. No defensible combination of the reconstructed parameters closes that gap. The lost simulator's equity model was materially harsher than anything the surviving description specifies; see README.md's 'Known unreproduced figures'.
- **The Calmar contrast: NOT reproduced.** The historical record has lever B scoring BETTER than the baseline on Calmar (6.46 vs 4.35), which is precisely what made the windowed check decisive. Under the reconstructed Calmar definition the baseline scores better on both exit models. The 'aggregate flatters the filters' effect still shows up here, but in per-trade expectancy and win rate rather than in Calmar.
- **The daily 5% loss limit never binds.** Across every variant, risk level and window, zero windows breached it. The stop-after-two-losses rule caps a day's exposure near 2R, so the max-drawdown cap is the only constraint that ever decides an account here.

## Exit model: partial_fraction = 0.0 (pure natural take-profit, no partial leg - what the recipe record literally describes)

### The contrast in one line

The best per-trade expectancy among the filtered variants is `lever_a_plus_b` at +0.496 R per trade, against the baseline's +0.397 R - on that number alone the filter wins. At 0.75% risk it would have breached the static 10% cap in 15.9% of all 250-day windows against the baseline's 4.3%, or 3.7x as often, on 734 trades against 1582.

### Is the unfiltered baseline the safest variant?

| Drawdown basis | Risk | Baseline fail_dd | Best lever | Worst lever | Verdict |
| --- | --: | --: | --- | --- | --- |
| `initial_balance_floor` | 0.50% | 0.1% | `lever_c` 0.0% | `lever_a_plus_b` 6.2% | `lever_c` safer by 0.1 pp |
| `initial_balance_floor` | 0.75% | 4.3% | `lever_d_zone_reject` 2.6% | `lever_a_plus_b` 15.9% | `lever_d_zone_reject` safer by 1.7 pp |
| `initial_balance_floor` | 1.00% | 13.3% | `lever_d_zone_reject` 7.9% | `lever_a_plus_b` 22.3% | `lever_d_zone_reject` safer by 5.4 pp |
| `peak_to_trough` | 0.50% | 28.6% | `lever_c` 0.0% | `lever_a_plus_b` 58.8% | `lever_c` safer by 28.6 pp |
| `peak_to_trough` | 0.75% | 82.7% | `lever_b` 61.0% | `lever_c` 80.9% | `lever_b` safer by 21.8 pp |
| `peak_to_trough` | 1.00% | 100.0% | `lever_a_plus_b` 69.0% | `lever_d_zone_reject` 98.4% | `lever_a_plus_b` safer by 31.0 pp |

### Aggregate, whole-period statistics (the view that favoured the filters)

| Variant | Trades | Win rate | Total R | Avg R / trade | Max DD (R) | Calmar |
| --- | --: | --: | --: | --: | --: | --: |
| Baseline - the live, unfiltered recipe | 1582 | 32.8% | 628.3 | +0.397 | 31.3 | 4.89 |
| Lever A - R:R floor raised to 2.5 (RECONSTRUCTED value) | 1316 | 30.9% | 613.2 | +0.466 | 34.1 | 4.40 |
| Lever B - key-level zone width <= 25 pips | 923 | 33.9% | 401.7 | +0.435 | 31.0 | 3.18 |
| Lever C - NY-only session 07:00-11:00 (RECONSTRUCTED window) | 782 | 34.3% | 362.3 | +0.463 | 20.5 | 4.33 |
| Levers A+B combined | 734 | 31.2% | 363.8 | +0.496 | 29.5 | 3.03 |
| Lever D (candidate) - require genuine Key Level zone rejection, not just CRT-range close | 1057 | 34.4% | 504.0 | +0.477 | 33.6 | 3.66 |

### Rolling-window survival, Phase-1 cap 10% static, basis `initial_balance_floor` (the user-confirmed static rule)

| Variant | fail_dd @ 0.50% | fail_dd @ 0.75% | fail_dd @ 1.00% |
| --- | --: | --: | --: |
| Baseline - the live, unfiltered recipe | 0.1% | 4.3% | 13.3% |
| Lever A - R:R floor raised to 2.5 (RECONSTRUCTED value) | 2.1% | 10.1% | 19.3% |
| Lever B - key-level zone width <= 25 pips | 2.1% | 8.5% | 13.9% |
| Lever C - NY-only session 07:00-11:00 (RECONSTRUCTED window) | 0.0% | 7.0% | 14.2% |
| Levers A+B combined | 6.2% | 15.9% | 22.3% |
| Lever D (candidate) - require genuine Key Level zone rejection, not just CRT-range close | 0.0% | 2.6% | 7.9% |

### Rolling-window survival, Phase-1 cap 10% static, basis `peak_to_trough` (the memory record's literal phrasing)

| Variant | fail_dd @ 0.50% | fail_dd @ 0.75% | fail_dd @ 1.00% |
| --- | --: | --: | --: |
| Baseline - the live, unfiltered recipe | 28.6% | 82.7% | 100.0% |
| Lever A - R:R floor raised to 2.5 (RECONSTRUCTED value) | 35.2% | 78.0% | 93.9% |
| Lever B - key-level zone width <= 25 pips | 43.2% | 61.0% | 87.6% |
| Lever C - NY-only session 07:00-11:00 (RECONSTRUCTED window) | 0.0% | 80.9% | 91.7% |
| Levers A+B combined | 58.8% | 61.5% | 69.0% |
| Lever D (candidate) - require genuine Key Level zone rejection, not just CRT-range close | 9.4% | 73.2% | 98.4% |

### Cross-check against the surviving historical figures

| Historical figure (VERIFIED) | Value | This reproduction | Delta |
| --- | --- | --- | --- |
| `baseline` trade count | 1681 | 1582 | -99 (-5.9%) |
| `lever_b` trade count | 975 | 923 | -52 (-5.3%) |
| `lever_a_plus_b` trade count | 768 | 734 | -34 (-4.4%) |
| `baseline` Phase-1 fail_dd @ 0.50% risk | 10.2% | 0.1% | -10.1 pp |
| `lever_b` Phase-1 fail_dd @ 0.50% risk | 16.0% | 2.1% | -13.9 pp |
| `baseline` Phase-1 fail_dd @ 0.75% risk | 13.7% | 4.3% | -9.4 pp |
| `lever_b` Phase-1 fail_dd @ 0.75% risk | 19.6% | 8.5% | -11.1 pp |
| `lever_a_plus_b` Phase-1 fail_dd @ 0.75% risk | 23.2% | 15.9% | -7.3 pp |
| `baseline` Calmar ratio | 4.35 | 4.89 | +0.54 |
| `lever_b` Calmar ratio | 6.46 | 3.18 | -3.28 |

## Exit model: partial_fraction = 0.5 (the detector's current library default, REQ-68 - what simulate() produces today)

### The contrast in one line

The best per-trade expectancy among the filtered variants is `lever_a_plus_b` at +0.463 R per trade, against the baseline's +0.392 R - on that number alone the filter wins. At 0.75% risk it would have breached the static 10% cap in 10.0% of all 250-day windows against the baseline's 2.3%, or 4.3x as often, on 755 trades against 1642.

### Is the unfiltered baseline the safest variant?

| Drawdown basis | Risk | Baseline fail_dd | Best lever | Worst lever | Verdict |
| --- | --: | --: | --- | --- | --- |
| `initial_balance_floor` | 0.50% | 0.0% | `lever_c` 0.0% | `lever_a_plus_b` 1.3% | baseline safest |
| `initial_balance_floor` | 0.75% | 2.3% | `lever_b` 1.1% | `lever_a_plus_b` 10.0% | `lever_b` safer by 1.2 pp |
| `initial_balance_floor` | 1.00% | 6.2% | `lever_d_zone_reject` 4.0% | `lever_a_plus_b` 13.3% | `lever_d_zone_reject` safer by 2.2 pp |
| `peak_to_trough` | 0.50% | 0.0% | `lever_c` 0.0% | `lever_a` 23.8% | baseline safest |
| `peak_to_trough` | 0.75% | 61.4% | `lever_c` 11.7% | `lever_a_plus_b` 57.4% | `lever_c` safer by 49.7 pp |
| `peak_to_trough` | 1.00% | 71.4% | `lever_d_zone_reject` 62.4% | `lever_a` 74.0% | `lever_d_zone_reject` safer by 9.0 pp |

### Aggregate, whole-period statistics (the view that favoured the filters)

| Variant | Trades | Win rate | Total R | Avg R / trade | Max DD (R) | Calmar |
| --- | --: | --: | --: | --: | --: | --: |
| Baseline - the live, unfiltered recipe | 1642 | 51.0% | 644.3 | +0.392 | 19.9 | 7.89 |
| Lever A - R:R floor raised to 2.5 (RECONSTRUCTED value) | 1347 | 48.6% | 606.0 | +0.450 | 23.5 | 6.31 |
| Lever B - key-level zone width <= 25 pips | 968 | 52.3% | 400.4 | +0.414 | 20.1 | 4.90 |
| Lever C - NY-only session 07:00-11:00 (RECONSTRUCTED window) | 789 | 49.3% | 319.7 | +0.405 | 17.3 | 4.53 |
| Levers A+B combined | 755 | 49.1% | 349.5 | +0.463 | 22.2 | 3.86 |
| Lever D (candidate) - require genuine Key Level zone rejection, not just CRT-range close | 1086 | 52.2% | 484.0 | +0.446 | 19.3 | 6.12 |

### Rolling-window survival, Phase-1 cap 10% static, basis `initial_balance_floor` (the user-confirmed static rule)

| Variant | fail_dd @ 0.50% | fail_dd @ 0.75% | fail_dd @ 1.00% |
| --- | --: | --: | --: |
| Baseline - the live, unfiltered recipe | 0.0% | 2.3% | 6.2% |
| Lever A - R:R floor raised to 2.5 (RECONSTRUCTED value) | 0.2% | 3.8% | 9.4% |
| Lever B - key-level zone width <= 25 pips | 0.2% | 1.1% | 6.4% |
| Lever C - NY-only session 07:00-11:00 (RECONSTRUCTED window) | 0.0% | 2.2% | 6.9% |
| Levers A+B combined | 1.3% | 10.0% | 13.3% |
| Lever D (candidate) - require genuine Key Level zone rejection, not just CRT-range close | 0.0% | 3.0% | 4.0% |

### Rolling-window survival, Phase-1 cap 10% static, basis `peak_to_trough` (the memory record's literal phrasing)

| Variant | fail_dd @ 0.50% | fail_dd @ 0.75% | fail_dd @ 1.00% |
| --- | --: | --: | --: |
| Baseline - the live, unfiltered recipe | 0.0% | 61.4% | 71.4% |
| Lever A - R:R floor raised to 2.5 (RECONSTRUCTED value) | 23.8% | 53.3% | 74.0% |
| Lever B - key-level zone width <= 25 pips | 16.4% | 27.9% | 69.4% |
| Lever C - NY-only session 07:00-11:00 (RECONSTRUCTED window) | 0.0% | 11.7% | 66.8% |
| Levers A+B combined | 16.4% | 57.4% | 69.0% |
| Lever D (candidate) - require genuine Key Level zone rejection, not just CRT-range close | 0.0% | 47.6% | 62.4% |

### Cross-check against the surviving historical figures

| Historical figure (VERIFIED) | Value | This reproduction | Delta |
| --- | --- | --- | --- |
| `baseline` trade count | 1681 | 1642 | -39 (-2.3%) |
| `lever_b` trade count | 975 | 968 | -7 (-0.7%) |
| `lever_a_plus_b` trade count | 768 | 755 | -13 (-1.7%) |
| `baseline` Phase-1 fail_dd @ 0.50% risk | 10.2% | 0.0% | -10.2 pp |
| `lever_b` Phase-1 fail_dd @ 0.50% risk | 16.0% | 0.2% | -15.8 pp |
| `baseline` Phase-1 fail_dd @ 0.75% risk | 13.7% | 2.3% | -11.4 pp |
| `lever_b` Phase-1 fail_dd @ 0.75% risk | 19.6% | 1.1% | -18.5 pp |
| `lever_a_plus_b` Phase-1 fail_dd @ 0.75% risk | 23.2% | 10.0% | -13.2 pp |
| `baseline` Calmar ratio | 4.35 | 7.89 | +3.54 |
| `lever_b` Calmar ratio | 6.46 | 4.90 | -1.56 |

## A live/backtest mismatch found while reconstructing this

Not part of the original comparison, but it surfaced from it and it affects the live scanner, so it is recorded here rather than dropped.

`scanner/main.py` builds its population with a bare `DetectorConfig()`, whose `BacktestConfig.kill_zone_gated` defaults to `True`. That gate restricts candidates to the NY 07:00-11:00 kill zone inside `build_stage6_population`, which is STRICTLY NARROWER than the 02:00-11:00 London+Lunch+NY session `scanner/rules.py::_in_session` then applies. The narrower gate wins, so the live scanner's effective session is 07:00-11:00 NY and its session filter changes nothing: measured on this corpus, the population is 1014 trades with that filter and 1014 without it.

Consequences worth a decision:

- The recipe's stated session is not the session being traded. Lever C ('NY-only narrowing'), a filter that was REJECTED, is approximately what the live scanner is already doing.
- The historical baseline count of 1681 is only reachable with the gate OFF, which is why `pipeline.build_variant` forces `kill_zone_gated=False`. That makes it near-certain the original comparison also ran with it off - i.e. the comparison measured a recipe the scanner does not currently run.

This research package changes nothing in `scanner/` or `detector/`. Reconciling them is a separate decision.

## Parameters this reproduction did NOT have to guess

| Parameter | Value (VERIFIED) | Basis |
| --- | --- | --- |
| pair | EURUSDm only | M1 |
| signal filter | key_level_reaction == "reject_close_inside" | M1 |
| exit | the detector's natural CRT-opposite-extreme take_profit | M1 |
| session | 02:00-11:00 America/New_York, DST-aware | M1 + scanner/rules.py |
| within-pair concurrency cap | 2R | M1 |
| daily risk rule | stop taking new trades after the 2nd loss of the day | M1 |
| rejected daily-risk alternative | max 1 trade/day (hurt results; not re-tested here) | M1 |
| H4 source | raw broker-native H4, NOT the UTC4aligned file | M1 |
| rolling window length | 250 days (Phase 1 + Phase 2 combined) | U |
| max-drawdown cap | 10% Phase 1 / 5% Phase 2, static from INITIAL balance | M1 + U |
| daily loss limit | 5%, static from INITIAL balance | M2 + U |
| lever B threshold | key-level zone width <= 25 pips | M2 |
| lever A lever | BacktestConfig.min_risk_reward, documented default 2.0 | M2 |

## Parameters this reproduction RECONSTRUCTED

Every value in this table is a rebuild, not a recovered historical fact. Treat any number in this report that depends on one as reproduction-grade evidence, not as a replay of the original run.

| Parameter | Value (RECONSTRUCTED) | Basis |
| --- | --- | --- |
| BacktestConfig.kill_zone_gated | False | FORCED, not chosen. With the library default (True) the detector's own NY 07:00-11:00 kill-zone gate subsumes the recipe's 02:00-11:00 session, making that session filter a no-op (1014 trades either way). Only with the gate off does the recipe's stated session govern, and only then does the baseline count reconcile with the historical 1681. See the report's live/backtest mismatch note. |
| lever A: min_risk_reward | 2.5 | PINNED BY CROSS-CHECK, not recovered. M2 names the lever but not the value. Sweeping it against M2's own lever-A+B count of 768 is decisive: 2.5 yields 755 (-1.7%), 3.0 yields 589 (-23%), 3.5 yields 443. 2.5 is the only candidate consistent with the record. |
| lever C: NY-only session | 07:00-11:00 NY-local | M2 names the lever but no window and gives no number to check against. Reuses the existing KillZoneConfig default (core/config.py) rather than inventing a window. |
| key-level zone width basis | the credited AlignedSignal.key_level, (top - bottom) * 10000 | M2 says 'the Daily Key Level's own price range in pips'. The credited key level is whichever tier the detector credited (H4 FVG or Daily order block when a Daily CSV is supplied); there is no separate 'Daily key level' field to read. |
| BacktestConfig.partial_fraction | 0.0 primary, 0.5 reported alongside | The library default is 0.5 (REQ-68, a LATER addition than this comparison). M1 describes the exit only as the natural take_profit level and says nothing about a partial leg. The choice is not cosmetic: at 0.0 the historical lever ORDERING reproduces, at 0.5 lever B reverses and looks better than the baseline. Both are published. |
| concurrency tie convention | a trade exiting on bar N frees its slot for a trade entering on bar N | See concurrency.py. The alternative yields 1613 baseline trades against this one's 1642 (historical: 1681). |
| daily-loss day key | the NY-local calendar date of the loss's own ENTRY | See daily_risk.py. Switching the timezone to UTC changes nothing (1642 either way). |
| Calmar ratio definition | (total R / years) / peak-to-trough drawdown in R | M2 quotes Calmar values but not the formula. This definition is risk%-independent. It reproduces the historical BASELINE value closely and the historical LEVER-B value not at all -- see the report's cross-check table. |
| rolling-window profit target | none modelled | A real challenge stops at its profit target, which truncates exposure. M2 mentions no target, so every window runs its full length, making the reported fail rates an upper bound. |

## Committed data artifacts

Under `data/partial_<fraction>/`:

- `trades_<variant>.csv` - every trade the variant took, after both account-level gates.
- `windows_<variant>.csv` - one row per rolling window per risk level per drawdown basis, carrying that window's own worst drawdown and breach flags, so every fail_dd% above can be recomputed independently from these rows alone.
- `summary.csv` - every number in the tables above, machine-readable.

