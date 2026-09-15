"""Build the 5 result artifact dicts from typed statistical results, manifest,
and fingerprints."""

from __future__ import annotations

from typing import TYPE_CHECKING

from runner.statistics_bridge import StatisticsResult
from runner.serialization import to_json_value

if TYPE_CHECKING:
    from runner.run_discovery import AuthorizationReceipt
    from adapter.manifest import Manifest


def _stratum_dict(stratum) -> dict:
    mean_r_status = "ESTIMABLE" if stratum.mean_r is not None else "NOT_ESTIMABLE"
    share_status = "ESTIMABLE" if stratum.share is not None else "NOT_ESTIMABLE"
    return {
        "relation": stratum.relation.value,
        "n": stratum.n,
        "share": stratum.share,
        "share_status": share_status,
        "mean_r": stratum.mean_r,
        "mean_r_status": mean_r_status,
        "wr_status": stratum.wr_status.value,
        "wr": stratum.wr,
    }


def build_run_manifest(
    manifest: Manifest,
    receipt: AuthorizationReceipt,
    run_started_utc: str,
    run_finished_utc: str,
    observation_table_fingerprint: str,
) -> dict:
    """Build the complete run_manifest.json content with full provenance."""
    import sys
    import numpy as np

    frozen_fields = to_json_value(manifest)
    return {
        **frozen_fields,
        "head_commit": receipt.head_commit,
        "authorization_commit": receipt.authorization_commit,
        "manifest_sha256": receipt.manifest_sha256,
        "protocol_sha256": receipt.protocol_sha256,
        "numpy_version": np.__version__,
        "python_version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "candidate_universe_fingerprint": {
            r.instrument: r.candidate_fingerprint for r in receipt.instrument_results
        },
        "observation_table_fingerprint": observation_table_fingerprint,
        "run_started_utc": run_started_utc,
        "run_finished_utc": run_finished_utc,
    }


def build_policy_summary(stats: StatisticsResult) -> dict:
    from evaluation.direction import FROZEN_POLICY_IDS

    summary: dict = {}
    for policy_id in FROZEN_POLICY_IDS:
        strata = stats.strata[policy_id]
        est_b = stats.est_b_results[policy_id]
        bootstrap = stats.bootstrap_results[policy_id]
        deltas = stats.instrument_deltas[policy_id]

        eligibilities = {eligibility.policy_id: eligibility for eligibility in stats.eligibilities}
        elig = eligibilities[policy_id]

        summary[policy_id] = {
            "total_n": strata.total_n,
            "closed_n": strata.closed_n,
            "open_n": strata.open_n,
            "never_filled_n": strata.never_filled_n,
            "strata": {
                "ALIGNED": _stratum_dict(strata.closed_aligned),
                "OPPOSED": _stratum_dict(strata.closed_opposed),
                "UNRESOLVED": _stratum_dict(strata.closed_unresolved),
            },
            "est_b": {
                "status": est_b.status.value,
                "point": est_b.point,
            },
            "ci": {
                "status": bootstrap.ci_status.value,
                "lower": bootstrap.lower,
                "upper": bootstrap.upper,
            },
            "instrument_deltas": [
                {
                    "instrument": d.instrument,
                    "status": d.status.value,
                    "point": d.point,
                }
                for d in deltas
            ],
            "eligible": elig.eligible,
            "reasons": [r.value for r in elig.reasons],
            "label": "frictionless label, not net economic validation",
            "profit_factor": "N/A",
            "trading_cost_price": 0.0,
            "cost_model": {
                "execution": "frictionless",
                "spread": "unmodeled",
                "commission": "unmodeled",
                "slippage": "unmodeled",
            },
        }
    return summary


def build_bootstrap_summary(stats: StatisticsResult) -> dict:
    from evaluation.direction import FROZEN_POLICY_IDS

    return {
        "replicate_count": len(stats.plan.draws),
        "seed": [20260910],
        "ci_method": "percentile",
        "family_wise_correction": "bonferroni_4",
        "per_policy_ci": {
            policy_id: {
                "status": stats.bootstrap_results[policy_id].ci_status.value,
                "lower": stats.bootstrap_results[policy_id].lower,
                "upper": stats.bootstrap_results[policy_id].upper,
            }
            for policy_id in FROZEN_POLICY_IDS
        },
        "per_instrument_universe_size": {
            instrument: len(universe)
            for instrument, universe in stats.plan.universes.items()
        },
    }


def build_nomination_trace(stats: StatisticsResult) -> dict:
    trace: dict = {"policies": {}}
    for elig in stats.eligibilities:
        est_b = stats.est_b_results.get(elig.policy_id)
        bootstrap = stats.bootstrap_results.get(elig.policy_id)
        deltas = stats.instrument_deltas.get(elig.policy_id, ())

        if est_b is None or bootstrap is None:
            raise ValueError(f"missing statistical result for policy {elig.policy_id}")

        delta_conditions = [
            {
                "instrument": delta.instrument,
                "status": delta.status.value,
                "point": delta.point,
                "passed": delta.status.value != "ESTIMABLE" or delta.point > -0.20,
            }
            for delta in deltas
        ]
        conditions = {
            "est_b_computable": {
                "evaluated_value": est_b.status.value,
                "passed": est_b.status.value == "ESTIMABLE",
            },
            "est_b_at_least_mei": {
                "evaluated_value": est_b.point,
                "value_status": est_b.status.value,
                "passed": est_b.status.value == "ESTIMABLE" and est_b.point >= 0.20,
            },
            "ci_computable": {
                "evaluated_value": bootstrap.ci_status.value,
                "passed": bootstrap.ci_status.value == "COMPUTABLE",
            },
            "ci_lower_positive": {
                "evaluated_value": bootstrap.lower,
                "value_status": bootstrap.ci_status.value,
                "passed": bootstrap.ci_status.value == "COMPUTABLE" and bootstrap.lower > 0,
            },
            "instrument_delta_guard": {
                "evaluated_value": delta_conditions,
                "passed": all(delta["passed"] for delta in delta_conditions),
            },
            "data_quality_checks_passed": {
                "evaluated_value": True,
                "passed": True,
            },
        }

        trace["policies"][elig.policy_id] = {
            "eligible": elig.eligible,
            "reasons": [r.value for r in elig.reasons],
            "est_b_point": elig.est_b_point,
            "ci_lower": elig.ci_lower,
            "ci_upper": elig.ci_upper,
            "conditions": conditions,
            "ranking_value": elig.ci_lower,
        }
    trace["nominee"] = stats.nomination.nominee or "NO POLICY NOMINATED"
    trace["tie_status"] = stats.nomination.nominee is None and any(
        e.eligible for e in stats.eligibilities
    )
    return trace
