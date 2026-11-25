# Deliverable H — Technical Checkpoint (Phase 6)

## Files created

- `docs/37-phase6-design-and-pre-registration.md` -- Deliverable A (execution semantics audit) +
  pre-registration of the E0-E4 taxonomy, S0-S3 scenarios, and verdict criteria.
- `eligibility/stop_timing_decomposition.py` -- `TimingCategory`, `classify_timing`,
  `classify_all_timing` (E0/E1/E2/E3/E4).
- `eligibility/intrabar_ambiguity.py` -- `IntrabarUncertainty`, `classify_intrabar_uncertainty`,
  `classify_all_intrabar_uncertainty` (sequence-verifiable / engine-conservative-same-bar /
  same-bar-multi-level-ambiguity / gap-affected / insufficient-evidence).
- `stats/stop_timing_decomposition.py` -- Deliverable B (decomposition table + identity checks).
- `stats/intrabar_uncertainty_report.py` -- Deliverable C (intrabar uncertainty counts).
- `stats/sensitivity_scenarios.py` -- Deliverable D (S0-S3).
- `docs/38-early-stop-decomposition.md`, `docs/39-intrabar-uncertainty-report.md`,
  `docs/40-sensitivity-analysis.md`, `docs/41-model-construction-audit.md`,
  `docs/42-research-verdict-phase6.md`, `docs/43-phase7-recommendation.md`, this file.
- `tests/test_stop_timing_decomposition.py` (10 tests), `tests/test_intrabar_ambiguity.py`
  (11 tests), `tests/test_sensitivity_scenarios.py` (7 tests), `tests/test_phase6_requirements.py`
  (1 test + coverage-map docstring for all 18 required proofs) -- 29 new tests.

## Tests

150 tests passing (121 prior + 29 new), `lint-imports` 11/11 contracts kept. No existing test
modified, skipped, or deleted to reach green. `test_source_files_untouched_by_phase6_pipeline` hashes
the source ledger, `detector/backtest/simulate.py`, and
`audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py`/`run_c1_c2.py` before and after running
the full Phase 6 pipeline -- unchanged.

## Reproduce

```bash
cd detector
uv run python ../research/loss-pattern-discovery/stats/stop_timing_decomposition.py      # B
uv run python ../research/loss-pattern-discovery/stats/intrabar_uncertainty_report.py    # C
uv run python ../research/loss-pattern-discovery/stats/sensitivity_scenarios.py          # D
uv run pytest ../research/loss-pattern-discovery/tests -q
uv run lint-imports
```

## Main results (summary; full detail in docs/37-43)

- **A**: the real ledger comes from `causal_intrabar.py::fill_pass_c` (fill-eligibility fix) +
  `simulate.py::_resolve_exits` (unmodified SL/TP/partial resolution) -- not a raw `simulate()` call,
  a correction to the brief's own premise, verified before anything else.
- **B**: `Gap_early` (+9.35pp) = `Gap_E0` (+3.97pp, CI [1.79, 6.27], below the 5pp bar) +
  `Gap_E1` (+5.38pp, CI [2.52, 8.26], clears the 5pp bar on its own). Identity verified exactly.
- **C**: 91.5% (9AM) / 84.4% (1AM) of same-bar events are sequence-verifiable from OHLC alone, not
  genuinely ambiguous. Zero same-bar-multi-level-ambiguity events within confirmed stops (verified,
  not assumed -- already excluded upstream by Phase 2's own eligibility taxonomy).
- **D**: S0-S3 all land in an 8.50-9.35pp band; S1 (zero-ambiguity component) alone is +5.38pp,
  CI [2.52, 8.26].
- **E**: the only verified structural difference between 1AM/9AM is confirmation-window timing
  (2h vs. 1h30m); entry/SL/invalidation rules are shared, unmodified Model-1 code. Trading cost does
  not affect SL-touch timing (verified from `simulate.py`'s own `sl_touched` expression).

## Sample-size changes vs. Phase 5

None. Same primary population (2043 evaluable executed trades: 619 1AM, 1424 9AM), same
`is_confirmed_stop`/`compute_trade_timing` definitions. S3 additionally reports an 11-event (7 1AM,
4 9AM) exclusion for its own restricted comparison, never substituted for the full population.

## Limitations

- The confirmation-window-timing difference (Deliverable E) is named as a candidate, not tested as
  a cause -- Phase 7's recommended next step, not evaluated this phase.
- The sequence-verifiable criterion (Unit C) assumes continuous intrabar price movement (no
  mid-bar jump) -- a standard assumption, stated explicitly, not verified against tick data (none
  exists in this dataset).
- `origin_model` remains observational, not randomly assigned -- Phase 6's verdict is an
  association that survived this specific execution-semantics audit, not a causal claim.
- 2015-2026 remains previously-examined, not genuine out-of-sample, regardless of this phase's
  findings.

## Commits

See `docs/45-phase6-commit-record.md` for the exact commit SHA once pushed.
