# EURUSD recipe validation

Research tooling. Nothing here is imported by `detector/` or `scanner/`; it
reuses the detector's pipeline unmodified and builds analysis on top, the
same shape as `detector/research/classify_trades.py` and
`research/dukascopy_eurusd_gbpusd/`.

**Read `data/REPORT.md` for the results.** This file explains what the
numbers are, what was verified, and what had to be rebuilt.

## What this is

A reproduction of a comparison run months ago, in a session whose scratch
data was never committed and is now gone. That comparison tested three
"quality over quantity" filters against the unfiltered EURUSD signal
recipe, rejected all three, and kept the unfiltered baseline — which is
what `scanner/rules.py` runs live today. Two memory records survived with
the decision and a handful of concrete numbers; the trade-by-trade data and
the prop-firm sizing simulation behind them did not.

So this is a **reproduction, not a replay**. Some of it reproduces closely
enough to confirm the original, some of it does not, and the difference is
labelled everywhere it appears — in the code, in the docstrings, and in the
generated report.

## The finding being reproduced

A filter that keeps only the best-looking signals improves every per-trade
average and shrinks the sample at the same time. The averages are what a
backtest summary shows you. The shrunken sample is what fails a funded
account, because what breaches a drawdown cap is a local cluster of losses,
not a lifetime expectancy.

Measured here, at 0.75% risk per trade against a static 10% Phase-1 cap:
the filtered variant with the **best** per-trade expectancy (+0.496 R
against the baseline's +0.397 R) would have blown a 250-day challenge in
**15.9%** of all possible start days against the baseline's **4.3%** —
roughly four times as often. That ratio holds on both exit models tested.

## Reproduce it

```sh
uv run --project detector python -m research.eurusd_recipe_validation.compare
```

From the repository root. Takes a few minutes; rewrites everything under
`data/`. Tests:

```sh
uv run --project detector python -m pytest research/eurusd_recipe_validation/tests -q
```

## Layout

| File | What it is |
| --- | --- |
| `sizing.py` | The rolling-window prop-firm simulator. RECONSTRUCTED. |
| `concurrency.py` | The within-pair 2R concurrency gate. RECONSTRUCTED. |
| `daily_risk.py` | Stop after the second loss of the day. RECONSTRUCTED. |
| `trades.py` | The trade record the stages share, plus the session/day helpers. |
| `pipeline.py` | Variant construction over the detector's own, unmodified pipeline. |
| `historical.py` | The surviving historical figures, as data, so the report computes its own cross-check. |
| `compare.py` | The one command that regenerates every artifact. |
| `data/` | The committed run output. |

`data/<exit model>/trades_<variant>.csv` is every trade a variant took.
`data/<exit model>/windows_<variant>.csv` is one row per rolling window per
risk level per drawdown basis, each carrying that window's own worst
drawdown and breach flags — every `fail_dd%` in the report is recomputable
from those rows and nothing else.

## What is reused, never reimplemented

- Detection and alignment: `cli._detect_all`, the exact function
  `scanner/main.py` calls.
- Candidate construction and trade resolution:
  `backtest.simulate.simulate`, which calls `build_stage6_population`
  itself.
- The exit: the detector's own `backtest.levels.take_profit`, the HTF CRT
  range's opposite extreme. No fixed R:R multiple is tested here — the
  memory record states the natural exit already beat every multiple from
  1.0 to 3.0.
- The purge reaction classification: `AlignedSignal.key_level_reaction`,
  from `alignment.htf_ltf._purge_reaction`.
- The session: copied from `scanner/rules.py::_in_session` and pinned to it
  hour by hour by `tests/test_trades.py`, so the comparison can never
  silently measure a window the live scanner no longer trades.

Data: `pairs/H4/EURUSDm_H4_202001020000_202609042000.csv` (raw,
broker-native) with `pairs/M15/EURUSDm_M15_202207260000_202609042045.csv`
and `pairs/D1/EURUSDm_Daily_202001020000_202609040000.csv`. **Not**
`pairs/H4/EURUSDm_H4_UTC4aligned.csv`, which the memory record says
silently degraded every result when it was used.

## Verified vs. reconstructed

`data/REPORT.md` prints both as tables, generated from `historical.py`, so
they cannot drift from the numbers beside them. In short:

**Verified** (carried by the surviving records or confirmed by the user):
the pair, the `reject_close_inside` signal filter, the natural take-profit
exit, the 02:00–11:00 NY session, the 2R concurrency cap, the
stop-after-two-daily-losses rule, the raw H4 source, the 250-day window,
the static 10%/5% max-drawdown caps and 5% daily limit, lever B's 25-pip
threshold, and that lever A's lever was `BacktestConfig.min_risk_reward`.

**Reconstructed** (rebuilt here; the originals are lost): both gating rules
in full, the entire sizing simulator, lever A's actual R:R value, lever C's
session window, the Calmar formula, the drawdown basis, the exit model's
partial fraction, and `kill_zone_gated=False`.

Two reconstructions deserve naming here because the report's numbers turn
on them:

- **Lever A's R:R value was recovered by cross-check, not guessed.** The
  record names the lever but not the value. Sweeping it against the
  record's own lever-A+B trade count of 768 is decisive: `2.5` yields 755,
  `3.0` yields 589, `3.5` yields 443. Only 2.5 is consistent.
- **The exit model changes the conclusion, so both are published.** The
  detector's current default closes 50% of the position at the
  entry-to-target midpoint (REQ-68, added *after* this comparison was run).
  The record describes the exit only as the natural take-profit level. At
  `partial_fraction=0.0` the historical lever ordering holds; at `0.5` the
  trade counts match the record more closely but lever B overtakes the
  baseline at 0.75% risk. Neither is "the" original run.

## Known unreproduced figures

Reported rather than tuned away. The task this work was commissioned under
was explicit that forcing a match would be worse than reporting a gap.

### Trade counts: reproduced

| Historical | This rebuild (`partial 0.5`) | Delta |
| --- | --- | --- |
| baseline 1681 | 1642 | −2.3% |
| lever B 975 | 968 | −0.7% |
| lever A+B 768 | 755 | −1.7% |

Three independent counts within 2.3%, with a consistent small shortfall —
the signature of a minor tie-break difference in the lost gating code, not
a wrong pipeline. This is the strongest evidence that the population being
measured here is the population that was measured then. At
`partial_fraction=0.0` the same three land 4.4–5.9% low.

### Absolute `fail_dd%`: NOT reproduced

Every historical fail rate is 7–19 percentage points higher than this
rebuild produces:

| Historical | This rebuild (`partial 0.5`, floor basis) |
| --- | --- |
| baseline @ 0.50% risk: 10.2% | 0.0% |
| lever B @ 0.50% risk: 16.0% | 0.2% |
| baseline @ 0.75% risk: 13.7% | 2.3% |
| lever B @ 0.75% risk: 19.6% | 1.1% |
| lever A+B @ 0.75% risk: 23.2% | 10.0% |

The cause is structural, not a tuning gap. Under a cap measured statically
from the window's initial balance, a 10% breach at 0.50% risk requires a
20R fall below the starting balance. Across all 1251 windows the
reconstructed baseline's worst such fall has a 90th percentile near 8–11R
and a maximum near 19–21R, so a ~10% fail rate is not reachable from this
trade population by any choice of the parameters above. The lost
simulator's equity model was materially harsher than its surviving
description specifies. Candidates not resolvable from what survives:
trading costs (`trading_cost_price` defaults to 0.0 here, so this rebuild
pays no spread), a different risk basis, or mark-to-market on floating
rather than realised P&L. Both drawdown bases are published precisely
because this is unresolved — `peak_to_trough` is harsher and overshoots
instead.

**Consequence for a reader:** the ratios and the ranking in the report are
reproduction-grade evidence. The absolute percentages are this rebuild's
own, and are more optimistic than the originals. Do not size an account off
them.

### The Calmar contrast: NOT reproduced

The record has lever B scoring *better* than the baseline on Calmar (6.46
vs 4.35), which is exactly what made the windowed check decisive. Under the
reconstructed Calmar definition — annualised R over worst peak-to-trough R,
risk-independent — the baseline scores better on both exit models
(4.89 vs 3.18 at `partial 0.0`). The reconstructed baseline value is close
to the historical one; the lever B value is not, and the ordering reverses.
The record does not carry the formula, so the definition is the most likely
difference.

The underlying effect still reproduces, just in a different statistic: on
per-trade expectancy and win rate the filtered variants do look better than
the baseline, and on windowed survival they are worse. That is the claim the
report makes, and it makes it from expectancy rather than from Calmar.

## A live/backtest mismatch found on the way

Not part of the original comparison, but it affects the live scanner, so it
is recorded instead of dropped.

`scanner/main.py` builds its population with a bare `DetectorConfig()`,
whose `BacktestConfig.kill_zone_gated` defaults to `True`. That gate cuts
candidates to the NY 07:00–11:00 kill zone inside
`build_stage6_population` — strictly narrower than the 02:00–11:00 session
`scanner/rules.py::_in_session` then applies. The narrower gate wins, so
the live scanner's effective session is 07:00–11:00 and its own session
filter changes nothing: measured on this corpus, 1014 trades with it and
1014 without.

Two consequences worth a decision:

- The recipe's stated session is not the session being traded, and lever C
  ("NY-only narrowing") — a filter that was rejected — is approximately
  what the scanner already does.
- The historical baseline of 1681 is only reachable with that gate off,
  which is why `pipeline.build_variant` forces `kill_zone_gated=False`. So
  the original comparison almost certainly ran with it off too, i.e. it
  measured a recipe the scanner does not currently run.

This package changes nothing in `scanner/` or `detector/`. Reconciling them
is a separate decision.

## Not re-tested, already settled

The memory records state these were tested and rejected; re-running them was
out of scope:

- Fixed R:R exit multiples from 1.0 to 3.0 — the natural take-profit exit
  beat all of them.
- "Max 1 trade per day" instead of the two-loss stop — it hurt results.
- `pairs/H4/EURUSDm_H4_UTC4aligned.csv` as the H4 source — it silently
  degraded every result.
- GBPUSDm as a second pair — its standalone drawdown profile was too weak
  to run as its own account.
