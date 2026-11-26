# Checkpoint Handoff — Loss Pattern Discovery Lab (verified before this experiment started)

Written 2026-11-26, before any Raza-rule code ran, as a durable record of the state this new,
separate experiment builds on top of. This file documents an EXISTING, prior research line
read-only -- it changes nothing in `research/loss-pattern-discovery/`.

## Verified Git state

- Checkout: `D:\Josué\Documents\proyectos\mado-strategy-research-loss-pattern-discovery`
- Branch: `research/loss-pattern-discovery`
- `HEAD`: `631149cf40ae2626aa178bb62bf886da585d22e4` ("docs(research): record Phase 10 commit SHA")
- Immediately preceding commit: `90e932a` ("feat(research): Phase 10 confirmation path and
  early-stop association")
- Base of that pair: `4b3e9c1` (Phase 9's own recorded SHA)
- Remote tracking: `origin/research/loss-pattern-discovery` at the SAME commit (`631149c`) --
  fully pushed, nothing ahead or behind.
- Working tree: clean, zero uncommitted changes, at the time this handoff was written.

**The reported Phase 10 checkpoint (`631149c`, following `4b3e9c1`) is verified exactly as
reported.** HEAD has not moved; there is no later work to preserve, and no reset was needed or
performed.

## Verified Phase 8-10 counts (recomputed directly from the on-disk artifacts, not from memory)

Source files read: `research/loss-pattern-discovery/artifacts/phase8_funnel_reconstruction.json`
and `phase8_funnel_reconciliation.json` (both regenerable per that lab's own README; not
regenerated here, read as-is since they already matched the reported numbers exactly).

| | 1AM | 9AM | Total |
|---|---|---|---|
| Triggers with Key Level (baseline activations) | 11,206 | 8,712 | 19,918 |
| Model-1 confirmed | 1,805 | 3,311 | **5,116** |
| Executed | 620 | 1,427 | **2,047** |
| Evaluable (closed) | 619 | 1,424 | 2,043 |
| Open (censored) | 1 | 3 | **4** |

`fully_reconciled: true` in the on-disk artifact; `baseline_check` matches the expected
620/619/1 (1AM) and 1,427/1,424/3 (9AM) exactly. These are the exact numbers this new experiment's
own population must reconcile against at its own "activation" and "closed trade" stages.

## Phase 10 conclusion (verbatim summary, for context -- not re-tested here)

Verdict `MODEL_SPECIFIC_ASSOCIATION`: signals that confirm Model-1 directly (zero internal
invalidations) show a HIGHER E1 (next-bar Stop Loss) rate than signals needing at least one
internal restart. Distinguishable from zero only in 9AM (+3.39pp, 95% CI [+0.83pp, +5.97pp], n=626
vs. 798), not in 1AM (+1.11pp, CI includes zero, n=364 vs. 255), though both point the same
direction and every per-instrument check (AUDUSD included) agrees in sign. Standardizing the
persistent 1AM/9AM E1 gap (+5.38pp unadjusted) by this variable leaves it essentially unchanged
(+5.11pp) -- it does not explain that gap. **Neither model's own point difference clears this
lab's pre-declared 5pp relevance bar** -- the finding is reported as real but small in magnitude,
an association within the executed population, never a causal or tradable claim.

## Phase 11 proposal (registered, paused)

A proposal to investigate the Stage-6 RR floor (`min_risk_reward=2.0`, 100% of Stage-6 attrition
per Phase 9, discarding 2,592 of the 5,116 confirmed signals: 1,087/1,805 = 60.2% of 1AM's,
1,505/3,311 = 45.5% of 9AM's) is registered at
`research/loss-pattern-discovery/docs/87-phase11-rr-filter-counterfactual-proposal.md`. **It has
not been executed.** No RR value has been changed; no counterfactual backtest has run. It remains
paused, pending separate explicit authorization.

## Boundary for this new experiment

This experiment (`research/raza-crt-candle2-9am/`) is a SEPARATE research line, kept out of
`research/loss-pattern-discovery/`'s own subtree, with its own protocol and its own results. It
reuses the SAME verified D3/C2 production code (`audit/2026-11-17-causal-lookahead-audit/`,
`detector/entries/model1.py`, `detector/backtest/`), the SAME historical instruments and date
range, and the SAME real executed-trade ledger -- all read-only. `detector/`, `scanner/`, `docs/`
(the Mado charters), and the original historical ledgers remain read-only for this experiment too.
Mado's charters remain the reference for the project's own strategy; Raza's thread (a different,
external author's framework) is used here strictly as a research lens for ONE descriptive
question, never as a replacement reference.
