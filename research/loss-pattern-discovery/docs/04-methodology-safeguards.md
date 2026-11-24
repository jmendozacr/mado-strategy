# Methodology Safeguards

This research line prioritizes scientific rigor and causality over producing a positive result. The
following protocol is binding for every subsequent phase of this lab.

## Threats this protocol guards against

- Look-ahead bias (using information not yet observable at decision time).
- Data leakage (post-outcome fields contaminating predictive features).
- Survivorship and selection bias (dropping inconvenient trades/periods silently).
- Overfitting / overoptimization to the discovery sample.
- Multiple testing (many hypotheses tried, best one reported as if it were the only one tried).
- Dependence between trades (overlapping holding periods, shared triggers, correlated outcomes).
- Temporal overlap between discovery and evaluation windows.
- Unstable historical regimes (an effect real in one sub-period but not representative overall).
- Unrealistic fills (prices not actually reachable given the bar/candle and the fill model used).
- Results explained only by spread/costs rather than genuine directional or structural information.

## Feature separation (hard rule)

Every event record keeps three disjoint groups, enforced at the schema level
(`schema/events.py`):

- `features_pre_entry` — known strictly before the original trade's entry.
- `features_at_stop` — known strictly at/by the moment the SL (or invalidation) is confirmed.
- `post_stop_outcomes` — anything that depends on price action *after* the SL, including MFE/MAE,
  time-to-move, reversal/continuation labels, and any hypothetical post-SL entry's own outcome.

`post_stop_outcomes` fields must never be used as predictors for anything evaluated at or before the
corresponding stage. This is checked by an automated validator (`validate/`), not only documented.

## Data splits

- Chronological splits only: **discovery → validation → final test**, in time order. No conventional
  random partition that mixes temporally adjacent observations.
- Purge/embargo windows around any split boundary that overlapping trades (shared holding period or
  shared triggering structure) could otherwise straddle.
- A "reserved" sub-range inside years that already participated in *prior* research in this
  repository (e.g. the D3/C2 2015-2026 robustness audit) is **not** treated as genuine virgin
  out-of-sample. It is documented as "previously-seen data, reserved" and findings from it are
  weighted accordingly, never reported as fresh OOS confirmation.
- Hypotheses are registered (written down, with their evaluation criteria) **before** being run
  against reserved/validation data. The registration itself lives in
  `06-limitations-and-decisions-log.md` with a timestamp, so a hypothesis cannot be silently reworded
  after seeing the result.

## Methodological order (binding for this phase and the next)

1. Descriptive statistics, empirical distributions, conditional probabilities, uncertainty intervals
   (bootstrap or equivalent), baseline comparisons, and stability checks across periods and pairs.
2. Only if (1) shows a stable, non-trivial signal: interpretable models (decision trees, simple
   interpretable rules), then — only with explicit justification — gradient boosting or exploratory
   clustering.

No step-2 method is used before step-1 has been run and reported, including when a result "looks
promising" early. A discovery must be interpretable before it is allowed to become a strategy
candidate.

## Evidence eligibility (upstream of all of the above)

Before any historical trade is used as evidence, its source is checked for:

- Causal validity of its entry/exit logic (no retrospective anchor selection, no post-hoc Key Level
  placement).
- Correct handling of broker-H4-vs-NY-feeder timezone reconstruction where H4 anchors are involved.
- A fill model that only uses prices actually reachable from the bar's own OHLC, with intrabar
  SL/TP ordering ambiguity (M15 resolution cannot always tell which was touched first) recorded as a
  flag, not silently resolved in either direction.
- Known prior findings in this repository (e.g. cost-fragility, lack of genuine OOS, period
  concentration of any pair's edge) are propagated as per-record/per-source flags rather than
  discarded — a record can be *usable* while also being *flagged* as coming from a weaker-evidence
  source.

Records that fail these checks are kept in the dataset with an explicit `execution_validity` /
`provenance` status rather than silently dropped, so selection bias from exclusion is itself visible
and auditable.
