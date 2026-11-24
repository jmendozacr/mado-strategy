# Objectives and Hypotheses

## Research question

Can losing trades, invalidations and Stop Losses of an existing strategy be analyzed systematically
to discover recurring price-behavior patterns, and can that evidence be used to develop a genuinely
new trading approach — without optimizing or modifying the original strategy's rules?

This is a question, not a conclusion. The lab is designed to produce a **falsifiable, out-of-sample
testable** answer, including the answer "no exploitable signal found," which is treated as equally
valuable as a positive result.

## Motivating baseline

A strategy with a 20% win rate at 1:2 reward:risk has a negative idealized expectancy:

```
0.20 × 2R − 0.80 × 1R = −0.40R
```

Despite that, the *losing* trades may still encode recurring market behavior worth studying on its
own terms — independent of whether the original strategy's rules were well chosen.

## Research lines

- **A — Failure prediction.** Do pre-entry observable characteristics predict a higher probability
  of a setup reaching its Stop Loss? Could feed an independent filter on top of the existing system.
- **B — Post-Stop-Loss behavior (initial priority).** What does price do after a trade is
  invalidated? This line measures, without yet proposing a strategy:
  - Predominant direction after the SL.
  - Favorable and adverse excursion after invalidation.
  - Maximum price excursion.
  - Time to reach various post-SL displacements.
  - Reversals vs. continuations.
  - Volatility regime shifts around the SL.
  - Dependence on session, pair, and market regime.
  - Frequency of moves large enough to be exploitable after realistic costs.

  Any hypothetical new entry studied under this line can only trigger once its own entry condition
  is observable — i.e. no earlier than the original SL event plus whatever confirmation that
  hypothetical entry itself requires. It can never be back-dated to before its trigger is knowable.
- **C — Alternative strategy discovery.** Only pursued if A/B produce sufficiently robust evidence.
  A new strategy here may use entirely different entries, stops, targets, and timeframes than CRT —
  it is not required to reuse the same Key Levels, sessions, or confirmations. Equally, a losing
  strategy's signals are **not** assumed to become profitable merely by inverting them; that claim
  requires its own evidence.

## Open questions this lab exists to answer (examples, not requirements)

- Does price keep moving against the trade after the SL is hit?
- How far does price typically travel after a setup is invalidated?
- Is there a recurring structure immediately before/after the SL?
- Does the speed at which the SL is reached carry information?
- Are failures associated with particular volatility, structural, or session conditions?
- Do some invalidations anticipate a strong continuation?
- Are some failures liquidity sweeps followed by a reversal?
- Can these behaviors be distinguished using information available in real time (no hindsight)?
- Is there an alternative entry, triggered after an observable post-SL signal, with positive
  expectancy net of realistic costs?

## Explicit non-goals for this phase

- No modification of `docs/`, `detector/`, `scanner/`, or the D3/C2 rules.
- No claim of profitability.
- No pattern mining, clustering, or model training yet (see `04-methodology-safeguards.md`).
