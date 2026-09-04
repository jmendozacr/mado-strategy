# Plan Verify Result

**Change**: crt-detector-key-level-confluence-core
**Iteration**: 2/3
**Mode**: plan
**Write mode**: n/a (spec_source: internal)

## Verdict: gaps

Both blind judges (opus, parallel, anti-anchoring) reviewed spec V2 (signed) + slices V2. Judge A received `problem_statement` + `scope` + spec V2 + slices V2 verbatim (problem/scope-fit lens). Judge B received ONLY slices V2 verbatim (simulated-executor lens). Neither had visibility into the other or into orchestrator reasoning.

## Findings

| # | Judge | Severity | Finding | Status | Route |
|---|---|---|---|---|---|
| 1 | A | Critical | Both-sides-HTF-breach tiebreak (14% of candles) arbitrarily always credited the high side; flips 5.4% of signal verdicts | **Resolved — user decision** | spec V3: REQ-55.6 rewritten — confluence counts if EITHER breached side's wick overlaps a valid Key Level zone |
| 2 | A | Info | Gate's discrimination is driven almost entirely by FVG expiry/mitigation, not geometric overlap per se — spec's framing overstates "geometric overlap" as the mechanism | Routed | spec V3: reword problem statement / REQ-53 preamble to describe the mechanism honestly (expiry state is load-bearing, not incidental) |
| 3 | A | Warning (real) | Confluence is computed per-HTF-candle, not per-individual-Model-1-signal — ~19.4 Model-1 signals on average share one HTF candle's verdict, but REQ/problem wording implies per-signal precision | Routed | spec V3: reword REQ-55 preamble + problem statement to state granularity accurately (HTF-candle-level, inherited by every LTF signal under that candle) |
| 4 | A | Critical | REQ-55.11 (expiry: not credited at/after expiry_index) collides with REQ-55.4 (zone-inclusive boundary touch) — a candle that both purges AND fills the same FVG (the single strongest-confluence case, ~0.2% of signals) is denied credit | **Resolved** | spec V3 + design V3: mirror origin_index's inclusive-at-index treatment — expiry exclusion becomes "MUST NOT be credited to a purge STRICTLY AFTER its expiry index" (expiry_index itself still counts) |
| 5 | A | Warning (real) | 2 scope items lack REQ-ID coverage: consumer-coupling fitness test, ≥50-trades floor | Routed | spec V3: add explicit REQ-IDs/scenarios for both |
| 6 | A | Warning (real) | REQ-46 (MODIFIED) has no scenario/slice coverage | Routed | slice V3: map REQ-46's existing 2 scenarios onto a slice task list (regression coverage, no new behaviour) |
| 7 | B | Critical | W's denominator is ambiguous between the full aligned non-fvg_fill population (105,061) and the post-never-confirmed-cut subset (41,160) — under the subset reading, the 0.75 upper bound is mathematically unreachable, making S-000's own halt-gate criterion uncheckable | **Resolved** | design V3: W's denominator is explicitly the FULL aligned non-fvg_fill population (105,061) — matches REQ-60.2's plain-language scope description and Judge A's own empirical methodology (which already clears the band under this reading) |
| 8 | B | Warning (real) | No existing or planned fixture produces the mixed population REQ-40.6/S-005.3's non-zero-bucket assertions require | Routed | design V3 + slice V3: specify a new e2e fixture with 2 HTF purge candles (one confluent, one not) |
| 9 | B | Warning (real) | REQ-40.2's existing shipped assertion (`session_considered == session_model1_rows`) becomes conditionally false once the gate withholds rows | Routed | spec V3: relax REQ-40.2's assertion or explicitly scope its test to a fixture with no withheld signals |
| 10 | B | Warning (real) | REQ-59.2 as worded is false for signals whose bucket membership is fixed by an earlier cut, before ever reaching the confluence check | Routed | spec V3: narrow REQ-59.2 to signals that reach the confluence-check stage |
| 11 | B | Warning (real) | Baseline capture instructions conflict — S-000.1 says reference obs #419 (don't re-run), design §8.5 says capture before any code; obs #419 lacks GBPUSDm/DXYm and detections.csv row counts REQ-60.1 needs | Routed | design V3 + slice V3: S-000 task list supplements obs #419 with GBPUSDm/DXYm pre-gate baselines + detections.csv row counts, captured before gate code lands |
| 12 | B | Product | `--types model1` silently withholds rows with no disclosure note | **Resolved — user decision** | No change — gate applies uniformly regardless of flags, no special-case note needed |
| 13 | User | — | New binding criterion: if post-gate performance regresses vs the pre-gate baseline (obs #419 + supplemented pairs), S-000 must HALT and notify the user before building S-001..S-006 — even if the W-band (10–75%) passes | **New requirement** | spec V3: new REQ-60 sub-scenario; slice V3: explicit S-000 halt condition, analogous to the existing W-band halt |

## Routing

spec V3 (`sdd-spec`) → design V3 (`sdd-design`) → slice V3 (`sdd-slice`) → plan-verify **iteration 3/3 — final budgeted iteration**. If iteration 3 does not reach `ready`, halt `plan-verify-failed` and escalate to the human per the orchestrator contract.

**Priority order for the fix pass**: #7 (W-formula ceiling) and #8 (fixture impossibility) first — a walking skeleton whose own halt-gate criterion is mathematically uncheckable cannot execute regardless of anything else being correct.
