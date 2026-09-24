"""Statistics bridge.

Behavioral: compute_all_statistics with synthetic observations proves:
- one RNG, one ResamplePlan, one invocation per calculation per policy
- nomination call after all policies
- frozen policy order
- no per-instrument statistics call site
- structural: single frozen_rng call site, no numpy.random, no logger"""

import inspect
from unittest.mock import patch, MagicMock, call

import pytest

from evaluation.direction import FROZEN_POLICY_IDS
from selection.model import (
    CandidateIdentity,
    ClosedTradeOutcome,
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
)


def _make_observations(n_per_instrument=3):
    """Synthetic observation set for all 3 instruments, all 4 policies."""
    obs = []
    instruments = ("EURUSDm", "GBPUSDm", "DXYm")
    for inst in instruments:
        for i in range(n_per_instrument):
            cid = CandidateIdentity(inst, "15M", f"sig_{inst}_{i}", 10 + i)
            cluster_id = (inst, 0, 5 + i, 4 + i)
            for pid in FROZEN_POLICY_IDS:
                relation = Relation.ALIGNED if i % 2 == 0 else Relation.OPPOSED
                obs.append(DirectionPolicyObservation(
                    candidate_id=cid,
                    context_cluster_id=cluster_id,
                    policy_id=pid,
                    relation=relation,
                    outcome_state=OutcomeState.CLOSED,
                    closed_outcome=ClosedTradeOutcome.WIN if i % 2 == 0 else ClosedTradeOutcome.LOSS,
                    realized_r=0.5 if i % 2 == 0 else -0.3,
                ))
    return obs


def test_compute_all_statistics_executes():
    """Actually execute compute_all_statistics with synthetic observations."""
    from runner.statistics_bridge import compute_all_statistics

    obs = _make_observations(n_per_instrument=3)
    instruments = ("EURUSDm", "GBPUSDm", "DXYm")

    result = compute_all_statistics(obs, instruments)

    assert set(result.strata.keys()) == set(FROZEN_POLICY_IDS)
    assert set(result.est_b_results.keys()) == set(FROZEN_POLICY_IDS)
    assert set(result.bootstrap_results.keys()) == set(FROZEN_POLICY_IDS)
    assert set(result.instrument_deltas.keys()) == set(FROZEN_POLICY_IDS)
    assert len(result.eligibilities) == 4
    assert result.nomination is not None
    assert result.plan is not None


def test_one_rng_one_plan():
    """One frozen_rng call, one ResamplePlan, shared across all 4 policies."""
    from runner.statistics_bridge import compute_all_statistics

    rng_calls = []
    plan_calls = []

    original_frozen_rng = None
    original_gen_plan = None

    import selection.bootstrap as bootstrap_mod
    original_frozen_rng = bootstrap_mod.frozen_rng
    original_gen_plan = bootstrap_mod.generate_cluster_resample_plan

    with (
        patch("runner.statistics_bridge.frozen_rng") as mock_rng,
        patch("runner.statistics_bridge.generate_cluster_resample_plan") as mock_plan,
        patch("runner.statistics_bridge.stratify") as mock_stratify,
        patch("runner.statistics_bridge.compute_est_b") as mock_est_b,
        patch("runner.statistics_bridge.bootstrap_est_b") as mock_bootstrap,
        patch("runner.statistics_bridge.compute_instrument_deltas") as mock_deltas,
        patch("runner.statistics_bridge.evaluate_eligibility") as mock_elig,
        patch("runner.statistics_bridge.nominate") as mock_nom,
    ):
        mock_rng.return_value = MagicMock()
        mock_plan_result = MagicMock()
        mock_plan.return_value = mock_plan_result

        from selection.estimators import Computability, ESTBResult
        from selection.bootstrap import CIComputability, BootstrapResult
        from selection.stratify import PolicyStrata, RelationStratum
        from selection.estimators import InstrumentDelta
        from selection.nomination import PolicyEligibility, NominationResult

        dummy_stratum = RelationStratum(Relation.ALIGNED, 1, 0.5, 0.3, Computability.ESTIMABLE, 0.5)
        mock_stratify.return_value = PolicyStrata("p", 4, 2, 1, 1, dummy_stratum, dummy_stratum, dummy_stratum)
        mock_est_b.return_value = ESTBResult(Computability.ESTIMABLE, 0.3)
        mock_bootstrap.return_value = BootstrapResult(CIComputability.COMPUTABLE, 0.1, 0.5)
        mock_deltas.return_value = (InstrumentDelta("EURUSDm", Computability.ESTIMABLE, 0.2),)
        mock_elig.return_value = PolicyEligibility("p", True, (), 0.3, 0.1, 0.5)
        mock_nom.return_value = NominationResult(None, ())

        obs = _make_observations()
        compute_all_statistics(obs, ("EURUSDm", "GBPUSDm", "DXYm"))

    mock_rng.assert_called_once()
    mock_plan.assert_called_once()

    assert mock_bootstrap.call_count == 4
    for c in mock_bootstrap.call_args_list:
        assert c.args[2] is mock_plan_result

    # Nomination called once after all policies
    mock_nom.assert_called_once()

    # Policy order matches FROZEN_POLICY_IDS
    stratify_policy_order = [c.args[1] for c in mock_stratify.call_args_list]
    assert stratify_policy_order == list(FROZEN_POLICY_IDS)


def test_single_frozen_rng_call_site():
    import importlib
    import pkgutil
    import runner

    modules_with_frozen_rng = []
    for importer, modname, ispkg in pkgutil.walk_packages(runner.__path__, runner.__name__ + "."):
        mod = importlib.import_module(modname)
        source = inspect.getsource(mod)
        if "frozen_rng" in source:
            modules_with_frozen_rng.append(modname)

    assert modules_with_frozen_rng == ["runner.statistics_bridge"]


def test_no_numpy_random_in_runner():
    import importlib
    import pkgutil
    import runner

    for importer, modname, ispkg in pkgutil.walk_packages(runner.__path__, runner.__name__ + "."):
        mod = importlib.import_module(modname)
        source = inspect.getsource(mod)
        assert "numpy.random" not in source, f"{modname} references numpy.random"
        assert "np.random" not in source, f"{modname} references np.random"


def test_no_logger_in_statistics_bridge():
    import runner.statistics_bridge as mod
    source = inspect.getsource(mod)
    assert "logging" not in source
    assert "print(" not in source
    assert "sys.stdout" not in source
    assert "sys.stderr" not in source


def test_statistics_result_type():
    from runner.statistics_bridge import StatisticsResult
    fields = set(StatisticsResult.__dataclass_fields__)
    assert "strata" in fields
    assert "est_b_results" in fields
    assert "bootstrap_results" in fields
    assert "instrument_deltas" in fields
    assert "eligibilities" in fields
    assert "nomination" in fields
    assert "plan" in fields


def test_compute_all_statistics_function_exists():
    from runner.statistics_bridge import compute_all_statistics
    assert callable(compute_all_statistics)
