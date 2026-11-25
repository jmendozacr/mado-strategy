"""Phase 9 Unit D: Stage-6 candidate attrition, per model.

`detector/backtest/population.py::build_stage6_population` is a thin
orchestrator over five sub-functions, in a FIXED sequential order:
`_population_cuts` -> `_build_candidate` -> `_dedup` -> `_kill_zone_cut` ->
`_rr_floor_cut`. It returns only the FINAL survivor list plus aggregate
counts (`Stage6Population.excluded_*`) -- never which model a removed
candidate belonged to, nor the intermediate population at each step.

This module calls the SAME five sub-functions, UNMODIFIED, in the SAME
order, with the SAME config -- never a different rule, never reordered --
and additionally records which `signal_id` was removed at each step, for
model attribution via `model_by_sig` (never guessed). The two structural
facts below are PROVEN by reading `experimental/htf_trigger_1am_9am_backtest.py`'s
`SYMBOL_CONFIG` and this pipeline's own AlignedSignal construction, not
assumed from the rule merely existing in the code (the brief's own
"disponible" vs. "activa" vs. "aplicada" vs. "responsable" distinction):

1. **`_population_cuts`'s five exclusion categories are structurally
   impossible for D3/C2** (RULE AVAILABLE, NEVER ACTIVE for this pipeline):
   - `excluded_no_crt_range` requires `confirmation_type=="fvg_fill"` --
     `causal_anchor_v2.py`'s `_track_anchor` calls are always hardcoded to
     `"purge_engulf"`; D3/C2 never produces an `fvg_fill` signal.
   - `excluded_unaligned` requires `tagged.aligned != "aligned"` --
     `causal_anchor_v2.build_causal_signal_v2` always constructs
     `AlignedSignal(..., aligned="aligned", ...)` literally.
   - `excluded_never_confirmed` requires `signal.status ==
     DetectionStatus.INVALIDATED` -- but `aligned_signals` passed into
     `build_stage6_population` are filtered to `rec.aligned is not None`,
     which `build_causal_signal_v2` only ever sets when
     `signal.status == DetectionStatus.CONFIRMED` (never INVALIDATED).
   - `excluded_confirmed_no_retest` requires `signal.retest_index is
     None` -- but `entries/model1.py::_track_anchor` only returns
     `DetectionStatus.CONFIRMED` via a code path that requires
     `retest_index is not None` as a precondition.
   - `excluded_no_key_level` requires `tagged.key_level is None` -- but
     `causal_anchor_v2.py`'s `CausalTrigger.credited_level` is a
     non-Optional field, only ever constructed (in
     `causal_intrabar.detect_sweep_and_key_level`) when a credited level
     was actually found.
   Verified empirically against real data by this module's own
   `verify_population_cuts_are_zero`, not just asserted.
2. **`_kill_zone_cut` is RULE AVAILABLE but NOT ACTIVE** for D3/C2:
   `SYMBOL_CONFIG[...].kill_zone_gated == False` for EURUSD/USDCAD/AUDUSD
   (`experimental/htf_trigger_1am_9am_backtest.py`), and
   `_kill_zone_cut`'s own condition is
   `config.backtest.kill_zone_gated and not in_ny_kill_zone(...)` --
   short-circuits to `False` (never excludes) whenever the flag is off.
3. **`_dedup` and `_rr_floor_cut` (`min_risk_reward=2.0`) are RULE ACTIVE
   AND RULE APPLIED** for D3/C2 -- these are the only two mechanisms that
   can plausibly explain the `model1_confirmed` -> `candidates_built` gap,
   verified per-model below.

Terminal-reason discipline (never double-counting an overlapping cause):
each candidate is evaluated through the SAME fixed sequence the real
pipeline uses; once removed at one step, it is never evaluated again at a
later step -- a candidate dropped by `_dedup` is never also "responsible"
for an RR-floor rejection, because it never reaches that stage.
"""
from __future__ import annotations

import sys
from collections import Counter
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
DETECTOR_ROOT = REPO_ROOT / "detector"
for _path in (LAB_ROOT, DETECTOR_ROOT):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from backtest.population import (  # noqa: E402
    Stage6Population,
    _build_candidate,
    _dedup,
    _kill_zone_cut,
    _population_cuts,
    _rr_floor_cut,
)
from primitives.swing import detect_swings  # noqa: E402


def build_stage6_population_instrumented(aligned_signals, ltf_series, config, swings=None, model_by_sig=None):
    """Mirrors `build_stage6_population` EXACTLY (same five sub-calls,
    same order, same config) -- the returned `population` field must be
    identical to calling the real function directly (asserted by
    `tests/test_stage6_attrition_diagnostics.py`'s equivalence test).
    `model_by_sig` is this lab's own already-built mapping (never
    reconstructed differently) -- `None` is allowed and simply skips
    model attribution (counts stay pooled, matching the original)."""
    model_by_sig = model_by_sig or {}
    cuts = _population_cuts(aligned_signals)
    swings = swings if swings is not None else detect_swings(ltf_series, config.swing)
    indices = [s.index for s in swings]
    candidates = [
        _build_candidate(tagged, swings, indices, ltf_series, config.backtest) for tagged in cuts.survivors
    ]
    pre_dedup_ids = {c.signal_id for c in candidates}

    candidates, excluded_duplicate = _dedup(candidates)
    post_dedup_ids = {c.signal_id for c in candidates}
    removed_dedup = pre_dedup_ids - post_dedup_ids

    candidates, excluded_kill_zone = _kill_zone_cut(candidates, ltf_series.candles, config)
    post_kill_zone_ids = {c.signal_id for c in candidates}
    removed_kill_zone = post_dedup_ids - post_kill_zone_ids

    candidates, excluded_rr_floor = _rr_floor_cut(candidates, config.backtest.min_risk_reward)
    post_rr_ids = {c.signal_id for c in candidates}
    removed_rr_floor = post_kill_zone_ids - post_rr_ids

    population = Stage6Population(
        series=ltf_series, candidates=candidates,
        excluded_no_crt_range=cuts.no_crt_range, excluded_unaligned=cuts.unaligned,
        excluded_never_confirmed=cuts.never_confirmed, excluded_no_key_level=cuts.no_key_level,
        excluded_duplicate=excluded_duplicate, excluded_kill_zone=excluded_kill_zone,
        excluded_rr_floor=excluded_rr_floor, excluded_confirmed_no_retest=cuts.confirmed_no_retest,
    )

    def _by_model(signal_ids):
        return dict(Counter(model_by_sig.get(sid, "unknown") for sid in signal_ids))

    removed_by_model = {
        "duplicate": _by_model(removed_dedup),
        "kill_zone": _by_model(removed_kill_zone),
        "rr_floor": _by_model(removed_rr_floor),
    }
    return population, removed_by_model


def verify_population_cuts_are_zero(population: Stage6Population) -> dict:
    """The 5 structurally-impossible-for-D3/C2 categories, checked against
    real data -- never just assumed from the analytical proof above."""
    values = {
        "excluded_no_crt_range": population.excluded_no_crt_range,
        "excluded_unaligned": population.excluded_unaligned,
        "excluded_never_confirmed": population.excluded_never_confirmed,
        "excluded_no_key_level": population.excluded_no_key_level,
        "excluded_confirmed_no_retest": population.excluded_confirmed_no_retest,
    }
    return {"values": values, "all_zero": all(v == 0 for v in values.values())}
