# Verify Report: crt-detector-forex-broker-clock-policy

- **Spec version**: V1 (signed)
- **Verify mode**: final
- **Date**: 2026-09-19
- **Overall verdict**: pass-with-followups
- **adversarial_review**: not-required (M classification, non-sensitive)

---

## Compliance Matrix

| REQ | Scenario | Code location | Test location | Verdict |
|-----|----------|---------------|---------------|---------|
| REQ-70.1 | london_crt happy | `core/broker_clock.py:4-6` | `tests/test_broker_clock.py::test_is_london_crt_h4_true` | PASS |
| REQ-70.2 | asia_range happy | `core/broker_clock.py:9-11` | `tests/test_broker_clock.py::test_is_asia_range_h4_true` | PASS |
| REQ-70.3 | no conversion | `core/broker_clock.py` (no `zoneinfo`/`astimezone`/`replace(tzinfo=)` anywhere) | `tests/test_broker_clock.py::test_broker_clock_does_not_import_kill_zone` (structural); grep verification: zero matches | PASS |
| REQ-70.4 | non-matching hour | `core/broker_clock.py:4-11` (both predicates return False for hour != 1 and != 21) | `tests/test_broker_clock.py::test_classification_neither` | PASS |
| REQ-71.1 | Asia timestamp derivation | `core/broker_clock.py:24-26` (`timedelta(hours=4)`) | `tests/test_broker_clock.py::test_asia_range_timestamp` | PASS |
| REQ-71.2 | Asia range found in series | `alignment/forex_broker_clock.py:57-66` | `tests/test_forex_broker_clock.py::test_find_asia_range_index_found` | PASS |
| REQ-71.3 | Asia range absent | `alignment/forex_broker_clock.py:57-66` (returns None) | `tests/test_forex_broker_clock.py::test_find_asia_range_index_not_found` | PASS |
| REQ-72.1 | 02:00 in window | `core/broker_clock.py:14-16` | `tests/test_broker_clock.py::test_in_execution_window_02_00` | PASS |
| REQ-72.2 | 02:15 in window | `core/broker_clock.py:14-16` | `tests/test_broker_clock.py::test_in_execution_window_02_15` | PASS |
| REQ-72.3 | 04:00 excluded | `core/broker_clock.py:14-16` (`< 4`) | `tests/test_broker_clock.py::test_in_execution_window_04_00_excluded` | PASS |
| REQ-72.4 | 01:59 excluded | `core/broker_clock.py:14-16` (`2 <=`) | `tests/test_broker_clock.py::test_in_execution_window_01_59_excluded` | PASS |
| REQ-72.5 | priority 03:15 | `core/broker_clock.py:19-21` | `tests/test_broker_clock.py::test_in_priority_subwindow_03_15` | PASS |
| REQ-72.6 | priority 02:45 excluded | `core/broker_clock.py:19-21` | `tests/test_broker_clock.py::test_in_priority_subwindow_02_45_excluded` | PASS |
| REQ-73.1 | happy, non-priority | `alignment/forex_broker_clock.py:16-54` | `tests/test_forex_broker_clock.py::test_aligned_signal_in_execution_window_emits_forex_crt_signal` | PASS |
| REQ-73.2 | happy, priority | `alignment/forex_broker_clock.py:51` (`in_priority_subwindow`) | `tests/test_forex_broker_clock.py::test_priority_subwindow_flag` | PASS |
| REQ-73.3 | wrong H4 hour | `alignment/forex_broker_clock.py:42-43` | `tests/test_forex_broker_clock.py::test_signal_outside_execution_window_excluded` (enclosing H4 is 05:00, not 01:00; also fails window check) | PARTIAL |
| REQ-73.4 | outside execution window | `alignment/forex_broker_clock.py:44-45` | `tests/test_forex_broker_clock.py::test_signal_outside_execution_window_excluded` | PASS |
| REQ-73.5 | unaligned | `alignment/forex_broker_clock.py:31-32` | `tests/test_forex_broker_clock.py::test_unaligned_signal_excluded` | PASS |
| REQ-73.6 | Asia range absent | `alignment/forex_broker_clock.py:69-82` (returns None fields) | `tests/test_forex_broker_clock.py::test_forex_context_asia_range_none_when_missing` | PASS |
| REQ-73.7 | start_index regression | `alignment/forex_broker_clock.py:37-40` (bisect, not start_index) | `tests/test_forex_broker_clock.py::test_session_identity_via_bisect_not_start_index` | PASS |
| REQ-74.1 | backward compat | `cli.py:156` (guarded by `args.forex_policy`) | `tests/test_cli.py::test_forex_policy_backward_compat` | PASS |
| REQ-74.2 | filtering | `cli.py:156-164` | `tests/test_cli.py::test_forex_policy_filters_to_execution_window` | PASS |
| REQ-74.3 | empty result | `cli.py:156-164` | `tests/test_cli.py::test_forex_policy_no_qualifying_signals` | PASS |
| REQ-75.1 | coexistence | `core/kill_zone.py` unchanged; `core/broker_clock.py` is a separate module | Structural: no import coupling between the two modules (verified via grep + `test_broker_clock_does_not_import_kill_zone`) | PASS |
| REQ-75.2 | no modification | `core/kill_zone.py` last modified by commit `f44b2c4` (backtest engine, pre-dating this change) | `git log -1 -- core/kill_zone.py` confirms no modification | PASS |

---

## Test Results

### Full suite

- **Command**: `cd detector && uv run pytest -v --tb=short`
- **Result**: 324 passed, 1 failed, 9 skipped
- **Failure**: `tests/property/test_partial_price_ordering.py::test_partial_price_ordering_holds_across_real_corpus`
  - **Classification**: PRE-EXISTING
  - **Evidence**: Last modified by commit `53a6514` (prior change: `fix(detector): make stop-loss buffer ATR-relative`). Fails because it globs for corpus CSV files in `../pairs/H4/` which are not present in this environment. No import or dependency on any file added by this change.
- **Skips**: 6 in `tests/research/test_classify_trades.py` (corpus-dependent), 3 elsewhere. All pre-existing.

### Focused suite (this change only)

- **Command**: `cd detector && uv run pytest tests/test_broker_clock.py tests/test_forex_broker_clock.py tests/test_cli.py -v --tb=short`
- **Result**: 52 passed, 0 failed, 0 skipped

---

## Import-Linter Result

- **Command**: `cd detector && uv run lint-imports`
- **Result**: 2 contracts kept, 0 broken
  - `Layered pipeline (ADR-01)`: KEPT
  - `Research tooling must not leak into production layers`: KEPT

### Layer placement audit

- `core.broker_clock` -> `core` layer (bottom). Imports only `datetime` (stdlib). Correct.
- `core.forex_crt_context` -> `core` layer. Imports nothing from the project. Correct.
- `alignment.forex_broker_clock` -> `alignment` layer. Imports from `core` (down) and `alignment.htf_ltf` (same layer). Correct.
- No new module imports `kill_zone`. Confirmed via grep.
- No new module uses `zoneinfo`, `astimezone`, or `replace(tzinfo=...)`. Confirmed via grep.

---

## Structural Verifications

1. **No timezone arithmetic**: `core/broker_clock.py` uses raw `datetime.hour` comparisons and `timedelta(hours=4)`. Zero `zoneinfo`/`astimezone`/`replace(tzinfo=)` calls. Confirmed.
2. **Session identity via bisect**: `alignment/forex_broker_clock.py:37` uses `bisect.bisect_right(htf_timestamps, m15_anchor_ts)`. `CRTRange.start_index` is never read inside `detect_forex_crt_signals`. Confirmed.
3. **`kill_zone.py` independence**: `core/kill_zone.py` is unmodified (last commit `f44b2c4`). No new file imports it. `broker_clock` and `kill_zone` share no coupling. Confirmed.
4. **CLI `--forex-policy`**: Defined as `action="store_true"`, `default=False`. Filter injection at `cli.py:156-164` is AFTER `tag_alignment` and BEFORE date/session filters, CSV write, and backtest. When flag is absent, the conditional block is skipped entirely, preserving byte-identical behavior.

---

## Followups (non-blocking)

1. **REQ-73.3 test isolation**: The existing test `test_signal_outside_execution_window_excluded` covers the wrong-H4-hour rejection path but simultaneously triggers BOTH the H4-hour guard and the execution-window guard. A dedicated test with an M15 anchor at hour 2 (inside the execution window) but an enclosing H4 at hour 5 (wrong session) would isolate the H4-hour guard specifically. Non-blocking because the predicate `is_london_crt_h4` is independently unit-tested in `test_broker_clock.py` and the bisect derivation is tested in `test_session_identity_via_bisect_not_start_index`.

2. **REQ-74.2 mock scope**: The CLI test for filtering mocks `detect_forex_crt_signals` to return `[]`, which verifies wiring but not end-to-end filtering logic at the CLI layer. The actual filtering is thoroughly unit-tested in `test_forex_broker_clock.py`. Non-blocking.

3. **ForexCRTSignal context not surfaced in CSV**: The `ForexCRTContext` fields (enclosing H4 index, Asia range, priority flag) are not written to `detections.csv` when `--forex-policy` is active. The CLI extracts only `.aligned_signal` from each `ForexCRTSignal`, discarding the context. This is a known limitation — surfacing these fields requires extending the CSV schema (future change).
