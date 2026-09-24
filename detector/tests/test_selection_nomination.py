"""SEL-A eligibility, ranking, and nomination (REQ-STAT-13..17). Each
condition is exercised independently against directly-constructed
`ESTBResult`/`BootstrapResult`/`InstrumentDelta` value objects so a failure
reason can never be conflated with another (Group R's requirement)."""

import pytest

from selection.bootstrap import BootstrapResult, CIComputability
from selection.estimators import Computability, ESTBResult, InstrumentDelta
from selection.nomination import IneligibilityReason, evaluate_eligibility, nominate

_COMPUTABLE_DELTA = InstrumentDelta(instrument="EURUSDm", status=Computability.ESTIMABLE, point=0.5)


def _eligibility_inputs(
    est_b_point=0.30,
    est_b_status=Computability.ESTIMABLE,
    ci_status=CIComputability.COMPUTABLE,
    ci_lower=0.05,
    ci_upper=0.60,
    deltas=(_COMPUTABLE_DELTA,),
):
    est_b = ESTBResult(status=est_b_status, point=est_b_point)
    bootstrap = BootstrapResult(ci_status=ci_status, lower=ci_lower, upper=ci_upper)
    return est_b, bootstrap, deltas


# --- Group O: MEI exact boundary ---------------------------------------------


def test_est_b_just_below_mei_fails():
    est_b, bootstrap, deltas = _eligibility_inputs(est_b_point=0.19999999999)
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert not result.eligible
    assert IneligibilityReason.BELOW_MEI in result.reasons


def test_est_b_exactly_at_mei_passes_that_condition():
    est_b, bootstrap, deltas = _eligibility_inputs(est_b_point=0.20)
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert IneligibilityReason.BELOW_MEI not in result.reasons


def test_est_b_above_mei_passes_that_condition():
    est_b, bootstrap, deltas = _eligibility_inputs(est_b_point=0.21)
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert IneligibilityReason.BELOW_MEI not in result.reasons


def test_est_b_not_estimable_fails_independently_of_mei():
    est_b, bootstrap, deltas = _eligibility_inputs(est_b_status=Computability.NOT_ESTIMABLE, est_b_point=None)
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert not result.eligible
    assert IneligibilityReason.EST_B_NOT_ESTIMABLE in result.reasons
    assert IneligibilityReason.BELOW_MEI not in result.reasons


# --- Group P: simultaneous CI lower bound, strict > 0 ------------------------


def test_ci_lower_positive_passes():
    est_b, bootstrap, deltas = _eligibility_inputs(ci_lower=0.01)
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert IneligibilityReason.CI_LOWER_NOT_POSITIVE not in result.reasons


def test_ci_lower_exactly_zero_fails():
    est_b, bootstrap, deltas = _eligibility_inputs(ci_lower=0.0)
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert IneligibilityReason.CI_LOWER_NOT_POSITIVE in result.reasons


def test_ci_lower_negative_fails():
    est_b, bootstrap, deltas = _eligibility_inputs(ci_lower=-0.01)
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert IneligibilityReason.CI_LOWER_NOT_POSITIVE in result.reasons


def test_ci_not_computable_fails_independently_of_lower_bound():
    est_b, bootstrap, deltas = _eligibility_inputs(ci_status=CIComputability.NOT_COMPUTABLE, ci_lower=None, ci_upper=None)
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert IneligibilityReason.CI_NOT_COMPUTABLE in result.reasons
    assert IneligibilityReason.CI_LOWER_NOT_POSITIVE not in result.reasons


# --- Group Q: instrument veto -------------------------------------------------


def test_instrument_delta_above_threshold_no_veto():
    deltas = (InstrumentDelta(instrument="EURUSDm", status=Computability.ESTIMABLE, point=-0.1999),)
    est_b, bootstrap, _ = _eligibility_inputs()
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert IneligibilityReason.INSTRUMENT_VETO not in result.reasons


def test_instrument_delta_exactly_at_threshold_vetoes():
    deltas = (InstrumentDelta(instrument="EURUSDm", status=Computability.ESTIMABLE, point=-0.20),)
    est_b, bootstrap, _ = _eligibility_inputs()
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert IneligibilityReason.INSTRUMENT_VETO in result.reasons


def test_instrument_delta_below_threshold_vetoes():
    deltas = (InstrumentDelta(instrument="EURUSDm", status=Computability.ESTIMABLE, point=-0.21),)
    est_b, bootstrap, _ = _eligibility_inputs()
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert IneligibilityReason.INSTRUMENT_VETO in result.reasons


def test_non_computable_instrument_delta_does_not_veto():
    deltas = (InstrumentDelta(instrument="EURUSDm", status=Computability.NOT_ESTIMABLE, point=None),)
    est_b, bootstrap, _ = _eligibility_inputs()
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert IneligibilityReason.INSTRUMENT_VETO not in result.reasons
    assert result.eligible


# --- Group R: full eligibility, all conditions pass --------------------------


def test_all_conditions_passing_is_eligible():
    est_b, bootstrap, deltas = _eligibility_inputs()
    result = evaluate_eligibility("P1", est_b, bootstrap, deltas)
    assert result.eligible
    assert result.reasons == ()


# --- Group S/T/U: SEL-A nomination -------------------------------------------


def test_one_eligible_policy_is_nominated():
    eligibilities = [
        evaluate_eligibility("P1", ESTBResult(Computability.ESTIMABLE, 0.30), BootstrapResult(CIComputability.COMPUTABLE, 0.05, 0.9), (_COMPUTABLE_DELTA,)),
        evaluate_eligibility("P2", ESTBResult(Computability.NOT_ESTIMABLE, None), BootstrapResult(CIComputability.NOT_COMPUTABLE, None, None), ()),
    ]
    result = nominate(eligibilities)
    assert result.nominee == "P1"


def test_zero_eligible_yields_no_policy_nominated():
    eligibilities = [
        evaluate_eligibility("P1", ESTBResult(Computability.NOT_ESTIMABLE, None), BootstrapResult(CIComputability.NOT_COMPUTABLE, None, None), ()),
        evaluate_eligibility("P2", ESTBResult(Computability.NOT_ESTIMABLE, None), BootstrapResult(CIComputability.NOT_COMPUTABLE, None, None), ()),
    ]
    result = nominate(eligibilities)
    assert result.nominee is None


def test_multiple_eligible_highest_lower_bound_wins():
    eligibilities = [
        evaluate_eligibility("P1", ESTBResult(Computability.ESTIMABLE, 0.30), BootstrapResult(CIComputability.COMPUTABLE, 0.05, 0.9), (_COMPUTABLE_DELTA,)),
        evaluate_eligibility("P2", ESTBResult(Computability.ESTIMABLE, 0.40), BootstrapResult(CIComputability.COMPUTABLE, 0.15, 0.9), (_COMPUTABLE_DELTA,)),
    ]
    result = nominate(eligibilities)
    assert result.nominee == "P2"


def test_exact_tie_yields_no_policy_nominated():
    eligibilities = [
        evaluate_eligibility("P1", ESTBResult(Computability.ESTIMABLE, 0.30), BootstrapResult(CIComputability.COMPUTABLE, 0.123456789, 0.9), (_COMPUTABLE_DELTA,)),
        evaluate_eligibility("P2", ESTBResult(Computability.ESTIMABLE, 0.30), BootstrapResult(CIComputability.COMPUTABLE, 0.123456789, 0.9), (_COMPUTABLE_DELTA,)),
    ]
    result = nominate(eligibilities)
    assert result.nominee is None


def test_near_tie_not_exactly_equal_still_nominates_the_higher():
    eligibilities = [
        evaluate_eligibility("P1", ESTBResult(Computability.ESTIMABLE, 0.30), BootstrapResult(CIComputability.COMPUTABLE, 0.123456788, 0.9), (_COMPUTABLE_DELTA,)),
        evaluate_eligibility("P2", ESTBResult(Computability.ESTIMABLE, 0.30), BootstrapResult(CIComputability.COMPUTABLE, 0.123456789, 0.9), (_COMPUTABLE_DELTA,)),
    ]
    result = nominate(eligibilities)
    assert result.nominee == "P2"


def test_non_computable_ci_policy_is_never_nominated_but_reports_point():
    eligibilities = [
        evaluate_eligibility("P1", ESTBResult(Computability.ESTIMABLE, 0.99), BootstrapResult(CIComputability.NOT_COMPUTABLE, None, None), (_COMPUTABLE_DELTA,)),
    ]
    result = nominate(eligibilities)
    assert result.nominee is None
    assert eligibilities[0].est_b_point == pytest.approx(0.99)
    assert not eligibilities[0].eligible
