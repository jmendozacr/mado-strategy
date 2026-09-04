# Proposal: crt-detector-key-level-confluence-core

**Triage**: L | **Program**: `crt-detector-key-level-confluence` (sub-change #1, walking skeleton) | **Persona lens**: none

## Intent

Charter-1 [00:12:02] makes reaction at an HTF Key Level a precondition of a valid Model-1 setup — the detector has never implemented that check. Every Model-1 signal it finds is reported as tradeable, so `detections.csv` and `--backtest`'s metrics describe an unfiltered signal stream, not the methodology as the user actually trades it. The user's own words: a Model-1 that does not react at a Key Level "is not a real setup". The reported +0.244R average on H4→M15 is therefore computed over a population containing setups the methodology itself rejects, and cannot be trusted as an edge estimate. This sub-change makes the confluence check a hard validity gate using the one Key Level source that already exists in code (FVG), so both artefacts finally report only endorsed setups — and establishes the `KeyLevel` seam that sub-changes #2 (ICTOrderBlock) and #3 (Breaker Block) plug into without touching the gate.

## Scope

### In Scope

- `core/key_level.py`: frozen `KeyLevel` dataclass (`kind`, `top`, `bottom`, `origin_index`) importing nothing from `primitives`/`composite` (SEAM-01).
- `to_key_levels(fvgs) -> list[KeyLevel]` adapter on `primitives/fvg.py`, with `origin_index = end_index` (`start_index + 2`), never `start_index` (SEAM-02).
- New HTF FVG detection stage in `_detect_all` — compute-only: not rendered on `overlay.png`, no change to `--types fvg`'s LTF-only meaning.
- Confluence determination in `alignment/htf_ltf.py`: `AlignedSignal.key_level: KeyLevel | None`, credited when the HTF purge candle's actual wick extreme (high for bullish purge, low for bearish) geometrically overlaps `[top, bottom]` and `origin_index < purge_index`. No tolerance parameter.
- A filled/mitigated FVG still counts as a valid Key Level; `fill_status`/`fill_index` are never read by `to_key_levels`.
- `_filter_to_confluent` in `cli.py`, inserted between the `population` snapshot (line 120) and `_filter_by_types` (line 121). Surgical predicate: `keep(t) = t.aligned != "aligned" or t.key_level is not None`.
- 8th exclusion bucket `excluded_no_key_level`, appended LAST in `_population_cuts`' chain; new `ReconciliationReport` field; new line in `viz/trades_table.py`.
- MODIFIED signed requirements: REQ-45/45.3, REQ-30 (+`REQ-30.7`), REQ-40/40.1 (+`REQ-40.5`).
- Fitness functions: cross-artefact reconciliation, two-sided `origin_index` no-lookahead boundary, gate-level no-lookahead, fill-status independence, per-signal exclusive bucket membership, minimal-pair confluent/non-confluent discipline, REQ-42.1 under gating, SEAM-01 consumer-coupling.

### Out of Scope

- Swing as a Key Level source — user deferred explicitly to a later sub-change.
- ICTOrderBlock (#2), Breaker Block (#3), Rejection Block (no definitional source; stays at `project/pending-changes`).
- Source-attribution column in `detections.csv` — deferred to #2. Header stays at its signed 7 columns; REQ-24 and REQ-41.3 are NOT touched.
- Any confluence tolerance/proximity parameter — rejected in favour of direct geometric overlap.
- Rendering HTF FVGs, or any `--types` semantic change.
- Single-series mode behaviour — confluence is undeterminable without HTF data; the user always runs paired. Documented, not built around.
- Named-fields refactor of `_population_cuts`' return tuple — deferred to design's judgement.
- Any change to `entries/model1.py` or REQ-17 — the gate is strictly downstream (ADR-001 layering).

## Capabilities

### New Capabilities

- `key-level-confluence`: KeyLevel type, FVG adapter, confluence determination, and the validity gate.

### Modified Capabilities

- `detector`: REQ-45 byte-compat re-anchored differentially; REQ-30 candidate selection gains a confluence exclusion; REQ-40 grows from seven exclusion buckets to eight.

## Approach

`KeyLevel` is a normalising frozen dataclass in `core/` (not a Protocol, not a union): each detector module owns a `to_key_levels` adapter, so `alignment` depends on one stable shape rather than on N detector types. `origin_index` is the index at which the level is first *provably knowable* — for an FVG that is `end_index`, since the geometry reads `candles[i]` and `candles[i+2]`; using the geometric anchor `start_index` would credit a signal against a gap not yet knowable, violating the project's flagship no-lookahead fitness function for real, not in theory.

The gate must sit above `entries/` — `detect_model1_signals` is pure-LTF by design and cannot see HTF context. Confluence is therefore *determined* in `alignment/htf_ltf.py` (which already holds HTF context) and *enforced* in `cli.py`. Placement resolves a contradiction inherited from the program artefact, which asked for both a pre-CSV filter and a live exclusion bucket: applied at one point those are mutually exclusive. Inserting `_filter_to_confluent` immediately after the `population` snapshot gives both — `population` keeps pre-filter data so the bucket stays live and countable, while CSV and chart output downstream is filtered.

Appending `excluded_no_key_level` last in `_population_cuts` keeps the three existing bucket counts byte-identical against the current regression suite (no re-baselining), and makes a signal that is both unaligned and non-confluent land in `excluded_unaligned` by the existing earliest-wins `elif` chain — the same precedence discipline as the shipped REQ-40.3 rule.

Decisions for `sdd-design` to formalise as ADRs: KeyLevel-as-normalising-dataclass; geometric overlap with no tolerance parameter; confluence-as-validity-gate (a product decision, recorded not re-litigated); `origin_index` = provably-knowable index; the `_population_cuts` return-shape judgement call.

## Affected Areas

| Area | Impact | Description |
|---|---|---|
| `detector/core/key_level.py` | New | `KeyLevel` frozen dataclass (SEAM-01) |
| `detector/primitives/fvg.py` | Modified | `to_key_levels` adapter (SEAM-02) |
| `detector/alignment/htf_ltf.py` | Modified | `key_level` field + confluence determination |
| `detector/cli.py` | Modified | HTF FVG detection in `_detect_all`; `_filter_to_confluent` |
| `detector/backtest/simulate.py` | Modified | 8th bucket in `_population_cuts` |
| `detector/backtest/metrics.py` | Modified | `ReconciliationReport.excluded_no_key_level` |
| `detector/viz/trades_table.py` | Modified | New reconciliation line |
| `openspec/specs/detector/spec.md` | Modified | REQ-45/30/40 destructive sync |
| `detector/tests/` (~7-8 files) | Modified/New | Fitness functions above |

## Risks

| Risk | Likelihood | Mitigation |
|---|---|---|
| REQ-45's signed byte-compat guarantee is reopened | High (certain) | Re-anchor absolute → differential: "identical to the equivalent run differing only by `--backtest`". Strengthening, not weakening — the absolute anchor is permanently unverifiable once gating runs on every run; the differential one stays testable forever. Destructive sync per `sdd-archive` §4. |
| HTF FVG detection is new surface in `_detect_all` | Medium | Compute-only; no rendering, no `--types` change. Confirmed at design. |
| `_population_cuts` returns a 5-tuple of 4 adjacent ints — positional swap hazard | Medium | Flagged as a design-phase judgement call (named fields vs. tuple), not a blocker. Per-signal exclusive-membership test catches a swap regardless. |
| "Stage 4" is ambiguous — REQ-40 already numbers `excluded_duplicate` as stage 4 | Medium | `sdd-spec` must name the new bucket by position in `_population_cuts`, not by a global stage number. |
| Gate silently regresses if a refactor moves the CSV filter ahead of the `population` snapshot | Low | Cross-artefact reconciliation test + REQ-42.1 confluence scenario both fail loudly. |
| Confluence discriminates too weakly or too harshly on real data | Medium | Measured on the H4→M15 validation run; `excluded_no_key_level` count is the observable. A near-zero or near-total count is a signal to revisit, not a silent pass. |

## Rollback Plan

Additive except for one behavioural insertion, so rollback is staged and partial rollback is safe:

1. **Behaviour** — delete the `_filter_to_confluent` call from `cli.py` (one line). `detections.csv` and `overlay.png` immediately return to today's unfiltered content.
2. **Reporting** — remove the `excluded_no_key_level` branch from `_population_cuts`, the `ReconciliationReport` field, and the `viz/trades_table.py` line. The other seven buckets are untouched by construction, so the REQ-40.1 sum invariant re-closes at seven with no re-baselining.
3. **Spec** — restore REQ-45.3/REQ-30/REQ-40.1 from git; drop `REQ-30.7`/`REQ-40.5`.
4. **Dormant, safe to leave** — `core/key_level.py`, the `to_key_levels` adapter, the HTF FVG detection call, and `AlignedSignal.key_level` are pure computation with no output effect. They may stay in place after steps 1-3 without changing any artefact byte, which is what makes partial rollback viable.

**Validation**: re-run the H4→M15 pair with and without `--backtest`; `detections.csv`, `overlay.png`, and `metrics_summary.txt` must match the pre-change outputs byte-for-byte, and the full suite plus `lint-imports` must pass.

**Unrecoverable data**: none. The detector is read-only over MT5 CSV exports and writes only regenerable artefacts.

## Dependencies

None. No new runtime or dev dependency; no upstream publication (`spec_source: internal`).

## Success Criteria

- [ ] A `--backtest` run on the H4→M15 real pair produces `detections.csv` in which every Model-1 row has a `key_level` whose `[top, bottom]` overlaps its HTF purge wick extreme, with `origin_index < purge_index` — verified programmatically, not by eye.
- [ ] `metrics_summary.txt` shows a non-zero `no key level:` line, and `trades_opened + sum(8 exclusion buckets) == signals_considered` holds exactly.
- [ ] Every signal in a fixed mixed population belongs to exactly one bucket or `trades_opened` — never zero, never two — including one unaligned+non-confluent signal (lands in `excluded_unaligned`) and one confluent signal that opens.
- [ ] For a run without `--backtest`, `detections.csv` differs from today's output ONLY by removal of non-confluent Model-1 rows: the 7-column header is byte-identical and every surviving row is byte-identical.
- [ ] Signals tagged `unaligned` or `insufficient_htf_data` appear in `detections.csv` exactly as they do today — count and bytes unchanged.
- [ ] Two-sided `origin_index` boundary test passes: the KeyLevel is present at `up_to(origin_index + 1)` and absent at `up_to(origin_index)`.
- [ ] Two FVGs differing only in `fill_status`/`fill_index` produce identical `KeyLevel`s.
- [ ] `lint-imports` passes and a fitness test asserts `alignment/htf_ltf.py` imports `core.key_level` and no detector module.

## Sizing Note

The code diff is genuinely M-sized: one small new module, one adapter, one field, one detection call, one filter function, one `elif` branch. What holds this at L is (a) three MODIFIED signed requirements under destructive-sync rules and (b) the walking-skeleton obligation to establish SEAM-01/SEAM-02 for two downstream sub-changes. Stated explicitly so the small diff does not read as a triage inconsistency.

## Caveats from Exploration

None — exploration returned `ready_for_proposal: yes` with zero open questions; both product questions (filter scope, source-attribution timing) were resolved directly by the user.
