# Slices: CRT/ICT Pattern Detector v1

**Triage**: L | **Spec**: V3 signed | **Design**: complete | **Total slices**: 7 (1 skeleton + 6)

## Global facts (every slice relies on these — self-contained by design, see `design.md` for full derivations)

- **Location/tooling**: `detector/` at repo root, sibling to `docs/`. `detector/pyproject.toml` is the Python project root. Python 3.12, `uv`. Deps: pandas, numpy, matplotlib, pytest, hypothesis, import-linter.
- **CSV format**: MT5 standard export, tab-delimited, header row: `<DATE> <TIME> <OPEN> <HIGH> <LOW> <CLOSE> <TICKVOL> <VOL> <SPREAD>`, date `yyyy.MM.dd`, time `HH:mm:ss` (separate columns), broker-local timezone unconverted.
- **Layering (ADR-01)**: `core`→nothing; `primitives`(swing/fvg/crt_range)→`core`; `composite`(mss)→`core`+`primitives`; `entries`(model1)→`core`+`primitives` (NOT composite); `alignment`(htf_ltf)→`core`+`primitives`+`entries`; `viz`/`cli`→result types only; `ingestion`(loader/pairing)→leaf.
- **Data model, algorithm predicates, config defaults**: see `design.md` §4.3/§4.4 — fully pinned (Swing tie rule, FVG gap formula + ATR-based min-size, CRT range formation + close-based resolution + corrected model classification, MSS decisive-close ratio, Model-1 full state machine + wick/body priority + retest definition).
- **Config defaults**: `FVGConfig.min_size_atr=0.1`, `CRTRangeConfig.max_lookback=20`, `MSSConfig.decisive_close_ratio=0.25`, `Model1Config.max_retest_lookback=20`, `Model1Config.body_ratio_tiebreak=0.6`, `Model1Config.respect_rule_tolerance=0`.
- **Instrument identity**: `--symbol`/`--htf-symbol`/`--ltf-symbol` CLI flags (ADR-06) — MT5 CSVs carry no symbol column.
- **No-lookahead**: `k` per detector (Swing=1, FVG=3, CRT range=20, MSS=swing-window, Model-1=20); comparison semantics in design.md §4.4.
- **Fixture mechanics**: in-code builder functions in `tests/fixtures/synthetic.py`, shared across all slices. Charter-cited fixtures = synthetic candles matching the charter's DESCRIBED behavior — NOT pixel-transcribed from video screenshots (deliberate; a hand-transcribed screenshot value isn't more trustworthy than a purpose-built fixture with known expected output).
- **CLI contract** (full, see design.md §4.6): `python -m detector.cli --csv PATH --symbol SYM [--htf-csv PATH --htf-symbol SYM] --output-dir PATH [--from-date D] [--to-date D] [--types LIST]`. No `--timeframe` flag — always inferred from data. Filters apply to RESULTS, never input.
- **Output**: `overlay.png` (150dpi, 1 or 2-panel), `detections.csv` (`timestamp,type,direction,price_high,price_low,status[,aligned]`).
- **Chart encodings**: Swing=triangle, FVG=shaded rect, CRT range=bracket+labels, MSS=dashed vline, Model-1=arrow+entry line, alignment=border color (green/gray/dashed-gray).
- **e2e image assertion**: inspect the matplotlib figure/axes object's plotted-element counts/types before saving — never pixel/hash comparison.
- **Manual acceptance step** (user decision, plan-verify gate): before v1 is considered done, run the tool against ONE real MT5-exported file and visually confirm the output looks sane. Not an automated pass/fail — a human sanity check, added as the closing task of S-006.
- **CLAUDE.md task**: S-000 updates repo-root `CLAUDE.md` to describe the `detector/` subproject (stack, test command: `cd detector && pytest`) alongside the existing docs-only description.

---

## S-000: Walking Skeleton
**Scope**: walking-skeleton | **Requires**: nothing | **Covers**: REQ-01, REQ-02, REQ-06, REQ-07, REQ-23 (happiest path)

**Acceptance**: GIVEN a single-series MT5 CSV + `--symbol EURUSD`, WHEN run via `python -m detector.cli`, THEN `overlay.png` with Swing markers is produced; `.importlinter` + hypothesis harness pass.

### Tasks
- [x] S-000.1 `core/candle.py`, `core/results.py`, `core/config.py` (empty `SwingConfig` — no fields needed), `detector/pyproject.toml`
- [x] S-000.2 `ingestion/loader.py` — MT5 format, `--symbol` flag (REQ-01/02)
- [x] S-000.3 `primitives/swing.py` (REQ-06) + `property/test_no_lookahead.py` harness (REQ-07, k=1)
- [x] S-000.4 `viz/chart.py` (Swing triangle markers only)
- [x] S-000.5 `cli.py` (single-series mode, full arg parsing)
- [x] S-000.6 `.importlinter` + `test_fitness_imports.py`
- [x] S-000.7 `tests/conftest.py` + `fixtures/synthetic.py` builder pattern, first fixture (charter-2 [00:05:28] shape)
- [x] S-000.8 Update repo-root `CLAUDE.md`

## S-001: FVG detection
**Requires**: S-000 | **Covers**: REQ-08, 09, 10, 25 (FVG config), 26.1 (k=3)
- [x] `primitives/fvg.py` (predicate + min_size_atr + fill semantics per Global facts) + tests + property test + viz marker

## S-002: CRT range detection
**Requires**: S-000 | **Covers**: REQ-11–14, 25 (max_lookback=20), 26.1
- [x] `primitives/crt_range.py` (formation + close-based resolution + corrected model classification per design.md §4.4) + tests (4 variants: true-break/false-break/never-resolves-absent/resolves-on-last-candle) + property test + viz marker

## S-003: MSS detection
**Requires**: S-000 (Swing) | **Covers**: REQ-15, 16, 25 (decisive_close_ratio=0.25), 26.1
- [ ] `composite/mss.py` (per design.md §4.4's precise predicate) + tests + property test + viz marker (draw-only in v1 — no downstream consumer, deliberate)

## S-004: Model-1 entry detection (core value)
**Requires**: S-001, S-002 | **Covers**: REQ-17–22, 25 (body_ratio_tiebreak, respect_rule_tolerance, max_retest_lookback)

**Fixtures**: anchor-detection (wick/body priority) isolated from 3 post-anchor state fixtures (CONFIRMED/INVALIDATED/PENDING) + 3 charter-2-behavior-matching examples (purge-engulf [00:05:28]-[00:06:04], delayed-engulf [00:06:35]-[00:07:02], dual purge+FVG-fill [00:07:27]-[00:07:56]).

- [ ] `entries/model1.py` (full state machine + entry-selection rules per design.md §4.4; `purge_target` = CRT High/Low only, NOT arbitrary swings) + tests + property test (k=20) + viz marker

## S-005: HTF↔LTF alignment
**Requires**: S-002, S-004 | **Covers**: REQ-03, 04, 05, 27, 26.2
- [ ] `core/pairing_table.py` (charter-2's 5-row table) + `ingestion/pairing.py` (REQ-03/04/27) + `alignment/htf_ltf.py` (3-state tagging per ADR-05) + property test + `cli.py` pair-mode args

## S-006: Full viz + CLI filters + manual acceptance
**Requires**: S-001–S-005 | **Covers**: REQ-23, 24, 28
- [ ] `viz/chart.py` (wiring only — encodings already added incrementally) + `viz/table.py` (REQ-24) + `cli.py` (`--from-date/--to-date/--types`) + `tests/test_cli_e2e.py` (full pipeline)
- [ ] **Manual acceptance**: run against one real MT5 export, visually confirm output — v1 done only after this passes

---

## Build Order
S-000 → {S-001, S-002, S-003 parallel} → S-004 → S-005 → S-006

## Anti-Pattern Check
✅ Pass — 7 slices, max dependency depth 2, each names a capability not a layer.
