"""REQ-STAT-59 — Pre-baseline synthetic performance qualification.

One-time execution; NOT part of the CI suite.

Constructs deterministic synthetic DirectionPolicyObservation populations at
four approved sizes (50, 100, 200, 500 candidates per instrument) and times the
frozen Layer-1 statistical path (compute_all_statistics + 10 000-replicate
bootstrap) for each size.

Guarantees:
  - SYNTHETIC DATA ONLY — no CSV files, no real datasets, no real outcomes.
  - Layer-1 code is not modified; this script is a caller only.
  - The production bootstrap RNG (SeedSequence [20260910]) is invoked exactly
    once inside compute_all_statistics, as required by REQ-STAT-51.
  - A separate seed (DATA_SEED = 42) governs synthetic data construction only.
  - Results are written to req_stat_59_report.json alongside this script.
  - Performance numbers are NOT interpreted as real-world estimates.

Usage (from repo root):
    cd detector && .venv\\Scripts\\python.exe tests/qualification/qualify_req_stat_59.py
"""

import gc
import platform
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

# ---------------------------------------------------------------------------
# Path setup — add detector/ src to sys.path so imports resolve.
# ---------------------------------------------------------------------------
_SCRIPT_DIR = Path(__file__).resolve().parent
_DETECTOR_ROOT = _SCRIPT_DIR.parents[1]
if str(_DETECTOR_ROOT) not in sys.path:
    sys.path.insert(0, str(_DETECTOR_ROOT))

from evaluation.direction import FROZEN_POLICY_IDS  # noqa: E402 — after path fix
from runner.serialization import canonical_json  # noqa: E402
from runner.statistics_bridge import compute_all_statistics  # noqa: E402
from selection.bootstrap import FROZEN_REPLICATES  # noqa: E402
from selection.model import (  # noqa: E402
    CandidateIdentity,
    ClosedTradeOutcome,
    DirectionPolicyObservation,
    OutcomeState,
    Relation,
)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
INSTRUMENTS: tuple[str, ...] = ("EURUSDm", "GBPUSDm", "DXYm")
CANDIDATE_SIZES: tuple[int, ...] = (50, 100, 200, 500)
CLOSED_FRACTION: float = 1.0   # worst-case: every observation is CLOSED
DATA_SEED: int = 42             # governs synthetic data construction only
REPORT_PATH = _SCRIPT_DIR / "req_stat_59_report.json"


# ---------------------------------------------------------------------------
# Synthetic population builder
# ---------------------------------------------------------------------------

def _build_synthetic_observations(
    n_candidates_per_instrument: int,
    rng: np.random.Generator,
) -> list[DirectionPolicyObservation]:
    """Return a fully CLOSED synthetic population at worst-case scale.

    Each candidate maps to exactly one cluster (1:1 mapping — maximises
    bootstrap universe size K, i.e. worst case for apply_plan_to_policy).
    Each candidate produces 4 observations (one per policy), satisfying the
    4N cardinality rule (run_discovery.py:95-96).

    realized_r values are drawn from a symmetric N(0, 1) distribution so
    that EST-B is expected to be near zero — the bootstrap CI computation
    path is exercised in full (no early UNDEFINED exit).
    """
    observations: list[DirectionPolicyObservation] = []
    timeframe = "M15"

    # Half ALIGNED, half OPPOSED per instrument so bootstrap has both sides.
    relations_cycle = [Relation.ALIGNED, Relation.OPPOSED]

    r_values = rng.standard_normal(n_candidates_per_instrument * len(INSTRUMENTS))
    r_idx = 0

    for inst in INSTRUMENTS:
        for cand_idx in range(n_candidates_per_instrument):
            signal_id = f"{inst}_s{cand_idx:04d}"
            candidate_id = CandidateIdentity(
                instrument=inst,
                timeframe=timeframe,
                signal_id=signal_id,
                retest_index=0,
            )
            # Cluster id: 1:1 with candidate (worst case for K).
            cluster_id = (inst, cand_idx, 0, 0)

            realized_r = float(r_values[r_idx])
            r_idx += 1
            closed_outcome = (
                ClosedTradeOutcome.WIN if realized_r >= 0.0 else ClosedTradeOutcome.LOSS
            )
            relation = relations_cycle[cand_idx % 2]

            for policy_id in FROZEN_POLICY_IDS:
                observations.append(
                    DirectionPolicyObservation(
                        candidate_id=candidate_id,
                        context_cluster_id=cluster_id,
                        policy_id=policy_id,
                        relation=relation,
                        outcome_state=OutcomeState.CLOSED,
                        closed_outcome=closed_outcome,
                        realized_r=realized_r,
                    )
                )

    return observations


# ---------------------------------------------------------------------------
# Memory measurement helpers
# ---------------------------------------------------------------------------

def _try_ctypes_rss_mb() -> float | None:
    """Attempt to read peak RSS via ctypes on Windows (PROCESS_MEMORY_COUNTERS).

    Returns peak working-set size in MB, or None if unavailable.
    This captures native allocations that tracemalloc misses (numpy arrays,
    C extensions). Does not add any pip dependency.
    """
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        import ctypes.wintypes

        class _PROCESS_MEMORY_COUNTERS(ctypes.Structure):
            _fields_ = [
                ("cb", ctypes.wintypes.DWORD),
                ("PageFaultCount", ctypes.wintypes.DWORD),
                ("PeakWorkingSetSize", ctypes.c_size_t),
                ("WorkingSetSize", ctypes.c_size_t),
                ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPagedPoolUsage", ctypes.c_size_t),
                ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                ("PagefileUsage", ctypes.c_size_t),
                ("PeakPagefileUsage", ctypes.c_size_t),
            ]

        psapi = ctypes.WinDLL("psapi.dll")
        kernel32 = ctypes.WinDLL("kernel32.dll")
        handle = kernel32.GetCurrentProcess()
        pmc = _PROCESS_MEMORY_COUNTERS()
        pmc.cb = ctypes.sizeof(pmc)
        if psapi.GetProcessMemoryInfo(handle, ctypes.byref(pmc), pmc.cb):
            return pmc.PeakWorkingSetSize / (1024 * 1024)
    except Exception:
        pass
    return None


# ---------------------------------------------------------------------------
# Single-size qualification run
# ---------------------------------------------------------------------------

def _run_one(n: int) -> dict:
    """Construct synthetic data, call compute_all_statistics, measure cost."""
    data_rng = np.random.Generator(np.random.PCG64(np.random.SeedSequence([DATA_SEED, n])))
    observations = _build_synthetic_observations(n, data_rng)
    total_observations = len(observations)

    # Disable GC during timed section for measurement stability.
    gc.collect()
    gc.disable()

    # Reset RSS baseline before the timed section by taking an initial snapshot.
    rss_before = _try_ctypes_rss_mb()

    tracemalloc.start()
    t0 = time.perf_counter()

    compute_all_statistics(observations, INSTRUMENTS)

    t1 = time.perf_counter()
    _, peak_traced_bytes = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    gc.enable()

    rss_after_peak = _try_ctypes_rss_mb()
    wall_seconds = t1 - t0

    result: dict = {
        "n_candidates_per_instrument": n,
        "total_observations": total_observations,
        "wall_clock_seconds": round(wall_seconds, 4),
        "peak_tracemalloc_mb": round(peak_traced_bytes / (1024 * 1024), 3),
    }

    if rss_before is not None and rss_after_peak is not None:
        result["peak_working_set_mb"] = round(rss_after_peak, 1)
        result["rss_delta_mb"] = round(rss_after_peak - rss_before, 1)
        result["memory_method"] = "ctypes_PROCESS_MEMORY_COUNTERS + tracemalloc"
    else:
        result["peak_working_set_mb"] = None
        result["rss_delta_mb"] = None
        result["memory_method"] = "tracemalloc_only (ctypes RSS unavailable on this platform)"

    return result


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print(f"REQ-STAT-59 synthetic performance qualification")
    print(f"Python {sys.version}")
    print(f"numpy {np.__version__}")
    print(f"Instruments: {INSTRUMENTS}")
    print(f"Policies: {FROZEN_POLICY_IDS}")
    print(f"Replicates: {FROZEN_REPLICATES}")
    print(f"Closed fraction: {CLOSED_FRACTION} (worst case)")
    print(f"Sizes: {CANDIDATE_SIZES}")
    print()

    results = []
    for n in CANDIDATE_SIZES:
        total = n * len(INSTRUMENTS) * len(FROZEN_POLICY_IDS)
        print(f"  N={n:4d} ({total:5d} total obs) ... ", end="", flush=True)
        row = _run_one(n)
        results.append(row)
        print(
            f"{row['wall_clock_seconds']:7.2f}s  "
            f"tracemalloc={row['peak_tracemalloc_mb']:.1f} MB"
            + (
                f"  RSS_delta={row['rss_delta_mb']:.1f} MB"
                if row["rss_delta_mb"] is not None
                else ""
            )
        )

    report = {
        "qualification": "REQ-STAT-59",
        "synthetic_data_only": True,
        "disclaimer": (
            "All observations are synthetic. No real datasets, CSV files, or "
            "real outcomes were loaded. Results reflect CPython performance on "
            "this specific machine and must not be interpreted as real-world "
            "discovery runtime estimates."
        ),
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "environment": {
            "python_version": sys.version,
            "numpy_version": np.__version__,
            "platform": platform.platform(),
            "processor": platform.processor(),
            "python_executable": sys.executable,
        },
        "workload": {
            "instruments": list(INSTRUMENTS),
            "n_policies": len(FROZEN_POLICY_IDS),
            "policy_ids": list(FROZEN_POLICY_IDS),
            "n_replicates": FROZEN_REPLICATES,
            "closed_fraction": CLOSED_FRACTION,
            "cluster_structure": "1:1 candidates-to-clusters (worst case for K)",
            "synthetic_data_seed": DATA_SEED,
            "production_bootstrap_seed": list([20260910]),
        },
        "timing_method": "time.perf_counter() (highest-resolution wall-clock, Python stdlib)",
        "memory_methods": {
            "tracemalloc": "Python stdlib; tracks Python-managed allocations only",
            "ctypes_rss": (
                "ctypes PROCESS_MEMORY_COUNTERS via psapi.dll (Windows only); "
                "captures peak working set including native numpy allocations"
            ),
        },
        "results": results,
        "threshold": "NONE — no performance threshold was preregistered (REQ-STAT-59). "
                     "Human operational review required before baseline B decision.",
        "verdict": "MEASURED — human decision required",
    }

    REPORT_PATH.write_bytes(canonical_json(report))
    print(f"\nReport written to: {REPORT_PATH}")


if __name__ == "__main__":
    main()
