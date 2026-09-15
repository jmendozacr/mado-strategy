"""Result-artifact schema tests using synthetic typed statistics."""

from evaluation.direction import FROZEN_POLICY_IDS
from runner.statistics_bridge import StatisticsResult
from selection.bootstrap import BootstrapResult, CIComputability, ResamplePlan
from selection.estimators import Computability, ESTBResult, InstrumentDelta
from selection.model import Relation
from selection.nomination import (
    IneligibilityReason,
    NominationResult,
    PolicyEligibility,
)
from selection.stratify import PolicyStrata, RelationStratum


def _stratum(relation: Relation, n: int, total_n: int) -> RelationStratum:
    estimable = n > 0
    return RelationStratum(
        relation=relation,
        n=n,
        share=(n / total_n) if total_n else None,
        mean_r=0.4 if estimable else None,
        wr_status=Computability.ESTIMABLE if estimable else Computability.NOT_ESTIMABLE,
        wr=0.5 if estimable else None,
    )


def _statistics_result() -> StatisticsResult:
    strata = {
        policy_id: PolicyStrata(
            policy_id=policy_id,
            total_n=2,
            closed_n=2,
            open_n=0,
            never_filled_n=0,
            closed_aligned=_stratum(Relation.ALIGNED, 1, 2),
            closed_opposed=_stratum(Relation.OPPOSED, 1, 2),
            closed_unresolved=_stratum(Relation.UNRESOLVED, 0, 2),
        )
        for policy_id in FROZEN_POLICY_IDS
    }
    undefined_policy = FROZEN_POLICY_IDS[0]
    est_b_results = {
        policy_id: ESTBResult(
            Computability.NOT_ESTIMABLE if policy_id == undefined_policy else Computability.ESTIMABLE,
            None if policy_id == undefined_policy else 0.25,
        )
        for policy_id in FROZEN_POLICY_IDS
    }
    bootstrap_results = {
        policy_id: BootstrapResult(
            CIComputability.NOT_COMPUTABLE if policy_id == undefined_policy else CIComputability.COMPUTABLE,
            None if policy_id == undefined_policy else 0.01,
            None if policy_id == undefined_policy else 0.49,
        )
        for policy_id in FROZEN_POLICY_IDS
    }
    instrument_deltas = {
        policy_id: (
            InstrumentDelta("EURUSDm", Computability.NOT_ESTIMABLE, None),
            InstrumentDelta("GBPUSDm", Computability.ESTIMABLE, -0.20),
        )
        if policy_id == undefined_policy
        else (InstrumentDelta("EURUSDm", Computability.ESTIMABLE, 0.10),)
        for policy_id in FROZEN_POLICY_IDS
    }
    eligibilities = tuple(
        PolicyEligibility(
            policy_id=policy_id,
            eligible=False if policy_id == undefined_policy else True,
            reasons=(
                IneligibilityReason.EST_B_NOT_ESTIMABLE,
                IneligibilityReason.CI_NOT_COMPUTABLE,
                IneligibilityReason.INSTRUMENT_VETO,
            )
            if policy_id == undefined_policy
            else (),
            est_b_point=est_b_results[policy_id].point,
            ci_lower=bootstrap_results[policy_id].lower,
            ci_upper=bootstrap_results[policy_id].upper,
        )
        for policy_id in FROZEN_POLICY_IDS
    )
    plan = ResamplePlan(
        instruments=("EURUSDm", "GBPUSDm"),
        universes={"EURUSDm": (("EURUSDm", 0, 1, 2),), "GBPUSDm": ()},
        draws=(),
    )
    return StatisticsResult(
        strata=strata,
        est_b_results=est_b_results,
        bootstrap_results=bootstrap_results,
        instrument_deltas=instrument_deltas,
        eligibilities=eligibilities,
        nomination=NominationResult(None, eligibilities),
        plan=plan,
    )


def test_policy_summary_marks_undefined_values_and_cost_model_explicitly():
    from runner.artifacts import build_policy_summary

    summary = build_policy_summary(_statistics_result())
    undefined = summary[FROZEN_POLICY_IDS[0]]

    assert undefined["est_b"] == {"status": "NOT_ESTIMABLE", "point": None}
    assert undefined["ci"] == {"status": "NOT_COMPUTABLE", "lower": None, "upper": None}
    assert undefined["instrument_deltas"][0] == {
        "instrument": "EURUSDm",
        "status": "NOT_ESTIMABLE",
        "point": None,
    }
    unresolved = undefined["strata"]["UNRESOLVED"]
    assert unresolved["mean_r"] is None
    assert unresolved["mean_r_status"] == "NOT_ESTIMABLE"
    assert unresolved["wr"] is None
    assert unresolved["wr_status"] == "NOT_ESTIMABLE"
    assert undefined["label"] == "frictionless label, not net economic validation"
    assert undefined["trading_cost_price"] == 0.0
    assert undefined["cost_model"] == {
        "execution": "frictionless",
        "spread": "unmodeled",
        "commission": "unmodeled",
        "slippage": "unmodeled",
    }


def test_nomination_trace_records_each_sel_a_condition_and_per_instrument_delta():
    from runner.artifacts import build_nomination_trace

    trace = build_nomination_trace(_statistics_result())
    conditions = trace["policies"][FROZEN_POLICY_IDS[0]]["conditions"]

    assert conditions["est_b_computable"] == {
        "evaluated_value": "NOT_ESTIMABLE",
        "passed": False,
    }
    assert conditions["est_b_at_least_mei"] == {
        "evaluated_value": None,
        "value_status": "NOT_ESTIMABLE",
        "passed": False,
    }
    assert conditions["ci_computable"] == {
        "evaluated_value": "NOT_COMPUTABLE",
        "passed": False,
    }
    assert conditions["ci_lower_positive"] == {
        "evaluated_value": None,
        "value_status": "NOT_COMPUTABLE",
        "passed": False,
    }
    assert conditions["instrument_delta_guard"] == {
        "evaluated_value": [
            {
                "instrument": "EURUSDm",
                "status": "NOT_ESTIMABLE",
                "point": None,
                "passed": True,
            },
            {
                "instrument": "GBPUSDm",
                "status": "ESTIMABLE",
                "point": -0.20,
                "passed": False,
            },
        ],
        "passed": False,
    }
    assert conditions["data_quality_checks_passed"] == {
        "evaluated_value": True,
        "passed": True,
    }
    assert trace["nominee"] == "NO POLICY NOMINATED"
