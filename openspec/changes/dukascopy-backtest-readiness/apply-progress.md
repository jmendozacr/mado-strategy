# Apply Progress: Dukascopy Backtest Readiness

**Scope**: `skeleton` + `happy-path` + `edge-case`
**Status**: S-000, S-001, S-002, S-003 all complete, including the official approved-cost run and replay (see "S-003 adjustment 2" and "Official approved-cost run" below).

## S-000

Implemented the walking skeleton: a concrete research command that runs the
canonical two-pair Dukascopy backtest end to end and publishes deterministic
evidence.

Changes:

- `research/dukascopy_eurusd_gbpusd/seam.py`: `SeamInstrumentResult` now
  carries `trades: tuple[Trade, ...]` and `reconciliation: ReconciliationReport`
  (previously computed by `run_instrument_seam` for the cardinality check
  only, then discarded).
- `research/dukascopy_eurusd_gbpusd/backtest.py` (new): argparse command
  (`--manifest`, `--derived-root`, `--output-dir`, `--eurusd-cost`,
  `--gbpusd-cost`); reads the six pre-aggregated derived CSVs
  (`{instrument}_{M15|H4|D1}.csv`) per the naming convention established in
  `openspec/explore/dukascopy-derived-manifest-receipt-2026-09-22.md`; runs
  EURUSD then GBPUSD sequentially through `run_instrument_seam`; writes one
  `receipt.json` plus one `{instrument}_trades.json` per pair via
  `runner.serialization.canonical_json`; stages all three files in a sibling
  temp directory and publishes with a single `os.replace` to the (must-be-
  absent) output directory. `replay.argv_template` is a literal argv array
  with only `${MANIFEST}`, `${DERIVED_ROOT}`, `${OUTPUT_DIR}` as path tokens;
  costs are baked in literally.
- `research/dukascopy_eurusd_gbpusd/tests/test_backtest.py` (new): synthetic
  flat-series two-pair command test (happy path + ordered evidence), an
  argv-template portability check, an unprofitable-trades-still-succeed test
  (REQ-01.4, via a monkeypatched `run_instrument_seam`), and an
  existing-destination rejection test.

Deferred to later slices per `slices.md`'s Build Order (not touched here):
manifest/derived hash **validation** against expected values, exhaustive
run/rename-failure injection, and the official approved-cost run + receipt
(all S-003); the nine-bucket reconciliation taxonomy fix (S-001); adverse
fill-candle handling (S-002).

## Verification

- `uv run --project detector pytest research/ -q` → 182 passed.
- `cd detector && uv run lint-imports` → 11/11 contracts kept.
- Full `cd detector && uv run pytest -q` (detector + research): **1046 passed**.

## S-001

Fixed the population/reconciliation taxonomy: a signal with `retest_index is
None` was previously folded into one `excluded_never_confirmed` bucket
regardless of whether it had actually reached confirmation. `entries/model1.py`
already distinguishes this via `Model1Signal.status` (`DetectionStatus`):
`INVALIDATED` means the anchor's protected extreme was breached before any
confirming close-beyond-body ever happened (genuinely never confirmed);
`PENDING` means the anchor's body WAS engulfed (confirmed) but the retest
sequence never completed within the lookback window. `CONFIRMED` always
carries a `retest_index` by construction, so it never reaches this branch.

Changes:

- `detector/backtest/population.py`: `_population_cuts` now branches on
  `signal.status` inside the `retest_index is None` case — `INVALIDATED` →
  `excluded_never_confirmed` (unchanged bucket), anything else (`PENDING`) →
  new `excluded_confirmed_no_retest` bucket. `Stage6Population` and the
  internal `_PopulationCuts` carry the new field.
- `detector/backtest/simulate.py`: `ReconciliationReport` carries the same
  new field, threaded from `population.excluded_confirmed_no_retest`.
- Both new dataclass fields default to `0` and were added last in each class
  body — every other exclusion bucket, its name, and the "nine-buckets-plus-
  trades_opened" precedence order for signals that DO carry a retest_index
  are unchanged. The default keeps the many existing `ReconciliationReport(...)`
  /`Stage6Population(...)` fixtures elsewhere in the suite (adapter, direction
  evaluation, causal, runner-pipeline, property tests) constructing these
  dataclasses without the new field working unchanged — production code
  always passes the real computed value explicitly, never relies on the
  default.
- `detector/viz/trades_table.py`: `write_metrics_summary`'s reconciliation
  block gained one literal line, `confirmed, no retest: {n}`, placed right
  before the existing `never confirmed: {n}` line.
- Tests updated to pin the corrected taxonomy: `test_backtest_population.py`
  (new split test + reconciliation-tuple assertions extended),
  `test_backtest_metrics.py` (`_ZERO_RECONCILIATION` + the reconciliation-sum
  invariant test extended to mix in both new-bucket cases),
  `test_cli_backtest_e2e.py` (one new assertion line). Also fixed
  `test_backtest_simulate.py`'s `test_retest_index_none_excludes_regardless_of_status`
  (renamed to `..._by_status_never_confirmed_vs_confirmed_no_retest`), which
  pinned the OLD single-bucket behavior under a docstring that already
  mis-cited REQ-30.3 — see "Decisions requiring review" below.

Deferred per Build Order (not touched): fill-candle SL/TP/partial semantics
(S-002); hash validation, replay, official run (S-003).

### Verification (focused, no network/build)

- `uv run --project detector pytest detector/tests/test_backtest_population.py detector/tests/test_backtest_metrics.py detector/tests/test_backtest_simulate.py detector/tests/test_cli_backtest_e2e.py -q` → **69 passed**.
- `uv run --project detector pytest detector/tests/test_direction_evaluation.py detector/tests/test_adapter_trade_join.py detector/tests/test_adapter_bundle.py detector/tests/test_adapter_build.py detector/tests/test_runner_instrument_pipeline.py detector/tests/test_causal_integration.py detector/tests/property/test_adapter_properties.py -q` (every other file constructing `ReconciliationReport`/`Stage6Population`) → **104 passed**.
- `uv run --project detector pytest detector/tests/property/test_no_lookahead.py -q` (reads `excluded_never_confirmed` under randomized windowing) → **21 passed**.
- No full/unrelated suite run, per instruction.

### Reconciliation after S-001

`Stage6Population`/`ReconciliationReport` now carry 9 exclusion buckets:
`excluded_no_crt_range`, `excluded_unaligned`, `excluded_confirmed_no_retest`
(new), `excluded_never_confirmed`, `excluded_no_key_level`,
`excluded_duplicate`, `excluded_kill_zone`, `excluded_rr_floor`,
`excluded_never_filled`. `trades_opened + sum(all 9) == signals_considered`
holds exactly (proved for a mixed population in
`test_reconciliation_buckets_plus_trades_opened_sum_to_signals_considered`);
every signal lands in exactly one bucket, per REQ-40.1/40.5/40.6.

### Decisions requiring review

- **Resolved** (human-confirmed): REQ-40's precedence-order sentence and
  design.md's data-model line originally omitted `excluded_no_key_level`
  from the enumerated bucket list, reading as if there were only 8 total.
  The human confirmed `excluded_no_key_level` is retained as its own
  independent terminal category — reconciliation has **nine** exclusion
  buckets, not eight; no requirement scope changed, only the enumerated
  count and bucket list. `specs/detector/spec.md` (REQ-40, REQ-40.1),
  `design.md` (Data Model, Fitness Functions), and `slices.md` (S-001
  acceptance and task) were corrected accordingly — documentation-only,
  no code or tests touched, since the implementation already reconciled
  nine buckets.
- New field names use the codebase's existing `excluded_` prefix convention
  (`excluded_confirmed_no_retest`) rather than the bare `confirmed_no_retest`
  spelling used in the spec's prose, matching every other bucket's Python
  identifier. If the spec intended the bare spelling as a literal contract
  (e.g. for external consumers), it needs to be renamed.
- `test_backtest_simulate.py`'s stale test wasn't in slices.md's named task
  list but directly pinned the pre-fix (spec-contradicting) behavior; fixed
  it as in-scope for S-001 rather than leaving a falsified test in the suite.

## S-002

Fixed adverse fill-candle SL exposure (REQ-33.4/.5, REQ-37.3-.6, REQ-68.3):
the fill candle previously only ever evaluated ENTRY (via `_fill_pass`'s
unified sweep, `eligible_at=retest_index` — unchanged, already correct);
all SL/TP/partial exit evaluation began at `fill_index + 1`, so a fill
candle whose own range also reached SL was silently ignored and the trade
could later resolve favourably from an intrabar sequence that was never
actually knowable.

Changes:

- `detector/backtest/simulate.py`: new `_fill_candle_immediate_loss(candidate,
  fill_index, candles, trading_cost_price)` evaluates ONLY the fill candle's
  own range for adverse SL exposure (inclusive `low<=stop`/`high>=stop`
  by direction). Returns a resolved immediate-loss `Trade` (entry_index ==
  exit_index == fill_index, exit_price == stop_loss exactly, single-leg —
  partial fields stay None/False) when SL is touched and the STRICT
  pre-entry-gap exemption does not apply; `ambiguous_bar` is set when the
  same candle also reaches TP (REQ-33.4), even though TP is never credited.
  Returns `None` when SL isn't touched, or when it's exempted (REQ-37.5)
  or moot (touched only via a favourable level, never credited per
  REQ-37.4 — the caller's unchanged `fill_index + 1` sweep never even
  inspects this candle, so that non-crediting falls out for free).
  The exemption reuses the existing `_exit_gap_beyond` helper (already used
  for post-fill gap-through pricing) with `chosen_is_stop=True` — it is
  the exact "open strictly beyond SL" test REQ-37.5/.6 need, so no new gap
  predicate was written.
- `_resolve_exits` now partitions `filled` candidates into those the fill
  candle itself immediately resolves (skip the sweep entirely) and the
  rest (`pending`), which go through the ORIGINAL, unmodified
  `fill_index + 1` sweep + `_resolve_trade`/`_resolve_single_leg` machinery
  — post-fill partial/SL/TP precedence, the unmoved-SL/TP remaining leg,
  and `partial_fraction=0.0`'s single-leg collapse are untouched code paths,
  not re-verified logic.
- No change to `_fill_pass` (fill search already started at `retest_index`,
  REQ-37.1/.2 — confirmed unaffected, not a bug this slice needed to fix)
  and no change to `Stage6Population`/`ReconciliationReport`/the S-001
  nine-bucket taxonomy (`_resolve_exits`'s new partition only reshapes how
  a FILLED candidate's own `Trade` gets resolved; `excluded_never_filled`
  and every other bucket are computed exactly as before, upstream of this
  function).
- Tests: 12 new tests in `test_backtest_simulate.py`, bullish+bearish pairs
  for — SL touch in fill, SL exactly-at-extreme equality, SL+TP tie
  (ambiguous), SL+partial tie (single-leg), strict pre-entry gap exemption,
  open-exactly-at-SL (exemption boundary, does NOT apply), TP/partial
  touched without SL (never credited) — plus one parametrized
  invalidated-vs-pending uniformity test, one bearish open-trade regression,
  and one bearish `partial_fraction=0.0` regression. Also fixed
  `test_sl_tp_sweep_excludes_the_fill_candle_itself` (renamed
  `test_fill_candle_reaching_sl_now_resolves_there_not_at_fill_plus_one`),
  which pinned the exact pre-fix behavior REQ-37's own preamble names as
  the defect being corrected — same situation as S-001's stale test, fixed
  as in-scope rather than left falsified.

Deferred per Build Order (not touched): hash validation, exhaustive
run/rename-failure injection, and the official approved-cost run (S-003).

### Verification (focused, no network/build)

- `uv run --project detector pytest detector/tests/test_backtest_simulate.py -q` → **48 passed** (36 pre-existing + 12 new, RED-then-GREEN confirmed: all 12 failed against pre-fix code, then passed after the fix).
- `uv run --project detector pytest detector/tests/test_backtest_population.py detector/tests/test_backtest_metrics.py detector/tests/test_cli_backtest_e2e.py detector/tests/test_backtest_levels.py -q` → **51 passed**. Every CLI E2E fixture's fill candle was hand-verified (and empirically confirmed passing) to never touch SL, so none of those hardcoded outcome/R-multiple assertions needed changing.
- `uv run --project detector pytest detector/tests/property/test_no_lookahead.py -q` → **21 passed** (windowed-vs-full-series fill/exit consistency, including the new immediate-loss path).
- `uv run --project detector pytest detector/tests/test_direction_evaluation.py detector/tests/test_adapter_trade_join.py detector/tests/test_adapter_bundle.py detector/tests/test_adapter_build.py detector/tests/test_runner_instrument_pipeline.py detector/tests/test_causal_integration.py detector/tests/property/test_adapter_properties.py -q` → **104 passed** (S-001 blast-radius set, re-confirmed untouched by this slice).
- `cd detector && uv run lint-imports` → 11/11 contracts kept.
- No full/unrelated suite run, per instruction.

### REQ-33/37/68 scenario coverage

| REQ | Scenario | Covered by |
|---|---|---|
| 37.1/.2 | Fill search starts at `retest_index`, uniform across CONFIRMED/INVALIDATED/PENDING | Pre-existing tests (unaffected, confirmed by inspection — not re-implemented) |
| 37.3 | Fill candle SL touch (inclusive) → immediate loss, incl. equality at the extreme | `test_fill_candle_adverse_sl_touch_{bullish,bearish}_...`, `test_fill_candle_sl_equality_{bullish,bearish}_...`, `test_fill_candle_reaching_sl_now_resolves_there_not_at_fill_plus_one` |
| 37.4 | TP/partial touched on fill candle without SL → never credited, evaluation resumes at fill_index+1 | `test_fill_candle_tp_without_sl_bullish_is_never_credited`, `test_fill_candle_partial_without_sl_bullish_is_never_credited`, `test_fill_candle_tp_or_partial_without_sl_bearish_is_never_credited` |
| 37.5 | Strict pre-entry gap beyond SL → exempt, no loss inferred | `test_fill_candle_strict_pre_entry_gap_beyond_sl_{bullish,bearish}_infers_no_loss` |
| 37.6 | Open exactly at SL → exemption does NOT apply, immediate loss | `test_fill_candle_open_exactly_at_sl_{bullish,bearish}_the_exemption_does_not_apply` |
| 33.1/.3 (post-fill, regression) | Same-candle SL+TP after the fill candle | Pre-existing tests, re-run green |
| 33.4 | Fill candle SL+TP → loss at SL, `ambiguous_bar=True` | `test_fill_candle_sl_and_tp_{bullish,bearish}_loses_at_sl_and_flags_ambiguous` |
| 33.5/68.3 | Fill candle SL+partial → single-leg loss, no partial recorded | `test_fill_candle_sl_and_partial_{bullish,bearish}_is_a_single_leg_loss` |
| 68.1/.2/.4-.6 (post-fill, regression) | Partial-before-SL, unmoved remaining SL/TP, gap-through partial, `partial_fraction=0.0`, no-eligible-exit stays open | Pre-existing bullish tests, re-run green; bearish added for zero-partial and open-trade (`test_partial_fraction_zero_reproduces_single_leg_output_bearish`, `test_confirmed_signal_fills_and_resolves_open_bearish`) |
| 37.2 (extended) | Fill-candle adverse-SL applies uniformly to INVALIDATED/PENDING, not just CONFIRMED | `test_fill_candle_adverse_sl_applies_uniformly_to_invalidated_and_pending` |

### Confirmations

- S-003 (hash validation, exhaustive failure injection, official approved-cost
  run + receipt) remains fully pending — untouched.
- `research/dukascopy_eurusd_gbpusd/backtest.py` untouched — no incompatibility
  arose (it consumes `SeamInstrumentResult.trades`/`.reconciliation` structurally,
  not any specific resolution-timing detail this slice changed).
- No detection-rule, Key Level, broker, shadow, or demo semantics touched.
- No commits made.

### Decisions requiring review

- None new for S-002 — REQ-33/37/68's fill-candle semantics matched the
  existing code's structure cleanly (no contradiction found requiring a
  stop): `_fill_pass`'s `retest_index` eligibility was already correct,
  and `_exit_gap_beyond` already existed with exactly the comparison
  S-002's exemption needed.

## S-003

Fixed REQ-01.2/.3: the command now validates every input before simulating
anything, and publication is hardened against the concurrent-writer race
the prior structure left open. The official approved-cost run remains
untouched — see "Blocked" below.

### Validation (before simulating; `research/dukascopy_eurusd_gbpusd/backtest.py`)

- `_validate_manifest_identity(manifest)`: the manifest's own declared
  `output_hashes` key set must equal exactly the six expected artifact
  names (`{EURUSD,GBPUSD}_{M15,H4,D1}.csv`) — not a subset, not extras.
  Runs before any filesystem access under `--derived-root`.
- `_load_and_validate_derived_files(derived_root, manifest)`: for each of
  the six expected files, in one pass — missing-file coverage check
  up front (names every missing file, not just the first); then per file,
  SHA-256 against `manifest.output_hashes[name]`; then parses and rejects
  zero data rows. Returns the parsed bars AND the hashes together, so nothing
  is read from disk twice between validation and simulation.
- Negative-cost rejection and the argparse-2-vs-BacktestError-1 exit
  distinction were already correct from S-000; both now have dedicated
  regression tests (`test_backtest_command_rejects_negative_cost`,
  `test_backtest_command_argparse_missing_required_flag_exits_2`).
- `_run` now has a strict two-phase shape: full validation (costs,
  destination absence, manifest identity, derived coverage/hash/rows) all
  completes before the per-pair `run_instrument_seam` loop starts — a
  GBPUSD-side validation failure can no longer happen after EURUSD has
  already been simulated.

### Publication (`_publish`)

- `_verify_staging_members(staging, members)`: one discrete, named gate
  right before the rename — lists the staging directory's actual members
  and compares both the member SET and every file's bytes against what the
  receipt already claims, catching any drift between what was written and
  what was verified (not just each file's own write echoing back correctly).
- Added an explicit `output_dir.exists()` recheck immediately before
  `os.replace`, closing the check-then-act window between the initial
  absence check and the rename — a destination created concurrently by
  another process is refused there even on a filesystem where a rename
  over an empty existing directory would otherwise silently succeed
  (`os.replace` itself already refuses a non-empty one; the explicit
  recheck is the platform-independent guarantee, not a Windows-specific
  behavior this repo happens to run on).
- Single `os.replace(staging, output_dir)` — the whole directory, never a
  per-file rename, copy, or merge. On any exception (write, verify, or
  rename), only the owned `staging` directory is removed; `output_dir` is
  never touched. Confirmed by test, not just by reading: an injected
  concurrent-writer scenario proves the destination it created survives
  untouched.

### Tests (`research/dukascopy_eurusd_gbpusd/tests/test_backtest.py`)

10 new tests, plus fixtures reworked so every existing S-000 test now
carries the derived files' REAL sha256 hashes in its manifest (previously a
single placeholder hash for one of six files — would have failed the new
identity/hash checks otherwise). RED-then-GREEN verified for the four least
obvious checks by temporarily removing each one, confirming the
corresponding test alone failed, then restoring — not just written and
trusted:

| Test | Proves |
|---|---|
| `test_backtest_command_rejects_derived_file_hash_mismatch` | Tampered derived file content → rejected (RED-confirmed) |
| `test_backtest_command_rejects_manifest_declaring_an_extra_artifact` | Manifest identity check catches an untracked 7th entry the per-file hash loop alone would silently ignore (RED-confirmed) |
| `test_backtest_command_rejects_incomplete_manifest_output_hashes` | Manifest declaring fewer than six artifacts |
| `test_backtest_command_rejects_incomplete_derived_coverage` | A missing derived file on disk |
| `test_backtest_command_rejects_empty_derived_file` | Zero-data-row derived file → rejected (RED-confirmed) |
| `test_backtest_command_rejects_negative_cost` | Negative cost, either pair |
| `test_backtest_command_argparse_missing_required_flag_exits_2` | argparse's own exit 2, distinct from `BacktestError`'s exit 1 |
| `test_backtest_command_rejects_existing_destination` | Pre-existing S-000 test, unchanged assertions |
| `test_backtest_command_execution_failure_leaves_no_evidence` | GBPUSD-side `run_instrument_seam` failure after EURUSD already succeeded → no output, no staging leftover |
| `test_backtest_command_write_failure_leaves_no_evidence` | Injected failure on the 2nd staged file write → cleanup, no evidence |
| `test_backtest_command_rename_failure_leaves_no_evidence` | Injected `os.replace` failure → cleanup, no evidence |
| `test_backtest_command_rechecks_destination_immediately_before_rename` | A destination created concurrently, staged right up to the rename, is never touched (RED-confirmed) |
| `test_backtest_command_replay_is_byte_identical_across_directories` | Two independent local directories, same manifest/derived content, different paths → byte-identical `receipt.json` and both `*_trades.json` |

Every "leaves no evidence" test asserts both `not output_dir.exists()` AND
no leftover `.staging-*` directory beside it — the concrete form of "no
mixed evidence."

### Verification (focused, no network/build)

- `uv run --project detector pytest research/ -q` → **194 passed**.
- `uv run --project detector pytest detector/tests/test_backtest_simulate.py detector/tests/test_backtest_population.py detector/tests/test_backtest_metrics.py detector/tests/test_cli_backtest_e2e.py -q` → **87 passed** (S-001/S-002 unaffected — nothing in `detector/` was touched this slice).
- `cd detector && uv run lint-imports` → 11/11 contracts kept.
- No full/unrelated suite run, no network, no commits.

### Official approved-cost run — complete

Executed with the human-approved all-in costs (EURUSD `0.00011`, GBPUSD
`0.00015`) against the retained external run at
`D:\Josué\Documents\dukascopy-run-2026-09-22`, then replayed into an
independent output directory with only `--output-dir` changed. Both runs
exited `0`; `receipt.json`, `DUKASCOPY_EURUSD_trades.json`, and
`DUKASCOPY_GBPUSD_trades.json` are byte-identical (SHA-256-verified) between
the two directories. Full hashes, costs, and per-instrument summary are
preserved at
`openspec/explore/dukascopy-canonical-backtest-receipt-2026-09-25.md`.

```
uv run --project detector python -m research.dukascopy_eurusd_gbpusd.backtest \
  --manifest "D:\Josué\Documents\dukascopy-run-2026-09-22\run-manifest.json" \
  --expected-manifest-sha256 e3c2caafb0a181a167a79d514fc9542886634643f4a543b3fbbd9367c75b745c \
  --derived-root "D:\Josué\Documents\dukascopy-run-2026-09-22" \
  --output-dir <canonical-backtest-official-or-replay> \
  --eurusd-cost 0.00011 --gbpusd-cost 0.00015
```

The `--expected-manifest-sha256` value above is EXT-01's own retained value
(design.md) — the manifest file's raw-byte SHA-256, not chosen or invented
this turn. This run could not succeed before the "S-003 adjustment 2" fix
below: the CLI previously validated `--expected-manifest-sha256` against
the parsed/canonicalized manifest (`a89a2e01...`), which never equals the
documented raw-file hash (`e3c2caaf...`) for a pretty-printed manifest file.

### S-003 adjustment: mandatory `--expected-manifest-sha256`

**Resolved** (human-confirmed): the prior "Manifest identity/hash" reading
below was flagged, not assumed — the human then confirmed the command
must explicitly verify manifest identity against a caller-supplied hash,
not merely check the manifest's own internal completeness. Implemented:

- `build_parser()`: new required `--expected-manifest-sha256`, typed
  through `_sha256_hex` (a 64-hex-char format check) so an absent or
  malformed digest is an argparse error — exit 2, before any file I/O.
- `_run`: immediately after `deserialize_manifest`, computes
  `manifest_sha256(manifest)` (the exact function and canonical
  representation already used to populate the receipt since S-000 — no
  second serialization path introduced) and compares it to
  `args.expected_manifest_sha256`; a mismatch raises `BacktestError` —
  `error: ...`, exit 1 — before `_validate_manifest_identity`, before any
  derived file is read, before simulating, before publishing. The prior
  six-artifact `_validate_manifest_identity` check is unchanged and still
  runs right after — it catches a different failure mode (an incomplete or
  over-declared `output_hashes` set within an otherwise-identity-matched
  manifest) that the hash check alone cannot.
- `_build_receipt`/`_argv_template`: both now carry
  `expected_manifest_sha256` — as a new `"expected_manifest_sha256"` key in
  `receipt.json` (alongside the pre-existing observed `"manifest_sha256"`),
  and as a literal value (not a token) in `replay.argv_template`, right
  after `--manifest ${MANIFEST}`. No new path token was added — the three
  path tokens (`${MANIFEST}`, `${DERIVED_ROOT}`, `${OUTPUT_DIR}`) are
  unchanged.
- Tests: fixtures reworked again — `_write_manifest` now returns the
  manifest's own `manifest_sha256()` so every test can thread the CORRECT
  expected hash through `_run_args` (a 4th positional argument now,
  required). 4 new tests: correct-hash happy-path assertions folded into
  the existing publish/argv-template tests (both `receipt["manifest_sha256"]`
  and `receipt["expected_manifest_sha256"]` checked); a wrong-but-well-formed
  hash (`test_backtest_command_rejects_wrong_expected_manifest_sha256`,
  RED-confirmed); a malformed digest
  (`test_backtest_command_invalid_expected_manifest_sha256_format_exits_2`,
  RED-confirmed); an absent flag
  (`test_backtest_command_missing_expected_manifest_sha256_exits_2`); the
  replay test now asserts both directories' independently-derived expected
  hashes agree (identical content, different local paths) before using
  each to run its own invocation.

#### Verification (focused, no network/build)

- `uv run --project detector pytest research/dukascopy_eurusd_gbpusd/tests/test_backtest.py -q` → **19 passed** (was 16 before this adjustment).
- RED-then-GREEN verified for both new checks (wrong hash, malformed
  format) by temporarily removing each, confirming only the corresponding
  test failed, then restoring.
- `uv run --project detector pytest research/ -q` → **197 passed**.
- `cd detector && uv run lint-imports` → 11/11 contracts kept.
- No full/unrelated suite run, no network, no commits.

### S-003 adjustment 2: raw-file manifest hash + permissive non-CSV provenance

**Resolved** (human-approved correction): the "S-003 adjustment"
implementation above checked `--expected-manifest-sha256` against
`manifest_sha256()` — the SHA-256 of the *parsed and re-canonicalized*
manifest — not the raw bytes of the `--manifest` file. Since the retained
manifest file is pretty-printed JSON and `manifest_sha256()` re-serializes
as compact, key-sorted JSON, the two hashes differ for any real manifest
file; the officially documented raw-file hash (EXT-01,
`e3c2caaf...`) could never pass. Separately, the retained manifest declares
a legitimate 7th `output_hashes` entry (the exclusion-gap-ledger JSON hash),
which the prior exact-six-set check rejected outright.

- `_run` (`research/dukascopy_eurusd_gbpusd/backtest.py`): now reads
  `args.manifest.read_bytes()` and hashes those raw bytes with
  `hashlib.sha256` *before* parsing — compared directly against
  `args.expected_manifest_sha256`, still before any derived file is read,
  simulation, or publication. Only after that check passes is the manifest
  parsed (`deserialize_manifest`); the parsed form's `manifest_sha256()` is
  now computed separately as `canonical_manifest_sha256` and carried into
  the receipt for diagnostics — it never gates the run.
- `_validate_manifest_identity`: no longer requires the declared
  `output_hashes` key set to equal exactly the six expected derived CSVs.
  It now requires the six to be present (`missing` check, unchanged
  failure mode) and separately rejects only *additional* entries that are
  themselves derived CSVs (`name.endswith(".csv")` and not one of the six)
  — an additional non-CSV provenance entry (e.g. the gap-ledger hash) is
  permitted through unchanged.
- `_build_receipt`: gained `raw_manifest_sha256` and
  `canonical_manifest_sha256` parameters. `receipt.json`'s
  `"manifest_sha256"` field is now explicitly the raw-file hash (identical
  to `"expected_manifest_sha256"` by construction, once the identity check
  passes); a new `"canonical_manifest_sha256"` field carries the
  parsed/canonicalized identity separately. `"schema_version"` bumped
  `1` → `2` for the added field.
- Tests (`research/dukascopy_eurusd_gbpusd/tests/test_backtest.py`): the
  `_write_manifest` fixture helper now returns the manifest **file's** raw
  SHA-256 (previously returned `manifest_sha256(manifest)`, the canonical
  hash) — every existing test's `expected_hash` now threads the raw-file
  hash through `--expected-manifest-sha256`, matching the corrected CLI
  contract. 3 new tests, RED-then-GREEN verified against the pre-fix code:
  `test_backtest_command_rejects_reformatted_manifest_against_raw_hash`
  (a semantically-equivalent but differently-formatted manifest is rejected
  against the original raw hash — the direct regression test for the bug
  this slice fixes), `test_backtest_command_accepts_additional_non_csv_provenance_hash`
  (the retained gap-ledger-style 7th entry no longer fails identity),
  `test_backtest_command_receipt_distinguishes_raw_and_canonical_manifest_hash`
  (asserts `manifest_sha256` / `expected_manifest_sha256` equal the raw
  hash, `canonical_manifest_sha256` equals the independently-computed
  canonical hash, and the two differ for this manifest — proving they are
  genuinely distinct fields, not aliases). The pre-existing
  `test_backtest_command_rejects_manifest_declaring_an_extra_artifact` is
  unchanged in behavior (an extra **CSV** stays rejected) but its docstring
  now cross-references the new non-CSV-acceptance test.

#### Verification (focused, no network/build)

- `uv run --project detector pytest research/dukascopy_eurusd_gbpusd/tests/test_backtest.py -q` → **22 passed** (RED confirmed first: 7 failed against pre-fix code with `manifest identity mismatch`, all for the expected reason — raw vs. canonical hash — then GREEN after the fix).
- No full/unrelated suite run, no network, no build, no commits, per instruction.

Requirements were not changed: REQ-01.2/REQ-01.3 (`slices.md`) describe
"identical replay" and "invalid/incomplete evidence rejected pre-
simulation" abstractly and say nothing about raw-vs-canonical hash
semantics or an exact-six-only `output_hashes` set — both remain satisfied
by the corrected, more precisely-scoped validation. No spec change needed.

### Decisions requiring review

- The command still never reads the RAW source CSVs at `manifest.inputs[i]
  .source_path` (only the pre-aggregated derived CSVs under
  `--derived-root`) — unchanged from S-000. `manifest.inputs[i]
  .source_sha256` stays pure provenance metadata, carried into the receipt
  but not re-verified against a live file, since the command has no
  parameter pointing at where the multi-gigabyte raw 1-minute exports live
  on the machine running the replay (that's the whole reason
  `${DERIVED_ROOT}` exists as a portable token instead). If "identidad del
  manifest" was intended to mean re-hashing the raw source files, that
  would need a new `--source-root`-style parameter this slice did not add —
  flagging this explicitly rather than guessing.
