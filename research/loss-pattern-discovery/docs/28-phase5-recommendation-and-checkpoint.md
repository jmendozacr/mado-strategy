# Deliverable F — Recommendation for Phase 5

## The priority hypothesis

**Does the `origin_model` label (1AM vs. 9AM) itself -- not a correlated volatility/session
artifact -- explain the now THREE independent, consistent differences observed between these two
models across Phases 2, 3, and 4?**

- Phase 2/3: 1AM shows larger post-SL MAE and higher recovery-to-entry than 9AM.
- Phase 4 (this phase): 1AM shows a much higher rate of `ambiguous`/`insufficient` pre-SL path
  reconstruction (31.2% vs. 15.3%) -- i.e. 1AM failures resolve faster/with less observable
  structure.

This is proposed over the other candidates in `docs/27-...` (the favorable-excursion pre-entry
signature, finding #8) because it already has three convergent, independently-derived observations
pointing the same direction -- the strongest evidentiary base available in this lab right now --
while finding #8 would be a fresh hypothesis with zero prior evidence behind it yet.

- **Variable observable**: `origin_model` (`Identification.session_label`) -- trivially known at
  signal activation, long before entry; also `atr_m15_at_entry`/`risk_atr` (Phase 4's own pre-entry
  features), to test whether the model-label effect survives after conditioning on volatility.
- **En qué momento**: at signal activation / order placement -- before entry, let alone before any
  SL.
- **Qué evento posterior intentaríamos anticipar**: whether the 1AM-vs-9AM gap in post-SL behavior
  (Phase 2/3) and failure-path reconstructibility (Phase 4) persists once volatility/risk-sizing at
  entry is held fixed -- i.e. is this a genuine model-specific mechanism, or a volatility proxy.
- **Qué grupo de comparación**: 1AM vs. 9AM trades matched on instrument, period bucket, and
  `risk_atr` (not just instrument/period/direction as Phase 3's control did) -- a NEW, tighter
  matching dimension specifically designed to isolate the model label from volatility.
- **Cómo evitaríamos sesgo retrospectivo**: register the exact comparison and matching rule before
  running it against this (already-examined) 2015-2026 data; this is explicitly a REPLICATION/
  refinement of an existing observation, not a new data-mined split; use the same chronological,
  pre-registered-threshold discipline as Phases 2-4.
- **Qué evidencia independiente haría falta para considerarla válida**: the gap surviving
  volatility-matching across at least two of the three pairs, with a stable sign, AND a concrete,
  falsifiable causal mechanism proposed (e.g. "1AM's feeder-candle construction produces
  systematically tighter/wider stops relative to realized volatility") that could itself be checked
  against the detector's own 1AM signal-generation code -- not just a fourth re-observation of the
  same correlation.

**Not evaluated this phase**, per the explicit instruction: no comparison was run against post-SL
movement to test this hypothesis. It is a recommendation for Phase 5, nothing more.

If the evidence from Phase 4 alone had NOT pointed anywhere consistent, the honest statement would
be: no hypothesis is yet justified beyond "keep collecting descriptive evidence." That is not the
case here -- the 1AM/9AM pattern has earned a dedicated look.

---

# Deliverable G — Checkpoint

## Files created this phase

- `features/pre_entry_features.py` (Layer A), `behavior/pre_stop_trajectory.py` (Layer B),
  `failure_modes/taxonomy.py` (Layer-B classification), `stats/failure_mode_atlas.py`
  (orchestration, Deliverable D).
- `tests/test_pre_entry_features.py` (6), `tests/test_pre_stop_trajectory.py` (9),
  `tests/test_failure_mode_taxonomy.py` (5), `tests/test_phase4_requirements.py` (3) -- 23 new tests.
- `docs/22` (design/pre-registration) through `docs/28` (this document) -- new. `docs/09-21`
  (Phases 1-3.1) **unchanged**, kept as historical reference.

## Tests

Full suite: `uv run --project detector python -m pytest research/loss-pattern-discovery/tests` --
**106 passed** (83 Phase 1-3.1 + 23 new). `uv run lint-imports`: 11/11 contracts kept.

## Reproduction commands

```bash
cd detector
uv run python -m pytest ../research/loss-pattern-discovery/tests
uv run python ../research/loss-pattern-discovery/stats/failure_mode_atlas.py
```

## Coverage and ambiguity summary

- 2047 total executed trades processed for Layer A (778 win / 1265 loss / 4 open); 100% pre-entry
  feature coverage (ATR + recent range), 0 missing-reason flags.
- 1262 eligible confirmed-stop losses processed for Layer B: 79.95% `reconstructible`, 12.76%
  `ambiguous`, 7.29% `insufficient` (20.05% combined cannot support a primary MFE/MAE-pre-SL value).

## SHA

- Base (Phase 3.1): `a030c449f0b65c30ab4b6cbaa620966c557ab169`.
- This phase's commit: `632e06b` (features + trajectory + taxonomy + Atlas), this doc's own SHA
  recorded in the same follow-up-commit pattern used in Phases 3/3.1.

## Open limitations

- L1 (unchanged since Phase 1): no valid-but-never-executed signal table exists; this phase's
  win/loss comparison is executed-trades-only.
- The win/loss pre-entry comparison used medians only, no CI/significance testing (`docs/27-...`,
  finding #9) -- an explicit inconclusive result, not a confirmed null.
- Retracement-from-best-favorable-price is in raw price units, not yet R/ATR-normalized
  (`docs/27-...`, finding #11).
- The 1AM/9AM mechanism (this document's Phase-5 recommendation) remains unexplained across four
  phases now -- proposed, not investigated, this round.
- No model training, RR optimization, or strategy design was performed, per the explicit stop
  instruction for this phase.
