# Real-data evidence (Success Criteria) — two-stage exit vs. single-TP baseline

**What changed**: Success Criteria's real-data run, gathered after S-003 (all 4 slices complete). `partial_fraction` at its default (0.5), no `--daily-csv` — this run measures the EXIT MODEL (partial-at-equilibrium + remainder-to-target), not the confluence-gate (already measured and found to carry no edge earlier this session, see `project/pending-changes` obs #303).

**Command** (per instrument, from repo root):
```
./detector/.venv/Scripts/python.exe -m detector.cli \
  --csv pairs/M15/{instrument}_M15_*.csv --symbol {instrument} \
  --htf-csv pairs/H4/{instrument}_H4_*.csv --htf-symbol {instrument} \
  --output-dir .sdd/evidence/crt-detector-backtest-partial-exits/{instrument} --backtest
```
H4 file: each instrument's dated-range file (e.g. `EURUSDm_H4_202001020000_202608192000.csv`) — matches the pairing precedent already established by `crt-detector-ict-order-block`'s own evidence runs. The `*_UTC4aligned.csv` variant is not used (undocumented, no reference anywhere in specs/design/code).

## Results

| Instrument | Win rate | Avg R | Total R | Trades opened | Partial exits | Open trades |
|---|---|---|---|---|---|---|
| EURUSDm | 40.5% (943W/1384L) | 0.200 | 465.074 | 2327 | 945 | 0 |
| GBPUSDm | 40.5% (996W/1461L) | 0.259 | 635.973 | 2457 | 998 | 0 |
| DXYm | 39.1% (1061W/1655L) | 0.415 | 1126.542 | 2717 | 1063 | 1 |
| **Pooled** | **40.0% (3000W/4500L, n=7500 closed)** | **0.297** | **2227.589** | **7501** | **3006** | **1** |

Full coverage — complete count set across all 3 instruments. `partial_fraction=0.5` (default): ~40-43% of all opened trades fired a partial leg (945/2327, 998/2457, 1063/2717).

## Comparison to this session's single-TP baseline

The single-TP engine (measured earlier this session, `full-range-only target = HTF CRT range extreme, no partial`) produced 23-27% winrate with no measurable edge from the confluence-gate. The two-stage model:

- **Win rate**: 23-27% → **40.0%** pooled (39.1-40.5% per instrument, consistent, no outlier) — a 13-17 point jump.
- **Average R**: turns clearly and consistently **positive** across all 3 instruments (0.20-0.42R, pooled 0.297R), where the single-TP model showed no measurable edge.

**Interpretation**: directionally consistent with Mado's own claim that the partial-exit mechanism (not the confluence-gate, not the entry rule) is where the strategy's real edge lives — locking in a guaranteed-favorable partial before letting the remainder ride captures value that a full-range-only exit was giving back. The pooled 40% winrate is still well short of the self-reported ~75%, so this is evidence of a real, material improvement — not a claim that the gap is closed. Candidate remaining gaps (not yet investigated): trade management beyond a single partial (breakeven-after-partial, explicitly out of scope for this change), the confluence-gate's own lack of edge (already measured separately), and the possibility that Mado's real execution involves discretionary selectivity a mechanical backtest of every signal cannot replicate.

**Not yet done**: a partial_fraction sensitivity sweep (does 0.3 or 0.7 change the picture materially?) — out of scope for this change (single default value was the Success Criteria's ask), candidate follow-up.
