from behavior.pre_stop_trajectory import PathIntegrity, PreStopTrajectory
from failure_modes.taxonomy import ExcursionClass, classify, duration_tercile_labels


def _trajectory(integrity=PathIntegrity.RECONSTRUCTIBLE, duration_bars=2, mfe_r=None, n_observable=1):
    return PreStopTrajectory(
        event_id="e0", integrity=integrity, n_observable_bars=n_observable, duration_bars=duration_bars,
        duration_s=duration_bars * 900.0, time_activation_to_exit_s=None,
        mfe_pre_sl_price=None, mfe_pre_sl_r=mfe_r, mfe_pre_sl_atr=None,
        mae_pre_sl_price=None, mae_pre_sl_atr=None,
        had_material_favorable_excursion=None, retracement_from_best_favorable_price=None,
        pct_bars_closed_favorable=None, pct_bars_closed_adverse=None, avg_adverse_speed_price_per_bar=None,
        mfe_including_entry_bar_r=None, mfe_including_exit_bar_r=None,
    )


def test_dimensions_vary_independently_not_as_one_exclusive_label():
    # Fast + reconstructible + no material excursion.
    fast_no_excursion = classify(_trajectory(duration_bars=2, mfe_r=0.05, n_observable=1))
    # Slow + reconstructible + material excursion.
    slow_material = classify(_trajectory(duration_bars=50, mfe_r=1.5, n_observable=40))
    # Fast + INSUFFICIENT path (zero observable bars) -- a third, distinct combination.
    fast_insufficient = classify(_trajectory(integrity=PathIntegrity.INSUFFICIENT, duration_bars=1,
                                              mfe_r=None, n_observable=0))

    assert fast_no_excursion.excursion_class == ExcursionClass.NONE
    assert slow_material.excursion_class == ExcursionClass.MATERIAL
    assert fast_insufficient.excursion_class == ExcursionClass.UNKNOWN
    # Confirms duration and excursion are independent fields on the SAME
    # classification object, not collapsed into one mutually-exclusive label:
    # two "fast" trajectories here land in two different excursion classes.
    assert fast_no_excursion.duration_bars < slow_material.duration_bars
    assert fast_no_excursion.excursion_class != fast_insufficient.excursion_class


def test_excursion_class_boundaries_reuse_preregistered_thresholds():
    assert classify(_trajectory(mfe_r=0.1)).excursion_class == ExcursionClass.NONE
    assert classify(_trajectory(mfe_r=0.25)).excursion_class == ExcursionClass.PARTIAL
    assert classify(_trajectory(mfe_r=0.99)).excursion_class == ExcursionClass.PARTIAL
    assert classify(_trajectory(mfe_r=1.0)).excursion_class == ExcursionClass.MATERIAL
    assert classify(_trajectory(mfe_r=2.5)).excursion_class == ExcursionClass.MATERIAL


def test_unknown_excursion_when_path_not_reconstructible():
    unreconstructible = classify(_trajectory(integrity=PathIntegrity.INSUFFICIENT, mfe_r=None))
    assert unreconstructible.excursion_class == ExcursionClass.UNKNOWN


def test_duration_terciles_are_labeled_bins_not_a_natural_category():
    durations = [1, 2, 3, 4, 5, 6, 7, 8, 9]
    labels = duration_tercile_labels(durations)
    assert labels[1] == "fast_tercile"
    assert labels[5] == "mid_tercile"
    assert labels[9] == "slow_tercile"
    assert len(set(labels.values())) == 3


def test_classification_is_deterministic():
    t = _trajectory(mfe_r=0.6)
    assert classify(t) == classify(t)
