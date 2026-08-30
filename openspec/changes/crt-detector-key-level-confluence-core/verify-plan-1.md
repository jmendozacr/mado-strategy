# Plan Verify Result

**Change**: crt-detector-key-level-confluence-core
**Iteration**: 1/3
**Mode**: plan
**Write mode**: n/a (spec_source: internal)

Mirrors engram `sdd/crt-detector-key-level-confluence-core/verify-plan-1` (obs #423) — see there for the full 21-finding table and routing. Verdict: **gaps**.

Headline finding: Judge A empirically ran the signed confluence rule against real `pairs/` data and found it withholds only 2.8% of signals (near-vacuous) because REQ-53.2's "FVG never expires on mitigation" lets zones accumulate to ~9x the instrument's price range. User resolved: FVG expires on mitigation (reverses the earlier decision, now informed by this evidence).

Also found: REQ-55's wick-extreme direction convention is inverted against the real codebase (both judges, independently); the cross-artefact fitness function the spec's own push-back already flagged as wrong gets resurrected in the design; ~25 existing tests would silently break; the e2e HTF fixture can't produce a credited Key Level at all.

Routing: sdd-spec V2 → sdd-design V2 → sdd-slice V2 → plan-verify iteration 2/3.