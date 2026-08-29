# Plan Verify Gate History: CRT Backtest Simulation Engine

Two Plan Verify cycles ran before this change was cleared to build.

## Cycle 1 (4 iterations, spec V1→V8 / design V1→V6 / slices V1→V4)

Blind judges (Judge A: problem/scope fit; Judge B: simulated executor) reviewed the plan against the signed spec and design at each iteration.

- **Iterations 1-3**: `gaps`. Closed problem-fit gaps in the tradeable-population definition (which signal statuses count as candidates), the fill-simulation model (assumed vs. simulated fill), `signals_considered`'s measurement point, and the exclusion-bucket precedence order.
- **Iteration 4** (the final authorized cycle-1 iteration): `gaps` — but the driving finding was structural rather than product-level: spec V7 and design V5 had both elided large portions of their normative text (ADRs, REQ scenarios) behind "unchanged, see revision history" pointers. The memory backend used mid-pipeline only ever returns an observation's LATEST revision — those pointers were unretrievable. Two independent blind judges hit this wall on roughly 14 of 22 REQ-IDs and on 3 of 5 ADRs (BLOCKING findings). Iteration 4 exhausted cycle 1's authorized iterations → halted `plan-verify-failed`.

**Resolution**: spec V8 and design V6 answered by reproducing every REQ-ID's and ADR's full current text on every revision going forward, splitting into one topic key per domain once the concatenated size (~46k characters as one artefact) risked repeating the same truncation. This convention held for the rest of the change's planning artefacts.

## Cycle 2 (2 iterations, spec V8→V10 / slices V4→V5)

Re-entered against the reconstructed spec V8 / design V6.

- **Iteration 1**: `gaps` — two independent judges (spec self-review + simulated-executor read) independently found a self-contradiction: REQ-41 made `detections.csv`'s `signal_id` column unconditional, while REQ-45 promised byte-for-byte output without `--backtest`. Both cannot hold simultaneously. Resolved via a human-ratified product decision: make the column conditional on `--backtest` being passed. Spec bumped to V9 (REQ-41, REQ-45 modified).
- **Iteration 2**: `gaps` — 6 findings, 5 mechanical (a triage-authorized `in_ny_kill_zone` relocation + dead-parameter removal had no REQ-ID backing it; a slice-artefact staleness issue; a spec-wording ambiguity in REQ-31's swing-window upper bound), one (a swing-window lookahead concern) investigated and debunked directly against the design's data-model derivation — only the spec's wording needed a fix, not the design. Closed by: REQ-52 added (backs the relocation/removal), REQ-31 wording clarified (spec V10), and the slices artefact's staleness fixed.

**Verdict after cycle 2 iteration 2**: `ready`. Plan cleared for build.

## Note

This is the plan-review history only — the deeper north-star (foresight) gate that ran BETWEEN cycle 1 and cycle 2, catching a defect in the stop-loss model that neither judge above was scoped to find, is recorded separately in `north-star.md`.
