# Slices: Dukascopy Backtest Readiness

**Triage**: L · **Spec**: V2 signed · **Design**: modifying · **Total**: 4 (1 skeleton + 3 SPIDR)

## S-000: Produce minimal two-pair evidence

**Scope**: walking-skeleton · **Dimension**: — · **Covers**: REQ-01.1, REQ-01.4 · **Requires**: nothing · **Test layers**: research integration + unit

**Acceptance**: GIVEN valid synthetic EURUSD and GBPUSD inputs and non-negative costs, WHEN the research command runs to an absent destination, THEN it publishes ordered trades plus one receipt for both pairs with a portable `replay.argv_template`; an unprofitable result still exits successfully.

### Tasks
- [x] Add `research/dukascopy_eurusd_gbpusd/backtest.py`: concrete argparse command, sequential pair invocation, staged JSON publication.
- [x] Extend `research/dukascopy_eurusd_gbpusd/seam.py` to return canonical trades and reconciliation.
- [x] Write deterministic ordered receipt/trade JSON using existing `runner.serialization.canonical_json`, including a literal argv array with only `${MANIFEST}`, `${DERIVED_ROOT}`, and `${OUTPUT_DIR}` path tokens.
- [x] Add synthetic two-pair command test in `research/dukascopy_eurusd_gbpusd/tests/test_backtest.py`.

## S-001: Disclose every terminal signal outcome

**Scope**: happy-path · **Dimension**: R (Rule) · **Covers**: REQ-30.1–30.6, REQ-40.1–40.7 · **Requires**: none · **Test layers**: population, metrics, CLI E2E

**Acceptance**: GIVEN mixed signals, WHEN canonical population and summary run, THEN confirmed signals without retests appear only as `confirmed_no_retest`, never-confirmed signals remain distinct, and exactly one of nine exclusions (including `excluded_no_key_level` as its own independent terminal category) or an opened trade accounts for every considered signal.

### Tasks
- [x] Update `detector/backtest/population.py` and reconciliation model with signed precedence and nine buckets.
- [x] Update `detector/viz/trades_table.py` literal labels; retain `metrics.py` as the consumer.
- [x] Pin taxonomy/invariant in `test_backtest_population.py` and `test_backtest_metrics.py`; pin labels/equality in `test_cli_backtest_e2e.py`.

## S-002: Resolve adverse fill-candle exposure

**Scope**: happy-path · **Dimension**: R (Rule) · **Covers**: REQ-33.1–33.5, REQ-37.1–37.6, REQ-68.1–68.6 · **Requires**: S-001 · **Test layers**: simulation unit + metrics

**Acceptance**: GIVEN bullish or bearish filled candidates, WHEN the fill candle touches SL (including equality or a simultaneous favourable level), THEN it is an immediate disclosed SL loss; pre-entry opening beyond SL is exempt and later favourable exits begin next candle.

### Tasks
- [x] Amend `detector/backtest/simulate.py` with strict pre-entry-gap handling, inclusive adverse-only fill handling, and SL-first ambiguity accounting.
- [x] Preserve post-fill partial/SL/TP resolution and original levels for the remaining leg.
- [x] Add boundary, tie, gap, pending/invalidated, zero-partial, and open-trade cases to `test_backtest_simulate.py` and reconciliation checks.

## S-003: Reject altered sources and preserve replayable evidence

**Scope**: edge-case · **Dimension**: P (Path) · **Covers**: REQ-01.2, REQ-01.3 · **Requires**: S-000, S-002 · **Test layers**: command integration + import fitness

**Acceptance**: GIVEN an existing destination, bad source, mismatched `--expected-manifest-sha256`, run error, or final rename failure, WHEN the command runs, THEN it exits 1, never alters that destination, and leaves no mixed completed evidence; GIVEN a new absent destination and a correct `--expected-manifest-sha256`, THEN it publishes only by same-parent staging-directory rename and replays byte-identically after token substitution.

### Tasks
- [x] Validate manifest identity against a required `--expected-manifest-sha256` CLI argument (EXT-01), plus pair/timeframe coverage, derived hashes, rows, required costs, absent destination, and argparse exit distinctions (including the digest's own format) in `backtest.py`.
- [x] Create a unique sibling staging directory; verify all three members and hashes, then atomically rename the directory only. Remove owned staging on every pre-commit or rename failure; never copy, merge, or rename files individually.
- [x] Add invalid-source, wrong/malformed-`--expected-manifest-sha256`, existing-destination, injected run/rename-failure, no-mixed-evidence, and two-directory byte-replay tests in `research/dukascopy_eurusd_gbpusd/tests/test_backtest.py`; replay substitutes different local paths into the template while carrying the same expected manifest hash.
- [x] Run the official approved-cost command and replay; preserve the resulting receipt at `openspec/explore/dukascopy-canonical-backtest-receipt-2026-09-25.md`. Executed with the human-approved all-in costs (EURUSD `0.00011`, GBPUSD `0.00015`) and `--expected-manifest-sha256 e3c2caafb0a181a167a79d514fc9542886634643f4a543b3fbbd9367c75b745c` (EXT-01); both runs exited `0` and replayed byte-identically — see `apply-progress.md`'s "Official approved-cost run — complete".
- [x] Verify `lint-imports` keeps production packages free of `research` imports.

## Build Order

| Order | Slice | Notes |
|---|---|---|
| 1 | S-000 | Mandatory end-to-end skeleton. |
| 2 | S-001 | Independent canonical taxonomy migration. |
| 3 | S-002 | Builds on S-001 reconciliation assertions. |
| 4 | S-003 | Completes failure/replay evidence; official run waits for approved costs and readable external inputs. |

## Coverage and Check

All REQ-01, REQ-30, REQ-33, REQ-37, REQ-40, and REQ-68 clauses are owned above. Pass: four vertical/demoable slices, no layer-named or cleanup-only work, ≤2 explicit dependencies, and no Key-Level expansion, shadow/demo execution, or profitability gate.
