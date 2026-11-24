# Next Research Unit — Recommendation

Given Phase 2's headline result (the raw post-SL continuation tendency is statistically
indistinguishable from the matched control baseline — `docs/11-research-findings.md` finding #11),
the next unit should NOT proceed directly to strategy design. Two disciplined options, in priority
order:

1. **Single, pre-registered test of the recovery-to-entry finding (#3/#8).** Define, before looking
   at any new data split, a specific hypothetical re-entry rule triggered only once price is
   confirmed back at/near the original entry level (satisfying the causal constraint that it cannot
   be known before that confirmation), and test whether ITS outcome — net of a realistic, cited cost
   model — differs from the matched-control baseline using the same block-bootstrap methodology. This
   is the most concrete, already-evidenced candidate from this phase.
2. **A dedicated, single-hypothesis test of the 1am-vs-9am session difference (#5/#7)** before
   trusting it: stratify a fresh comparison (ideally pre-registering the exact metric and horizon)
   rather than re-mining this phase's own stratified output further.

Either option should reuse this lab's existing building blocks read-only
(`eligibility/stop_eligibility.py`, `behavior/post_stop_metrics.py`, `control/sampling.py`,
`stats/bootstrap.py`) rather than duplicating them, and must register its hypothesis and evaluation
criterion in `docs/06-limitations-and-decisions-log.md` BEFORE running it against any data split, per
`docs/04-methodology-safeguards.md`.

What this phase explicitly recommends AGAINST: proceeding to Line C (alternative strategy discovery)
on the strength of the raw continuation tendency alone — Deliverable C already showed that tendency is
not distinguishable from ordinary market behavior.
