# North Star: Dukascopy Backtest Readiness

**Checkpoint**: foresight  
**AI-assessable verdict**: aligned  
**Human ratification**: confirmed

## Intent

Produce one trustworthy, reproducible EURUSD/GBPUSD H4/M15 backtest evidence set that can inform a later shadow-mode and demo-account decision without presenting misleading historical metrics as fact.

## How It Fits

The change preserves the one-way production pipeline `core → primitives → composite|entries → alignment → backtest → viz`. Canonical population, fill, reconciliation, and published-label semantics remain owned by `backtest` and `viz`. A concrete Dukascopy command stays outside production under `research/`, validates the frozen inputs, calls production pure functions inward, and writes deterministic evidence. Production packages remain forbidden from importing `research`.

## Outcome Chased

The person deciding whether the strategy merits later shadow-mode work receives evidence they can reproduce and audit: both target pairs are present, source identity and hashes are verified, costs and configuration are explicit, trade results reconcile exactly, fill-candle adverse movement is not hidden, confirmed-without-retest signals are not mislabeled, and an unprofitable run remains valid evidence.

## Problem-to-Design Map

| Stated pain | Designed response | Pre-archive proof |
|---|---|---|
| Historical metrics can mislead | Split `confirmed_no_retest` from `never_confirmed`; restore the signed nine-bucket reconciliation | Behavioural and CLI tests plus exact reconciliation |
| Fill-candle losses are omitted | Resolve inclusive SL exposure on the fill candle before favourable exits | Bullish/bearish boundary, tie, gap, and partial-exit tests |
| The two-pair result is not reproducible | Validate manifest and six derived files; emit ordered trade files and a deterministic receipt | Successful official run plus byte-identical replay |
| Profitability could be mistaken for validity | Completion depends on evidence integrity, never P/L | Synthetic and official unprofitable runs still complete successfully |
| Provider orchestration could contaminate production | Keep the command under `research/` with inward-only imports | Import-linter fitness check |

## End-to-End Journey

The researcher supplies the retained manifest, derived-data root, output directory, and approved pair-specific costs. The command validates all sources before simulation, runs EURUSD and GBPUSD sequentially through the canonical detector/backtest functions, and publishes nothing final unless both succeed. It then emits ordered per-pair trades and one receipt containing provenance, configuration, costs, reconciliation, metrics, and artifact hashes. Repeating the command against the same inputs must reproduce identical bytes. The resulting evidence informs a later decision; it does not itself approve shadow mode or claim profitability.

## Reckoning Criteria

- The preserved official evidence covers both EURUSD and GBPUSD H4/M15 and identifies approved inputs, hashes, complete configuration, pair-specific costs, reconciliation, metrics, and trades.
- An identical replay produces byte-identical receipt and trade artifacts.
- Missing or altered sources fail closed without presenting completed evidence as valid.
- Reconciliation assigns every considered signal to exactly one signed terminal bucket and distinguishes `confirmed_no_retest` from `never_confirmed` in public output.
- Fill-candle SL touches, including equality and simultaneous favourable levels, resolve conservatively as specified; the strict pre-entry beyond-SL exception remains intact.
- Profitability does not control execution success or evidence validity.
- No production package imports provider-specific research code.

No deferred outcome is hidden in these criteria: the later shadow-mode/demo decision is explicitly out of scope, while the decision-grade backtest evidence must exist and be replayable before archive.

## Shorter-Path Check

A manual report or two invocations of the production CLI would be less code, but would not provide atomic manifest validation, canonical two-pair provenance, or byte-identical replay. The proposed concrete research command is the shortest path identified that reaches the same auditable outcome. The design correctly avoids a generic runner or serializer abstraction.

## Human Ratification

The human confirmed the intended strategy frame is D1 → H4 → M15: existing D1 key levels and H4 context are required alongside M15 execution. This does not admit Key-Level expansion.

The human also confirmed that the receipt and ordered per-pair trade artifacts will be usable by the person deciding whether to proceed to shadow mode.

The human confirmed that this reproducible evidence set is significant enough to justify building now, despite deliberately stopping short of shadow-mode execution and any profitability threshold.

Pair-specific all-in costs remain an official-run preflight. Their exact values must be approved before the official run.

The ratified answers become the commitment against which the reckoning checkpoint will judge delivery.
