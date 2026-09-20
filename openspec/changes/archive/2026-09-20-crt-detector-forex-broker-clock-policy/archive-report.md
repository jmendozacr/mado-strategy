# Archive Report: crt-detector-forex-broker-clock-policy

**Archived at**: 2026-09-20
**Verify verdict**: pass-with-followups
**Spec version**: V1 (signed)

## Summary

Delivered the Forex broker-clock temporal policy as an opt-in `--forex-policy` CLI filter. The filter tags an `AlignedSignal` as a `ForexCRTSignal` only when the H4 candle enclosing the M15 anchor (derived via `bisect_right`) opens at 01:00 broker clock AND the M15 anchor falls within 02:00–04:00 broker clock. Session identity is explicitly NOT read from `CRTRange.start_index`.

The approved temporal policy is delivered and usable. All generic detection (Model-1, CRT ranges, alignment), the NY Kill Zone, and every pre-existing code path are preserved byte-for-byte when `--forex-policy` is absent.

Profiles, order flow, SMT, daily narrative, CISD/OB alternatives, targets, the 01:00–02:00 window, and the 04:00–05:00 window are intentionally deferred.

## Files Delivered

| File | Kind |
|---|---|
| `detector/core/broker_clock.py` | NEW — raw broker-clock predicates |
| `detector/core/forex_crt_context.py` | NEW — `ForexCRTContext` / `ForexCRTSignal` types |
| `detector/alignment/forex_broker_clock.py` | NEW — `detect_forex_crt_signals` filter |
| `detector/cli.py` | MOD — `--forex-policy` flag |
| `detector/tests/test_broker_clock.py` | NEW — 17 unit tests (REQ-70/71.1/72/75.2) |
| `detector/tests/test_forex_broker_clock.py` | NEW — 9 integration tests (REQ-73 incl. REQ-73.7 regression) |
| `detector/tests/test_cli.py` | MOD — 3 CLI tests (REQ-74) |

## Test Results (verify-final)

- Focused suite: **52 passed, 0 failed**
- Full suite: **324 passed, 1 pre-existing failure** (`test_partial_price_ordering` — missing real corpus, unrelated to this change), 9 skipped
- Import-linter: **2 contracts kept, 0 broken**
- adversarial_review: not-required (M, non-sensitive)

## Non-Blocking Followups (registered in pending-changes)

1. REQ-73.3 test isolation — wrong-H4-hour guard could have a standalone test with M15 inside the window
2. REQ-74.2 CLI test mocks the filter (wiring test only; logic covered by unit tests)
3. `ForexCRTContext` fields (Asia range, priority) not surfaced in `detections.csv` — requires future CSV schema change
