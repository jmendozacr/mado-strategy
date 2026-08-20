# Design: CRT/ICT Pattern Detector v1

**Change**: crt-pattern-detector-v1 | **Spec**: V3 signed | **Triage**: L

## 4.1 Architecture Overview

Layered pure-function pipeline under `detector/` (the Python project root — `detector/pyproject.toml`, not repo root, keeps the docs-only repo root clean; run via `cd detector && pytest`). `core`(Tier0) → `primitives`(Tier1: swing/fvg/crt_range, independent of each other) → `composite`(Tier2: mss, needs swing) → `entries`(Tier3: model1, needs crt_range+fvg) → `alignment`(Tier4: htf_ltf, needs crt_range+model1) → `viz`(needs result types only). `ingestion` is a leaf (loader.py, pairing.py), never imported back.

**Pattern**: none — simplest pure-function composition; no named GoF/architectural pattern warranted.

## 4.2 File Changes

| Path | Action | Purpose |
|---|---|---|
| `detector/pyproject.toml` | Create | Python 3.12, `uv`; deps: pandas, numpy, matplotlib, pytest, hypothesis, import-linter |
| `detector/core/candle.py` | Create | `Candle`, `OHLCSeries` (+ `.up_to(n)`), `instrument` from CLI flag |
| `detector/core/windows.py` | Create | Rolling N-candle window utility |
| `detector/core/results.py` | Create | `DetectionStatus` enum |
| `detector/core/config.py` | Create | `DetectorConfig` — nested frozen dataclass, Python-level defaults |
| `detector/core/pairing_table.py` | Create | charter-2's 5-row HTF/LTF table; `validate_pairing()` |
| `detector/primitives/swing.py` | Create | Swing detector |
| `detector/primitives/fvg.py` | Create | FVG detector |
| `detector/primitives/crt_range.py` | Create | CRT range detector (close-based resolution) |
| `detector/composite/mss.py` | Create | MSS detector |
| `detector/entries/model1.py` | Create | Model-1 detector (absorbs anchor/purge logic) |
| `detector/alignment/htf_ltf.py` | Create | HTF/LTF tagging |
| `detector/ingestion/loader.py` | Create | MT5 CSV parser |
| `detector/ingestion/pairing.py` | Create | Paired-file loader + instrument-match check |
| `detector/viz/chart.py` | Create | Chart renderer |
| `detector/viz/table.py` | Create | CSV table renderer |
| `detector/cli.py` | Create | Entry point |
| `detector/{core,primitives,composite,entries,alignment,ingestion,viz}/__init__.py` (7) | Create | Package markers |
| `detector/tests/conftest.py` + `fixtures/synthetic.py` | Create | In-code fixture builder functions |
| `detector/tests/test_{swing,fvg,crt_range,mss,model1,alignment,pairing,loader,viz}.py` (9) | Create | Per-module |
| `.importlinter` | Create | Layers contract |
| `detector/tests/test_fitness_config.py` | Create | Determinism + config-completeness |
| `detector/tests/property/test_no_lookahead.py` | Create | Hypothesis suite, all 5 detectors + alignment |
| `detector/tests/test_cli_e2e.py` | Create | Full pipeline e2e |
| `detector/README.md` | Create | Usage |
| `CLAUDE.md` (repo root) | Modify | Document the `detector/` subproject alongside the docs-only content side |
| `docs/charter-1.md`..`charter-5.md` | Read-only | Source methodology |

## 4.3 Data Model

```python
@dataclass(frozen=True)
class Candle:
    timestamp: datetime; open: float; high: float; low: float; close: float

@dataclass(frozen=True)
class OHLCSeries:
    candles: tuple[Candle, ...]; instrument: str
    timeframe: str  # "MN"|"W"|"D"|"4H"|"1H"|"15M"|"5M", inferred from modal timestamp delta
    def up_to(self, index: int) -> "OHLCSeries": ...  # candles with index < n (exclusive)

class DetectionStatus(str, Enum): CONFIRMED="confirmed"; INVALIDATED="invalidated"; PENDING="pending"

@dataclass(frozen=True)
class SwingPoint: index: int; price: float; kind: Literal["high","low"]

@dataclass(frozen=True)
class FVG:
    start_index: int; end_index: int; top: float; bottom: float
    direction: Literal["bullish","bearish"]; fill_status: Literal["open","filled"]

@dataclass(frozen=True)
class CRTRange:
    model: Literal["2-candle","3-candle","multi-inside","multi-outside"]
    high: float; low: float; start_index: int; end_index: int
    resolution: Literal["true_break","false_break"]; resolved_at_index: int

@dataclass(frozen=True)
class MSSEvent: index: int; direction: Literal["bullish","bearish"]; broken_swing: SwingPoint

@dataclass(frozen=True)
class Model1Signal:
    anchor_index: int; direction: Literal["bullish","bearish"]; purge_target: float
    confirmation_type: Literal["purge_engulf","fvg_fill"]
    entry_type: Literal["wick","body"]; entry_price: float
    retest_index: int | None; status: DetectionStatus

@dataclass(frozen=True)
class AlignedSignal:
    ltf_signal: Model1Signal; htf_context: CRTRange | None
    aligned: Literal["aligned","unaligned","insufficient_htf_data"]
```

## 4.4 Algorithm Predicates (complete)

**Swing (REQ-06)**: strict fractal, `high[i] > high[i-1] AND high[i] > high[i+1]`. No discretionary threshold.

**No-lookahead `k`**: Swing=1, FVG=3(window), CRT range=`max_lookback`(20), MSS=swing-confirmation window, Model-1=`max_retest_lookback`(20). Property: `detect(series.up_to(n))` truncated to indices `< n-k` MUST equal full-series output truncated the same way. Comparison semantics: for indices `≤ n-k-1`, full equality including mutable fields (status, fill_status); for indices in `(n-k-1, n)` (inside the settling window), only stable identity fields need match — status legitimately differing there is expected, not a violation.

**FVG (REQ-08/09/10)**: bullish = `candle[i+2].low > candle[i].high`; min-size = `FVGConfig.min_size_atr = 0.1` (× ATR(14) at formation, standard 14-period true-range average). Fill = cumulative price action after formation has traded (via wick) to the far edge of the gap — the running minimum low (bullish) / maximum high (bearish) reaches the opposite edge. Binary `open`/`filled`, no partial state.

**CRT range — formation** (was previously undefined): every candle index `i` is tried as a candidate range-establishing candle ("Vela 1"); its High/Low seed the candidate range. Looking forward up to `max_lookback=20` candles, the algorithm checks for resolution. Overlapping candidates from different starting indices are NOT deduplicated — each independently-resolving range is emitted; the CLI's date filter narrows a cluttered view, not detector-side suppression.

**CRT range — resolution predicate** (charter-5 [00:08:50] "wicks lie, closes tell the truth"): `true_break` = a candle's CLOSE goes beyond the range High/Low. `false_break` = a candle's WICK pokes beyond but its CLOSE stays inside, AND a subsequent candle's CLOSE reverses back through the range by at least reaching the opposite side's midpoint. Neither within `max_lookback` → not emitted (REQ-14).

**CRT range — model classification** (corrected during plan-verify — the original "trapped-candle count" rule contradicted charter-1's own taxonomy):
- `2-candle`: Vela1=range. Vela2 BOTH purges AND fully expands to the opposite extreme.
- `3-candle`: Vela1=range. Vela2 purges only (closes back inside). Vela3 fully expands.
- `multi-inside`: Vela1=range. Candles 2..N-1 stay trapped WITHIN [low,high]. Candle N finally purges.
- `multi-outside`: Vela1=range. Vela2 purges (like 3-candle). Expansion takes MULTIPLE subsequent candles (3+) instead of completing in Vela3 alone.

**MSS (REQ-15/16)**: "swing-to-extreme distance" = distance from the broken swing's price to the most recent swing point of the OPPOSITE kind formed before it. "Prior opposite-extreme rejection" = that opposite-kind swing existing at all before the break (requires a genuine swing-low→swing-high→break-below structure, not a one-directional run). `decisive_close_ratio=0.25` multiplies this distance; the break candle's close must exceed the swing by at least that fraction.

**Model-1 (REQ-17-22)**:
- `purge_target` scope (v1): CRT High/Low ONLY, not arbitrary old swing highs/lows (deliberate narrowing for the conservative posture — an ICT-standard enhancement for a fast-follow, not v1). `entries/model1.py` depends on `primitives.crt_range` for purge targets, NOT on Swing directly.
- Wick-vs-Body: PRIMARY — confirming candle's close beyond the anchor's WICK extreme → Wick. If close is beyond the anchor's BODY extreme but not its wick extreme (middle zone) → TIEBREAK: anchor's body/range ratio ≥ `body_ratio_tiebreak=0.6` → Body, else → Wick.
- Retest: first candle after confirmation whose wick range overlaps the anchor's BODY range `[min(open,close), max(open,close)]`.
- CONFIRMED: retest occurs AND a close in the trade direction follows (any magnitude beyond the retest candle's own open — no minimum threshold).
- INVALIDATED: any candle CLOSES beyond the anchor's protected extreme (`respect_rule_tolerance=0`, close-based per charter-2's literal "cerró" — a wick breach alone does NOT invalidate). Can occur before or after a retest.
- CONFIRMED is TERMINAL — v1 does no trade-management/exit tracking.
- PENDING: `max_retest_lookback=20` candles or series end elapse with the anchor unbreached and no retest yet.

**Alignment (REQ-05)**: `aligned` iff the LTF signal's timestamp falls within `[htf_purge_candle.timestamp, htf_purge_candle.timestamp + htf_timeframe_duration]` of a resolved HTF CRTRange. `insufficient_htf_data` = the relevant HTF candle isn't fully covered by available LTF data (tail case, ADR-05). Else `unaligned`.

## 4.5 Architecture Decisions

### ADR-01: Detector layering + one-way import rule
`core`→nothing; `primitives`→`core`; `composite`→`core`+`primitives`; `entries`→`core`+`primitives` (NOT composite — Model-1 doesn't need MSS); `alignment`→`core`+`primitives`+`entries`; `viz`/`cli`→result types only; `ingestion`→leaf. Enforced by `.importlinter` layers contract. Alternative rejected: folding `alignment` into `ingestion` — would invert the leaf-ingestion rule.

### ADR-02: One typed immutable config dataclass
`DetectorConfig`, nested per detector, passed explicitly (never a global/singleton). Alternatives rejected: per-detector kwargs (transitive param explosion), scattered module constants (undiscoverable, defeats the config-completeness fitness function).

### ADR-03: No-lookahead / causal-detection contract
Every detector's output over `series.up_to(n)` is invariant to candles beyond n (within its settling window k) — a structural contract, not just a test suite. User confirmed the full hypothesis suite for v1 over a lighter alternative.

### ADR-04: Core data model — dataclass + tuple, pandas confined to ingestion
`Candle`/`OHLCSeries` are frozen dataclasses; `loader.py` may use pandas internally but converts before returning. Alternative rejected: pandas DataFrame end-to-end — would leak pandas' API into every detector signature.

### ADR-05: HTF↔LTF partial-candle boundary policy
Partial-tail-coverage → `insufficient_htf_data` (conservative, distinct from `unaligned` — never hard-reject the run, never silently exclude the signal).

### ADR-06: Instrument identity supplied explicitly via CLI, not parsed from CSV
MT5's standard export has no symbol column. `--symbol` (single-series) / `--htf-symbol`+`--ltf-symbol` (pair mode) required flags populate `OHLCSeries.instrument`. Alternatives rejected: filename parsing (fragile), price-magnitude inference (unreliable).

## 4.6 CLI Contract

```
python -m detector.cli --csv PATH --symbol SYM
                        [--htf-csv PATH --htf-symbol SYM]   # pair mode, adds alignment
                        --output-dir PATH
                        [--from-date YYYY-MM-DD] [--to-date YYYY-MM-DD]   # filters RESULTS, not input
                        [--types swing,fvg,crt_range,mss,model1,alignment]  # default: all
```
Timeframe is ALWAYS inferred from each series' modal timestamp delta — no `--timeframe` flag (avoids flag-vs-data disagreement).

**Output**: `{output-dir}/overlay.png` (matplotlib, 150 DPI; 1 panel single-series, 2-panel stacked HTF-top/LTF-bottom in pair mode; legend always shown). `{output-dir}/detections.csv` (columns: `timestamp,type,direction,price_high,price_low,status[,aligned]`; one row per detection object). Exit 0 (including zero detections — still emits valid empty outputs), exit 1 on load/validation/unknown-`--types`-token error.

**Ingestion validation**: ERROR (exit 1) — duplicate timestamps, non-monotonic timestamps, `high<low` or OHLC outside `[low,high]`, missing/NaN values. TOLERATED — weekend/session gaps (normal FX data). Fewer candles than the largest lookback: not a load error, detectors simply produce nothing until enough data accumulates.

**Viz build strategy**: S-001 through S-005 each ADD their encoding to the SAME `viz/chart.py` incrementally (extend, never rewrite). S-006 is wiring only (CLI filters + `viz/table.py` + e2e test).

## 4.7 Fitness Functions
- **Import-direction** (ADR-01): `import-linter`, `.importlinter` layers contract.
- **Determinism/purity**: hypothesis — same series in, identical detections out, twice.
- **No-lookahead** (ADR-03): hypothesis property test per detector.
- **Config-completeness** (ADR-02): custom AST scan — no bare numeric literal outside `config.py`.

## 4.8 Migration / Rollout
Not applicable — greenfield.

## 4.9 Performance
Not applicable at v1 data volumes (thousands of rows, not millions).

## 4.10 Architecture Impact
**additive** — no baseline existed before this change; this design creates the first one. `/sdd-architecture scan` recommended AFTER this change ships, not before.

## 4.11 Open Questions
None — all resolved through the plan-verify gate (3 iterations) and direct user confirmation. See `verify-plan.md` for the full history.

## Registered Follow-ups (not v1)
- CRT range "currently forming / live" PENDING state (only the last candle's in-progress range, not reintroducing REQ-14's noise problem) — v1.1 candidate.
- Standalone ICT-conventional Order Block + Breaker Block detectors — separate M change.
- SMT Divergence, Rejection Block detectors — separate changes.
