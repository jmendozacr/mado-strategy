# Pre-gate baseline (H4/M15) — EURUSDm, GBPUSDm, DXYm

**Captured**: 2026-08-30, at commit `4851f545a7249c6372fdf1619e9dfa0519d11037` (verified `git diff f44b2c4..HEAD -- detector/` is empty — the detector tree is byte-identical to the commit obs #419 was captured at, so these figures are exactly comparable to it). Supplements engram obs #419 (topic `sdd/crt-detector-key-level-confluence-core/pre-gate-baseline`) in place — no re-run of EURUSDm's cost sweep.

**Command** (per instrument, `{instrument}` substituted):

```
python -m detector.cli \
  --csv pairs/M15/{instrument}_M15_*.csv --symbol {instrument} \
  --htf-csv pairs/H4/{instrument}_H4_*.csv --htf-symbol {instrument} \
  --output-dir .sdd/evidence/crt-detector-key-level-confluence-core/pre-gate/{instrument} --backtest
```

**EURUSDm validity check**: this run's `metrics_summary.txt` matches obs #419's recorded block exactly (same `signals considered`, `trades opened`, win rate, average R, total R, open trades, same-candle SL+TP count, and all seven reconciliation bucket counts). Obs #419 confirmed still valid against HEAD — the pre-gate baseline this walking skeleton's REQ-60.2/.4 comparisons depend on.

## EURUSDm

```
signals considered: 142984
trades opened: 2402
win rate: 0.273 (656W / 1746L)
average R: 0.244 over 2402 closed trades
total R: 585.672 over 2402 closed trades
open trades: 0
same-candle SL+TP resolutions: 11
reconciliation:
  no crt range: 17143
  unaligned: 20780
  never confirmed: 63901
  duplicate: 9060
  kill zone: 26147
  rr floor: 3521
  never filled: 30
```

`detections.csv` Model-1 row count (pre-gate): **142984**

## GBPUSDm

```
signals considered: 143054
trades opened: 2502
win rate: 0.265 (662W / 1840L)
average R: 0.270 over 2502 closed trades
total R: 675.741 over 2502 closed trades
open trades: 0
same-candle SL+TP resolutions: 16
reconciliation:
  no crt range: 17034
  unaligned: 20454
  never confirmed: 64332
  duplicate: 8873
  kill zone: 26468
  rr floor: 3367
  never filled: 24
```

`detections.csv` Model-1 row count (pre-gate): **143054**

## DXYm

```
signals considered: 142776
trades opened: 2838
win rate: 0.262 (742W / 2095L)
average R: 0.502 over 2837 closed trades
total R: 1423.185 over 2837 closed trades
open trades: 1
same-candle SL+TP resolutions: 24
reconciliation:
  no crt range: 18171
  unaligned: 20497
  never confirmed: 64299
  duplicate: 8530
  kill zone: 25408
  rr floor: 3007
  never filled: 26
```

`detections.csv` Model-1 row count (pre-gate): **142776**

## REQ-60.2 denominator (per §9.1) — EURUSDm

`signals_considered − excluded_no_crt_range − excluded_unaligned` = `142984 − 17143 − 20780` = **105061**, matching design §9.1's cited figure exactly.
