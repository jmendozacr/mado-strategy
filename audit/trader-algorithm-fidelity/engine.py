"""Server-owned causal replay for the local trader fidelity audit."""

from __future__ import annotations

import csv
import hashlib
import json
import os
import threading
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo


NY = ZoneInfo("America/New_York")
UTC = timezone.utc
M15 = timedelta(minutes=15)
H4 = timedelta(hours=4)
FEEDER_HOURS = (1, 5, 9, 13, 17, 21)


def utc_text(value: datetime) -> str:
    return value.replace(tzinfo=UTC).isoformat()


def feeder_open_utc(day: date, hour: int) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=NY).astimezone(UTC).replace(tzinfo=None)


def reference_open(case: dict) -> datetime:
    day = date.fromisoformat(case["date_ny"])
    if case["model"] == "1am":
        return feeder_open_utc(day - timedelta(days=1), 21)
    return feeder_open_utc(day, 5)


def current_open(case: dict) -> datetime:
    return feeder_open_utc(date.fromisoformat(case["date_ny"]), 1 if case["model"] == "1am" else 9)


def read_m15(path: Path, lower: datetime, upper: datetime) -> list[dict]:
    bars = []
    first_day = lower.strftime("%Y.%m.%d")
    last_day = upper.strftime("%Y.%m.%d")
    with path.open("r", encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream, delimiter="\t")
        for row in reader:
            if row["<DATE>"] < first_day:
                continue
            if row["<DATE>"] > last_day:
                break
            instant = datetime.strptime(row["<DATE>"] + " " + row["<TIME>"], "%Y.%m.%d %H:%M:%S")
            if instant < lower:
                continue
            if instant >= upper:
                break
            bars.append({"instant": instant, "open": float(row["<OPEN>"]), "high": float(row["<HIGH>"]),
                         "low": float(row["<LOW>"]), "close": float(row["<CLOSE>"])})
    return bars


def complete_bucket(bars: list[dict], start: datetime) -> bool:
    bucket = [bar for bar in bars if start <= bar["instant"] < start + H4]
    return len(bucket) == 16 and all(bar["instant"] == start + i * M15 for i, bar in enumerate(bucket))


class AuditEngine:
    def __init__(self, cases: list[dict], data_paths: dict[str, Path], journal: Path, rules_version: str):
        self.cases = {case["id"]: case for case in cases}
        self.data_paths = data_paths
        self.journal = journal
        self.rules_version = rules_version
        self.lock = threading.RLock()
        self.history: dict[str, list[dict]] = {case_id: [] for case_id in self.cases}
        self.datasets: dict[str, str] = {}
        self.bars: dict[str, list[dict]] = {}
        if journal.exists():
            with journal.open("r", encoding="utf-8") as stream:
                for line in stream:
                    event = json.loads(line)
                    if event["case_id"] in self.history:
                        self.history[event["case_id"]].append(event)

    def _events(self, case_id: str, kind: str | None = None) -> list[dict]:
        if case_id not in self.cases:
            raise KeyError(case_id)
        return [event for event in self.history[case_id] if kind is None or event["kind"] == kind]

    def _append(self, event: dict) -> None:
        self.journal.parent.mkdir(parents=True, exist_ok=True)
        with self.journal.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        self.history[event["case_id"]].append(event)

    def _case_status(self, case_id: str) -> str:
        events = self._events(case_id)
        if any(event["kind"] == "finish" for event in events):
            return "finished"
        if any(event["kind"] == "start" for event in events):
            return "in_progress"
        return "not_started"

    def list_cases(self) -> list[dict]:
        with self.lock:
            return [{"id": case["id"], "pair": case["pair"], "date_ny": case["date_ny"],
                     "model": case["model"], "status": self._case_status(case["id"])}
                    for case in self.cases.values()]

    def _load_bars(self, case_id: str) -> list[dict]:
        if case_id not in self.bars:
            case = self.cases[case_id]
            origin = current_open(case)
            self.bars[case_id] = read_m15(self.data_paths[case["pair"]], origin - timedelta(hours=32), origin + H4)
        return self.bars[case_id]

    def _dataset_version(self, pair: str) -> str:
        if pair not in self.datasets:
            digest = hashlib.sha256()
            with self.data_paths[pair].open("rb") as stream:
                for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(chunk)
            self.datasets[pair] = digest.hexdigest()
        return self.datasets[pair]

    def _cursor(self, case_id: str) -> datetime:
        case = self.cases[case_id]
        moves = [event for event in self._events(case_id) if event["kind"] in {"start", "next"}]
        if not moves:
            raise ValueError("Case has not started")
        return datetime.fromisoformat(moves[-1]["cursor_utc"]).replace(tzinfo=None)

    def start(self, case_id: str) -> dict:
        with self.lock:
            if self._case_status(case_id) == "not_started":
                self._append({"kind": "start", "case_id": case_id, "cursor_utc": utc_text(current_open(self.cases[case_id]))})
            return self.snapshot(case_id)

    def next(self, case_id: str) -> dict:
        with self.lock:
            if self._case_status(case_id) != "in_progress":
                raise ValueError("Case is not active")
            cursor = self._cursor(case_id)
            end = current_open(self.cases[case_id]) + H4
            candidates = [bar["instant"] + M15 for bar in self._load_bars(case_id)
                          if cursor < bar["instant"] + M15 <= end]
            if not candidates:
                raise ValueError("No more M15 candles")
            self._append({"kind": "next", "case_id": case_id, "cursor_utc": utc_text(min(candidates))})
            return self.snapshot(case_id)

    def snapshot(self, case_id: str) -> dict:
        with self.lock:
            cursor = self._cursor(case_id)
            case = self.cases[case_id]
            visible = [bar for bar in self._load_bars(case_id) if bar["instant"] + M15 <= cursor]
            m15 = [{"time": utc_text(bar["instant"]), "available_at": utc_text(bar["instant"] + M15),
                    "open": bar["open"], "high": bar["high"], "low": bar["low"], "close": bar["close"]}
                   for bar in visible]
            h4 = []
            start_day = (cursor - timedelta(hours=32)).date()
            end_day = cursor.date()
            day = start_day
            while day <= end_day:
                for hour in FEEDER_HOURS:
                    opening = feeder_open_utc(day, hour)
                    if opening > cursor or opening < cursor - timedelta(hours=32):
                        continue
                    bucket = [bar for bar in visible if opening <= bar["instant"] < opening + H4]
                    if not bucket:
                        continue
                    visible_end = min(cursor, opening + H4)
                    if len(bucket) != int((visible_end - opening) / M15) or any(
                        bar["instant"] != opening + index * M15 for index, bar in enumerate(bucket)
                    ):
                        continue
                    complete = opening + H4 <= cursor and complete_bucket(visible, opening)
                    h4.append({"time": utc_text(opening), "available_at": utc_text(opening + H4) if complete else None,
                               "open": bucket[0]["open"], "high": max(bar["high"] for bar in bucket),
                               "low": min(bar["low"] for bar in bucket), "close": bucket[-1]["close"],
                               "complete": complete, "integrity": "complete" if complete else "forming"})
                day += timedelta(days=1)
            h4.sort(key=lambda bar: bar["time"])
            reference = next((bar for bar in h4 if bar["time"] == utc_text(reference_open(case))), None)
            levels = []
            if reference and reference["complete"]:
                levels = [{"price": reference["high"], "label": "Reference high", "time": reference["available_at"]},
                          {"price": reference["low"], "label": "Reference low", "time": reference["available_at"]}]
            opening = current_open(case)
            current_bars = [bar for bar in visible if opening <= bar["instant"] < cursor]
            expected_count = int((cursor - opening) / M15)
            current_contiguous = len(current_bars) == expected_count and all(
                bar["instant"] == opening + index * M15 for index, bar in enumerate(current_bars)
            )
            public_case = {"id": case_id, "pair": case["pair"], "date_ny": case["date_ny"],
                           "model": case["model"], "status": self._case_status(case_id),
                           "integrity": "evaluable" if levels and current_contiguous else "non_evaluable"}
            decisions = [event["decision"] for event in self._events(case_id, "decision")]
            return {"case": public_case, "cursor_utc": utc_text(cursor),
                    "cursor_ny": cursor.replace(tzinfo=UTC).astimezone(NY).isoformat(),
                    "m15": m15, "h4": h4, "reference_levels": levels, "key_levels": [],
                    "last_available_m15": m15[-1]["time"] if m15 else None, "decisions": decisions}

    def record_decision(self, case_id: str, payload: dict) -> dict:
        with self.lock:
            if self._case_status(case_id) != "in_progress":
                raise ValueError("Case is not active")
            if payload.get("decision") not in {"buy", "sell", "wait", "discard"}:
                raise ValueError("Invalid decision")
            if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
                raise ValueError("Reason is required")
            if payload["decision"] in {"buy", "sell"}:
                for field in ("entry_price", "stop_loss", "take_profit"):
                    if not isinstance(payload.get(field), (int, float)) or payload[field] <= 0:
                        raise ValueError(f"{field} is required for a trade")
            if payload["decision"] == "discard" and not payload.get("discard_reason"):
                raise ValueError("discard_reason is required")
            cursor = self._cursor(case_id).replace(tzinfo=UTC)
            for field in ("sweep_confirmed_at", "key_level_available_at", "model1_anchor_at", "model1_confirmed_at"):
                value = payload.get(field)
                if not value:
                    continue
                try:
                    instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
                except (AttributeError, ValueError) as error:
                    raise ValueError(f"Invalid {field}") from error
                available_at = instant + M15 if field == "model1_anchor_at" else instant
                if instant.tzinfo is None or available_at.astimezone(UTC) > cursor:
                    raise ValueError(f"{field} exceeds replay cursor")
            existing = [event["decision"]["id"] for event in self._events(case_id, "decision")]
            if payload.get("supersedes") and payload["supersedes"] not in existing:
                raise ValueError("Correction target not found")
            snapshot = self.snapshot(case_id)
            now = datetime.now(UTC).isoformat()
            fields = {key: value for key, value in payload.items()
                      if key not in {"id", "case_id", "cursor_utc", "cursor_ny", "last_available_m15",
                                     "dataset_version", "rules_version", "recorded_at"}}
            decision = {**fields, "id": str(uuid.uuid4()), "case_id": case_id,
                        "cursor_utc": snapshot["cursor_utc"], "cursor_ny": snapshot["cursor_ny"],
                        "last_available_m15": snapshot["last_available_m15"],
                        "dataset_version": self._dataset_version(self.cases[case_id]["pair"]),
                        "rules_version": self.rules_version, "recorded_at": now}
            self._append({"kind": "decision", "case_id": case_id, "decision": decision})
            return decision

    def finish(self, case_id: str) -> dict:
        with self.lock:
            if self._case_status(case_id) != "in_progress":
                raise ValueError("Case is not active")
            if not self._events(case_id, "decision"):
                raise ValueError("At least one human decision is required")
            self._append({"kind": "finish", "case_id": case_id, "recorded_at": datetime.now(UTC).isoformat()})
            return {"id": case_id, "status": "finished"}
