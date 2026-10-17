# Design: Dukascopy Backtest Readiness

**Triage**: L  
**Spec**: V2, signed  
**Architecture impact**: modifying

## Architecture Overview

Preserve the one-way pipeline `core → ingestion → primitives → composite|entries → alignment → backtest → viz`. Correct population and fill semantics in `backtest`, render them in `viz`, and keep provider orchestration outside production. One concrete research command validates the retained two-pair corpus, invokes production pure functions, stages deterministic evidence, and atomically publishes the complete directory.

**Pattern**: existing pure-function pipeline plus the research-only seam; ADR-01 governs the boundary.

## Binding File Changes

| Path | Action | Purpose |
|---|---|---|
| `detector/backtest/population.py` | Modify | Restore the signed nine-bucket precedence. |
| `detector/backtest/simulate.py` | Modify | Resolve adverse fill-candle SL before later exits. |
| `detector/viz/trades_table.py` | Modify | Publish distinct no-retest outcomes. |
| `detector/tests/test_backtest_{population,simulate,metrics}.py` | Modify | Pin taxonomy, fill, partial, and reconciliation rules. |
| `detector/tests/test_cli_backtest_e2e.py` | Modify | Pin public labels and equality. |
| `research/dukascopy_eurusd_gbpusd/seam.py` | Modify | Return canonical trades and reconciliation. |
| `research/dukascopy_eurusd_gbpusd/backtest.py` | Create | Validate, run, serialize, and atomically publish evidence. |
| `research/dukascopy_eurusd_gbpusd/tests/test_backtest.py` | Create | Cover command, replay, rejection, and publication failures. |
| `openspec/explore/dukascopy-canonical-backtest-receipt-2026-09-25.md` | Create | Preserve the official run and replay comparison. |

## Flow Changes

| Flow | Action | REQ-IDs | Verification target |
|---|---|---|---|
| Canonical backtest reporting | Modify | REQ-30, 33, 37, 40, 68 | detector unit tests plus CLI E2E |
| Produce validated two-pair evidence | Create | REQ-01.1, .3, .4 | research command integration test |
| Replay canonical evidence | Create | REQ-01.2 | two-directory byte replay test |

## Architecture Touchpoints

| Layer/component | Action | Why | Baseline fit |
|---|---|---|---|
| `backtest.population/simulate` | modify | Canonical classification and fill contract | aligns |
| `viz.trades_table` | modify | Correct public disclosure | aligns |
| research Dukascopy run seam | new | Provider orchestration and evidence publication | deviates; ADR-01 |

## Data Model

- `Stage6Population` / `ReconciliationReport`: nine exclusion buckets — `confirmed_no_retest`, `never_confirmed`, `excluded_no_key_level` (its own independent terminal category, unaffected by the split), `excluded_no_crt_range`, `excluded_unaligned`, `excluded_duplicate`, `excluded_kill_zone`, `excluded_rr_floor`, `excluded_never_filled` — plus `trades_opened`, reconcile exactly against `signals_considered`.
- `SeamInstrumentResult`: immutable `trades: tuple[Trade, ...]` and `reconciliation: ReconciliationReport`.
- `receipt.json`: schema version; ordered pairs; full applied configuration and costs; the CLI-supplied `expected_manifest_sha256` alongside the observed raw-file `manifest_sha256` (both are the SHA-256 of the `--manifest` file's raw bytes, verified equal before parsing) and the separate `canonical_manifest_sha256` (the parsed/canonicalized manifest's identity, kept for diagnostics only — never gates the run); source/derived hashes; reconciliation and metrics; each trade-file hash; and `replay.argv_template`.
- `replay.argv_template` is the canonical JSON string array containing literal executable/module/options, the literal `--expected-manifest-sha256` value, literal approved costs, and exactly three stable tokens: `${MANIFEST}`, `${DERIVED_ROOT}`, `${OUTPUT_DIR}`. Runtime paths, staging names, timestamps, and current working directory are forbidden. A researcher substitutes local paths; the expected manifest hash and the source hashes in the receipt identify the preserved inputs.

## Interface and Error Contract

Command: `uv run --project detector python -m research.dukascopy_eurusd_gbpusd.backtest --manifest <path> --expected-manifest-sha256 <hex64> --derived-root <path> --output-dir <path> --eurusd-cost <decimal> --gbpusd-cost <decimal>`.

Costs are required and non-negative; `--expected-manifest-sha256` is required and must be a 64-character hex SHA-256 digest — this is the mandatory manifest-identity check (EXT-01): the command hashes the `--manifest` file's raw bytes (SHA-256, before parsing) and rejects any mismatch, before reading a single derived file, simulating, or publishing. The parsed manifest's separate canonical identity (`manifest_sha256()` over the parsed/re-serialized form) is recorded in the receipt as `canonical_manifest_sha256` for diagnostics but never gates the run — two byte-for-byte distinct manifest files can carry the same canonical identity, and only the raw file the researcher was handed is what `--expected-manifest-sha256` authenticates. Argument errors — including an absent or malformed `--expected-manifest-sha256` — exit 2; validation errors — including a well-formed but mismatched `--expected-manifest-sha256` — execution, destination, or publication errors print `error: <reason>` and exit 1; success exits 0. Profitability never affects status.

The final output path MUST be absent before work begins; an existing file or directory, empty or populated, is left untouched and rejected. The command creates a unique staging directory beside the final path, writes both ordered trade files and the receipt, verifies hashes and required members, then renames the staging directory to the absent final path in one same-filesystem operation. It never renames individual evidence files. Any pre-commit failure removes staging. If the directory rename fails, the command reports failure, removes staging when still owned, and never copies or merges; the final path remains absent unless another process created it, which is reported and never modified. Successful rename is the sole completion point.

## Architecture Decisions

### ADR-01: Research owns orchestration and atomic evidence

**Status**: Proposed. **Context**: provider validation and two-pair evidence must be reproducible without reversing production dependencies or exposing partial results. **Decision**: keep one command under `research/`; use a path-tokenized argv template and same-parent staged-directory rename. **Consequences**: receipts replay across machines and completed directories are indivisible; callers need a new absent destination and publication requires one filesystem. **Rejected**: production CLI invocations cannot enforce the frozen corpus atomically; per-file renames expose mixed evidence; copying over an existing directory destroys provenance.

### ADR-02: Fill candle is adverse-only

**Status**: Proposed. **Decision**: a strict pre-entry opening beyond SL is exempt; otherwise inclusive SL touch is an immediate loss and wins any TP/partial tie. Normal exits start at `fill_index + 1`. **Consequence**: favourable intrabar ordering is never invented. **Rejected**: evaluating all fill-candle exits credits unknowable order.

## Test Derivation

| Matrix rows | Signed scenarios | Level / target |
|---|---|---|
| `REPRO-01`, `REPRO-03` | REQ-01.1, .4 | integration: synthetic two-pair run, including unprofitable result |
| `REPRO-04` | REQ-01.2 | integration: substitute different local paths into the template; compare all bytes |
| `REPRO-02` | REQ-01.3 | integration: invalid source, existing destination, run failure, and injected rename failure leave no newly completed evidence |
| `DETECTOR-01`, `DETECTOR-03` | REQ-30.1–.6; REQ-40.1–.7 | unit + CLI E2E: taxonomy, precedence, labels, equality |
| `DETECTOR-02`, `DETECTOR-04` | REQ-33.1–.5; REQ-37.1–.6; REQ-68.1–.6 | table-driven unit: bullish/bearish equality, gap, tie, partial, zero-partial, open trade |

## Fitness Functions

- `lint-imports`: production packages cannot import `research`.
- Reconciliation: `trades_opened + sum(9 exclusions) == signals_considered`.
- Receipt schema rejects runtime paths; replay compares receipt and trade bytes.
- Publication tests prove no per-file final writes and no mutation of an existing destination.

## Migration, Rollout, Performance

Migrate report fields and literals together; no database or feature flag. Verify synthetically, then run once and replay against approved external inputs before preserving the Markdown receipt. Pair execution remains sequential and O(candles + candidates), with staging bounded to three files.

## Architecture Impact

**Architecture impact**: modifying.  
**Rationale**: canonical `backtest`/`viz` contracts change and the material research run seam must be added to the baseline; production dependency direction remains intact.

## External Assumptions (`external_assumptions[]`)

| ID | Assumption | Status | Settlement |
|---|---|---|---|
| EXT-01 | Retained manifest's raw file SHA-256 is `e3c2caafb0a181a167a79d514fc9542886634643f4a543b3fbbd9367c75b745c`. | enforced | Passed by the human as the required `--expected-manifest-sha256`; the command hashes the `--manifest` file's raw bytes and rejects any mismatch before parsing, reading a derived file, simulating, or publishing — no longer a documentation-only assumption. |
| EXT-02 | Six retained derived files match the manifest; the manifest may also declare additional non-CSV provenance entries (e.g. the retained exclusion-gap-ledger hash). | doc-verified | Hash every one of the six required derived CSVs before simulation; reject any manifest missing a required CSV or declaring an additional, undeclared derived CSV, while permitting additional non-CSV `output_hashes` entries. |
| EXT-03 | Approved pair costs are decision-appropriate. | assumed | Human supplies values before the official run. |
| EXT-04 | Final and staging paths share a filesystem whose directory rename is atomic. | build-preflight | Attempt the single rename; failure yields no completed evidence. |

## Questions and Execution Notes

**Blocking questions**: None.  
**Executor-local notes**: reuse `runner.serialization.canonical_json`; do not add a runner or serializer abstraction.  
**Build preflights**: confirm external files are readable and obtain approved costs. These block only the official run. No Key-Level expansion, shadow/demo execution, or profitability gate.
