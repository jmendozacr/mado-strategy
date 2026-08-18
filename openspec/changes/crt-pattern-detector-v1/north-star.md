# North Star — crt-pattern-detector-v1 (Foresight Checkpoint)

**Verdict**: aligned (steward foresight gate, post-design)

## North Star

The trader's eye stops being the bottleneck for FINDING CRT/ICT setups and becomes the judge of setups already found — the methodology in `docs/charter-1..5.md` is read onto his own historical data mechanically and honestly (nothing silently dropped, nothing detected by peeking at the future), tagged with whether the higher timeframe agreed. Success is measured by a chart he can act on, not by detectors that pass their tests.

## Conscience questions — human-ratified answers (the commitment `reckoning` will hold delivery against)

1. **Sequencing** (detector before backtest proves profitability): accepted as sound — the detector is phase 2's required input.
2. **Python vs. Pine Script — the load-bearing question**: user CONFIRMED commitment to phase 2 (backtest) and phase 3 (live alerts). This is the explicit justification for Python over a much-shorter Pine Script path — property-based no-lookahead testing and multi-candle state machines (Model-1's Respect Rule, Inside/Outside-Bar CRT) are things Pine cannot do well (repainting is Pine's classic failure mode, exactly what REQ-07/22 exist to prevent). **If phases 2/3 are later abandoned, this justification no longer holds — worth re-litigating the Python choice if that happens, not before.**
3. **Partial scope** (OB/Breaker deferred): user explicitly ACCEPTED — 5 of 7 patterns automated in v1 is a real improvement, not required to be complete.

## Deferred/lower-priority note (not blocking)
Suspicion flagged by the steward, not a finding: the custom AST config-completeness linter may be disproportionate ceremony for a 5-detector, single-user project. Not a halt — `import-linter` and the hypothesis no-lookahead suite were both explicitly defended as correctly-scoped.
