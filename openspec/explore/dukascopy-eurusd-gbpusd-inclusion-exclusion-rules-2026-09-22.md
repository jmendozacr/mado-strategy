# EURUSD + GBPUSD inclusion and exclusion rules

These rules govern the Dukascopy research experiment only. They make missing-minute handling, closure evidence, zero-volume rows, aggregation eligibility, and exclusion recording deterministic before any statistical result is calculated. They do not modify production code, the frozen three-instrument protocol, datasets, baselines, or instrument identities.

## Approved decision

Use conservative, fail-closed classification. A missing interval is treated as explained only when a retained JForex offline domain completely covers it. Every other missing interval is unresolved and can exclude dependent observations.

## Quick path

1. Validate the raw EURUSD and GBPUSD files against their manifest hashes and exact JForex header.
2. Convert timestamps using `Europe/Helsinki` for the exported `EET` label.
3. Classify every gap between consecutive rows against the retained offline-domain receipt.
4. Preserve zero-volume rows, but never use them as closure evidence.
5. Aggregate to M15, H4, and D1 only when missing minutes are absent or fully explained.
6. Exclude and ledger any signal whose required context, retest, or outcome depends on an unresolved interval.

## Decision table

| Condition | Treatment | Reason |
|---|---|---|
| Consecutive rows are one minute apart | Eligible continuity | No gap exists |
| Gap is fully covered by one or more retained offline domains | Explained closure | Provider evidence covers the complete interval |
| Gap is only partially covered by an offline domain | Unresolved | Partial evidence cannot justify the remainder |
| Gap has no covering offline domain | Unresolved | Do not infer closure from calendar intuition |
| Valid price row has zero volume | Preserve as an observation | Zero volume is data, not closure evidence |
| Non-finite, malformed, duplicate, or non-monotonic row | Reject input | Source integrity failure |
| Required bar contains unresolved missing minutes | Exclude that bar and dependent signal | Fail closed |
| Required bar is short only because of fully explained closure | Eligible, with reason recorded | Closure is evidenced, not imputed |
| Signal context, retest, or exit crosses an unresolved interval | Exclude signal | Outcome would depend on unknown market availability |

## Aggregation contract

- Use the approved timeframes only: M15, H4, and D1.
- Derive bucket boundaries from `Europe/Helsinki` wall time and convert them to UTC.
- Do not fill, interpolate, forward-fill, or synthesize prices for absent minutes.
- A bucket may contain fewer raw rows only when every absent interval is fully covered by retained offline-domain evidence.
- Record the bucket's explained-closure intervals in the exclusion/coverage ledger even when the bucket remains eligible.

## Exclusion ledger

Each excluded interval or signal must record:

| Field | Required value |
|---|---|
| instrument | `DUKASCOPY_EURUSD` or `DUKASCOPY_GBPUSD` |
| interval_start_utc | Inclusive UTC timestamp |
| interval_end_utc | Exclusive UTC timestamp when applicable |
| duration_minutes | Calculated duration |
| classification | `UNRESOLVED` or source-integrity failure |
| covering_domain | Domain identifier, or `none` |
| affected_artifact | Bar, context, retest, exit, or signal identifier |
| action | `excluded` |
| reason | Short deterministic explanation |

The ledger is an input to the run manifest. Its hash must be recorded before statistical outputs are accepted.

## Statistical boundary

The experiment reports pooled EURUSD + GBPUSD results and separate per-instrument results. No imputation or calendar-derived closure assumptions are permitted, and no comparison with the original three-instrument experiment is inferential.

## Gate before execution

No statistical result may be generated until the raw-input hashes, offline-domain receipt hash, adapter reference, exclusion-ledger hash, and deterministic run manifest are all recorded.

