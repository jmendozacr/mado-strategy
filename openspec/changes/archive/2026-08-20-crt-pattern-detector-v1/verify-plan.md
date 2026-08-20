# Plan Verify Gate — History

**Change**: crt-pattern-detector-v1 | **Iterations used**: 3/3 | **Final verdict**: ready (human-ratified)

Two blind judges (Judge A: problem/scope fit; Judge B: simulated executor with zero other context) reviewed the plan in parallel, three times, per the SDD harness's plan-verify protocol.

## Iteration 1
Judge A: 6 findings (Breaker Block coverage gap — deliberate; missing config-extensibility REQ; missing no-lookahead REQs for FVG/CRT/MSS/alignment; GBP/USD never referenced; CLI filters untraceable to a REQ; REQ-05 scenario implied unscoped kill-zone logic).
Judge B: 29 questions, did not say "ready to execute" — mostly content that existed in spec/design but wasn't inlined into the slices artefact.
**Fix**: added REQ-25–28, fixed REQ-05's wording, made slices self-contained (first pass).

## Iteration 2
Judge A: (not separately re-run at this depth — see iteration 3, which supersedes)
Judge B: 35 questions — revealed a real process bug: two `mem_save` calls had degraded the spec/design artefacts to delta-only "unchanged, see prior save" notes, making the actual content unrecoverable to any other reader. This explained most of the "missing content" findings.
**Fix**: rewrote spec (V3) and design (complete) with FULL content, never a delta note again. Corrected the triage artefact's scope, which had drifted out of sync with the actual negotiated plan.

## Iteration 3
Judge A: 4 findings, much lighter — no acceptance criterion validates against real market data (philosophical, addressed via a manual acceptance step); "conservative tuning" was unlinked prose (now traced to concrete numeric defaults); instrument coverage (EUR/USD only has a positive test) — minor; two slice tasks (CLAUDE.md update, import-linter setup) trace to no REQ — normal engineering housekeeping, not a gap.
Judge B: found one genuine algorithmic bug (CRT model classification contradicted charter-1's own taxonomy — **fixed**), one false alarm (claimed the FVG predicate was inverted — verified against the actual saved content and found to be a misread, not fixed since nothing was broken), and ~20 legitimate specification-precision gaps (CRT range formation rule was entirely missing, MSS's ratio terms undefined, Model-1's retest/confirmation logic underspecified, `detections.csv` schema didn't fit all 6 detection types, CLI `--timeframe`/pairing-table contradiction, etc.) — all resolved in `design.md`'s final version.

Two genuinely product-level questions were escalated to the human directly (not resolvable by the orchestrator):
1. **Real-data validation approach** → resolved: manual acceptance step added to S-006 (run against one real MT5 export, eyeball the result).
2. **CRT "currently forming" live state** → resolved: deferred as a registered v1.1 follow-up (reopening REQ-14's noise-flood problem needs careful separate design).

## Outcome
Per protocol, 3 iterations without a clean automated pass triggers human escalation rather than a 4th automated round. The human reviewed the remaining findings, confirmed the fixes, and answered the 2 genuine open questions. **Verdict: ready.** Proceeds to `/build --scope=skeleton`.

## Lesson learned (recorded for all future SDD work in this project)
A `mem_save` to an existing topic_key must always contain the artefact's COMPLETE current content — never a diff/changelog-only note. `mem_get_observation` returns only the latest revision; a delta-only save makes the full content unrecoverable to any other reader, even though the save itself succeeds without error. This cost 2 of the 3 plan-verify iterations on this change.
