"""Explicit coverage map for Phase 4's 15 required proofs (section 12 of the
user's brief). Most are covered by tests in test_pre_entry_features.py,
test_pre_stop_trajectory.py and test_failure_mode_taxonomy.py; the three
not naturally covered there are implemented in this file.

 1. Win/loss with identical pre-entry history processed identically -> test_pre_entry_features.py::test_win_and_loss_with_identical_pre_entry_history_produce_identical_features
 2. A future candle never modifies a pre-entry feature              -> test_pre_entry_features.py::test_future_candle_does_not_affect_pre_entry_feature
 3. The entry bar contributes no not-yet-observable information     -> test_pre_entry_features.py::test_entry_bar_itself_not_used_in_recent_range
 4. The SL bar never retroactively contributes earlier extremes     -> test_pre_stop_trajectory.py::test_exit_bar_does_not_retroactively_contribute_to_primary_mfe
 5. MFE/MAE respect buy/sell                                        -> test_pre_stop_trajectory.py::test_mfe_mae_respect_bearish_direction
 6. Zero/invalid risk never produces a misleading division          -> test_pre_entry_features.py::test_zero_risk_does_not_divide_misleadingly, test_pre_stop_trajectory.py::test_zero_risk_price_no_misleading_division
 7. A gap preserves the real executed price, not the planned one    -> test_pre_stop_trajectory.py::test_gap_uses_actual_executed_exit_price_not_planned_stop_loss
 8. Ambiguous events never receive an artificially confident class  -> test_failure_mode_taxonomy.py::test_unknown_excursion_when_path_not_reconstructible
 9. Censored events never automatically become failures             -> THIS FILE: test_open_censored_events_are_never_included_as_failure_paths
10. NY conversion respects EST/EDT                                  -> THIS FILE: test_ny_hour_and_weekday_cross_a_dst_boundary_correctly
11. Classification is deterministic                                 -> test_failure_mode_taxonomy.py::test_classification_is_deterministic
12. A post-SL change never changes the taxonomy                     -> test_pre_stop_trajectory.py::test_post_sl_changes_never_affect_the_trajectory_or_taxonomy
13. Extraction never modifies the original CSVs                     -> THIS FILE: test_source_files_untouched_by_phase4_pipeline
14. Multidimensional categories are not confused with exclusive ones -> test_failure_mode_taxonomy.py::test_dimensions_vary_independently_not_as_one_exclusive_label
15. Identical data/config reproduce identical results                -> test_pre_entry_features.py::test_deterministic_for_identical_inputs, test_pre_stop_trajectory.py::test_deterministic_for_identical_inputs
"""
from __future__ import annotations

import datetime as dt
import hashlib
from pathlib import Path

from common.ny_time import to_ny
from eligibility.stop_eligibility import StopEligibility, classify_all
from extract.from_causal_lookahead_audit import SOURCE_RELATIVE_PATH, extract
from schema.events import Outcome

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def test_open_censored_events_are_never_included_as_failure_paths():
    records = extract(REPO_ROOT)
    results = classify_all(records)
    eligible_ids = {
        r.identification.event_id
        for r in records
        if results.get(r.identification.event_id) is not None
        and results[r.identification.event_id].category
        in (StopEligibility.CONFIRMED_STOP, StopEligibility.STOP_AFTER_PARTIAL)
    }
    open_ids = {r.identification.event_id for r in records if r.operation.outcome is Outcome.OPEN}
    ambiguous_ids = {
        r.identification.event_id
        for r in records
        if results.get(r.identification.event_id) is not None
        and results[r.identification.event_id].category is StopEligibility.AMBIGUOUS_STOP
    }
    assert eligible_ids.isdisjoint(open_ids)
    assert eligible_ids.isdisjoint(ambiguous_ids)
    assert open_ids  # sanity: the dataset really does have censored events to exclude
    assert ambiguous_ids  # sanity: the dataset really does have ambiguous events to exclude


def test_ny_hour_and_weekday_cross_a_dst_boundary_correctly():
    # 2026-03-08 is the US DST "spring forward" Sunday (2nd Sunday of
    # March): 06:00 UTC the day before is EST (UTC-5) -> 01:00 NY; 06:00
    # UTC the day after is EDT (UTC-4) -> 02:00 NY. A naive fixed-offset
    # conversion would get one of these wrong.
    before = to_ny(dt.datetime(2026, 3, 7, 6, 0))
    after = to_ny(dt.datetime(2026, 3, 9, 6, 0))
    assert before.hour == 1
    assert after.hour == 2
    assert before.weekday() == 5  # Saturday
    assert after.weekday() == 0  # Monday


def test_source_files_untouched_by_phase4_pipeline():
    source_path = REPO_ROOT / SOURCE_RELATIVE_PATH
    before = hashlib.sha256(source_path.read_bytes()).hexdigest()
    records = extract(REPO_ROOT)
    classify_all(records)
    after = hashlib.sha256(source_path.read_bytes()).hexdigest()
    assert before == after
