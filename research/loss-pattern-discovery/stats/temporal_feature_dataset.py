"""Deliverable C: Temporal Feature Dataset.

Joins `features.confirmation_window_features` (Unit B) with the SAME
pre-entry risk/geometry features Phase 4/5 already validated
(`features.pre_entry_features`) for every executed, evaluable trade (win
and loss -- never loss-only, same primary population as every prior
phase). No field here is computed from anything timestamped after
`entry_ts` -- `compute_pre_entry_features` already enforces that causal
boundary (Phase 4), and `compute_confirmation_window_features` only uses
fields that are all available strictly before or at entry (confirmation
and order-placement instants always precede the fill).

Field integrity (source / formula / availability instant / unit /
missing-value treatment / causality test) is documented in full in
docs/48-temporal-feature-dataset.md; this module is the implementation.
"""
from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

LAB_ROOT = Path(__file__).resolve().parent.parent
REPO_ROOT = LAB_ROOT.parent.parent
for _path in (LAB_ROOT, REPO_ROOT / "detector"):
    if str(_path) not in sys.path:
        sys.path.insert(0, str(_path))

from control.sampling import period_bucket  # noqa: E402
from extract.from_causal_lookahead_audit import extract  # noqa: E402
from features.confirmation_window_features import compute_confirmation_window_features  # noqa: E402
from features.pre_entry_features import compute_pre_entry_features  # noqa: E402
from schema.events import EventRecord  # noqa: E402
from stats.early_stop_hypothesis import build_primary_population  # noqa: E402
from stats.model_population_audit import load_all_series  # noqa: E402


@dataclass(frozen=True)
class TemporalFeatureRow:
    event_id: str
    origin_model: str
    instrument: str
    direction: str
    period_bucket: str | None
    outcome: str
    confirmation_elapsed_minutes: float | None
    confirmation_remaining_minutes: float | None
    confirmation_relative_position: float | None
    confirmation_bar_position: float | None
    window_duration_minutes: float | None
    order_to_fill_minutes: float | None
    risk_atr: float | None
    atr_m15_at_entry: float | None
    risk_price: float
    planned_rr: float | None
    missing_reasons: tuple[str, ...]


def build_temporal_feature_dataset(
    records: list[EventRecord], series_by_instrument: dict,
) -> dict[str, TemporalFeatureRow]:
    rows: dict[str, TemporalFeatureRow] = {}
    for r in records:
        event_id = r.identification.event_id
        window = compute_confirmation_window_features(r)
        pre_entry = compute_pre_entry_features(r, series_by_instrument[r.identification.instrument])
        bucket = period_bucket(r.operation.entry_ts) if r.operation.entry_ts else None
        rows[event_id] = TemporalFeatureRow(
            event_id=event_id,
            origin_model=r.identification.session_label,
            instrument=r.identification.instrument,
            direction=r.identification.original_direction,
            period_bucket=bucket,
            outcome=r.operation.outcome.value,
            confirmation_elapsed_minutes=window.confirmation_elapsed_minutes,
            confirmation_remaining_minutes=window.confirmation_remaining_minutes,
            confirmation_relative_position=window.confirmation_relative_position,
            confirmation_bar_position=window.confirmation_bar_position,
            window_duration_minutes=window.window_duration_minutes,
            order_to_fill_minutes=window.order_to_fill_minutes,
            risk_atr=pre_entry.risk_atr,
            atr_m15_at_entry=pre_entry.atr_m15_at_entry,
            risk_price=pre_entry.risk_price,
            planned_rr=pre_entry.planned_rr,
            missing_reasons=window.missing_reasons + pre_entry.missing_reasons,
        )
    return rows


def _serializable(row: TemporalFeatureRow) -> dict:
    return {k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in row.__dict__.items()}


def main() -> dict[str, TemporalFeatureRow]:
    records = extract(REPO_ROOT)
    series_by_instrument = load_all_series()
    primary = build_primary_population(records)
    rows = build_temporal_feature_dataset(primary, series_by_instrument)

    artifacts_dir = LAB_ROOT / "artifacts"
    artifacts_dir.mkdir(exist_ok=True)
    (artifacts_dir / "phase7_temporal_feature_dataset.json").write_text(
        json.dumps({eid: _serializable(row) for eid, row in rows.items()}, indent=2, default=str),
        encoding="utf-8",
    )
    n_missing = sum(1 for row in rows.values() if row.missing_reasons)
    summary = {"n_rows": len(rows), "n_with_missing_reasons": n_missing}
    print(json.dumps(summary, indent=2))
    return rows


if __name__ == "__main__":
    main()
