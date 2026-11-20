"""Server-owned causal replay for the local trader fidelity audit."""

from __future__ import annotations

import csv
import hashlib
import json
import math
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
DAILY_HOURS = (17,)
# Engineering assumption (not a charter rule, none defines a Daily boundary):
# the forex trading day rolls over at 17:00 America/New_York.
FOREX_WEEK_CLOSE_HOUR = 17  # Friday 17:00 NY
FOREX_WEEK_OPEN_HOUR = 17  # Sunday 17:00 NY
CONTEXT_MAX_PAGE_DAYS = 60
CONTEXT_DEFAULT_PAGE_DAYS = 14
CONTEXT_TIMEFRAMES = {"h4": (FEEDER_HOURS, 4), "daily": (DAILY_HOURS, 24)}
ANNOTATION_TYPES = {"max", "min", "horizontal_level", "key_level", "m15_anchor"}
ANNOTATION_TIMEFRAMES = {"m15", "h4", "daily"}
ANNOTATION_TIME_CONVENTIONS = {"m15": "utc_m15_close", "h4": "ny_feeder_h4", "daily": "ny_17_00_daily"}


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


def window_end(case: dict) -> datetime:
    return current_open(case) + H4


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


def is_forex_weekend_ny(instant_utc: datetime) -> bool:
    """Standard forex week closure: Friday 17:00 NY through Sunday 17:00 NY.

    Engineering assumption used only to avoid flagging the expected weekly
    closure as a data gap; no charter defines this boundary.
    """
    ny = instant_utc.replace(tzinfo=UTC).astimezone(NY)
    weekday = ny.weekday()  # Monday = 0 ... Sunday = 6
    if weekday == 4:
        return ny.hour >= FOREX_WEEK_CLOSE_HOUR
    if weekday == 5:
        return True
    if weekday == 6:
        return ny.hour < FOREX_WEEK_OPEN_HOUR
    return False


def bucket_close_utc(day: date, hour: int, span_hours: int) -> datetime:
    """The UTC instant `span_hours` of NY wall-clock time after NY local (day, hour).

    Computed by shifting the NY-local hour/day and re-resolving through
    `feeder_open_utc`, rather than adding a fixed UTC timedelta, so a bucket that
    spans a DST transition still closes at the correct NY wall-clock time.
    """
    total = hour + span_hours
    return feeder_open_utc(day + timedelta(days=total // 24), total % 24)


def bucket_candles(bars: list[dict], cursor: datetime, lower_bound: datetime, upper_bound: datetime,
                    anchor_hours: tuple[int, ...], span_hours: int) -> list[dict]:
    """Derive HTF candles anchored at `anchor_hours` (NY local), from a causal M15
    prefix only. Never fabricates or interpolates a missing M15 slot: a slot missing
    for the expected weekly forex closure does not count against completeness; any
    other missing slot is reported in `gap_slots` and the candle's `integrity`
    becomes `"gap"` instead of `"complete"`. A candle whose window has not fully
    elapsed yet is `"forming"` and carries no `available_at`.
    """
    visible = sorted((bar for bar in bars if bar["instant"] + M15 <= cursor), key=lambda bar: bar["instant"])
    candles = []
    day = lower_bound.date() - timedelta(days=1)
    end_day = upper_bound.date() + timedelta(days=1)
    while day <= end_day:
        for hour in anchor_hours:
            opening = feeder_open_utc(day, hour)
            if opening < lower_bound or opening > upper_bound:
                continue
            closing = bucket_close_utc(day, hour, span_hours)
            bucket = [bar for bar in visible if opening <= bar["instant"] < closing]
            if not bucket:
                continue
            present = {bar["instant"] for bar in bucket}
            missing = []
            slot = opening
            while slot < closing:
                if slot not in present:
                    missing.append(slot)
                slot += M15
            unexplained = [slot for slot in missing if not is_forex_weekend_ny(slot)]
            elapsed = closing <= cursor
            if unexplained:
                integrity = "gap"
            elif elapsed:
                integrity = "complete"
            else:
                integrity = "forming"
            candles.append({"time": utc_text(opening),
                             "available_at": utc_text(closing) if integrity == "complete" else None,
                             "open": bucket[0]["open"], "high": max(bar["high"] for bar in bucket),
                             "low": min(bar["low"] for bar in bucket), "close": bucket[-1]["close"],
                             "complete": integrity == "complete", "integrity": integrity,
                             "gap_slots": [utc_text(slot) for slot in unexplained]})
        day += timedelta(days=1)
    candles.sort(key=lambda bar: bar["time"])
    return candles


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
        self.dataset_starts: dict[str, datetime] = {}
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

    def _metric_eligible(self, case_id: str) -> bool | None:
        finishes = self._events(case_id, "finish")
        return finishes[-1].get("metric_eligible", False) if finishes else None

    def _can_finish(self, case_id: str, integrity: str, cursor: datetime) -> bool:
        if self._case_status(case_id) != "in_progress":
            return False
        decisions = self._events(case_id, "decision")
        if integrity == "non_evaluable":
            return any(event["decision"]["decision"] == "data_issue" for event in decisions)
        return cursor >= window_end(self.cases[case_id]) and bool(decisions) and \
            decisions[-1]["decision"]["cursor_utc"] == utc_text(cursor)

    def list_cases(self) -> list[dict]:
        with self.lock:
            return [{"id": case["id"], "pair": case["pair"], "date_ny": case["date_ny"],
                     "model": case["model"], "status": self._case_status(case["id"]),
                     "metric_eligible": self._metric_eligible(case["id"])}
                    for case in self.cases.values()]

    def _load_bars(self, case_id: str) -> list[dict]:
        if case_id not in self.bars:
            case = self.cases[case_id]
            origin = current_open(case)
            self.bars[case_id] = read_m15(self.data_paths[case["pair"]], origin - timedelta(hours=32), origin + H4)
        return self.bars[case_id]

    def _dataset_start(self, pair: str) -> datetime:
        if pair not in self.dataset_starts:
            with self.data_paths[pair].open("r", encoding="utf-8-sig", newline="") as stream:
                row = next(csv.DictReader(stream, delimiter="\t"))
            self.dataset_starts[pair] = datetime.strptime(row["<DATE>"] + " " + row["<TIME>"], "%Y.%m.%d %H:%M:%S")
        return self.dataset_starts[pair]

    def historical_context(self, case_id: str, timeframe: str, before: datetime | None, page_days: int) -> dict:
        if timeframe not in CONTEXT_TIMEFRAMES:
            raise ValueError("Unknown timeframe")
        page_days = max(1, min(page_days, CONTEXT_MAX_PAGE_DAYS))
        with self.lock:
            cursor = self._cursor(case_id)
            case = self.cases[case_id]
            upper = cursor if before is None else before
            if upper > cursor:
                raise ValueError("Cannot request historical context beyond the replay cursor")
            lower = upper - timedelta(days=page_days)
            anchor_hours, span_hours = CONTEXT_TIMEFRAMES[timeframe]
            margin = timedelta(hours=span_hours + 1)
            path = self.data_paths[case["pair"]]
            bars = read_m15(path, lower - margin, min(upper + margin, cursor))
            candles = bucket_candles(bars, cursor, lower, upper, anchor_hours, span_hours)
            exhausted = lower <= self._dataset_start(case["pair"])
            return {"timeframe": timeframe, "candles": candles,
                    "next_before": utc_text(lower) if not exhausted else None, "exhausted": exhausted}

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
            end = window_end(self.cases[case_id])
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
                           "integrity": "evaluable" if levels and current_contiguous else "non_evaluable",
                           "metric_eligible": self._metric_eligible(case_id)}
            decisions = [event["decision"] for event in self._events(case_id, "decision")]
            public_case["can_finish"] = self._can_finish(case_id, public_case["integrity"], cursor)
            return {"case": public_case, "cursor_utc": utc_text(cursor),
                    "cursor_ny": cursor.replace(tzinfo=UTC).astimezone(NY).isoformat(),
                    "m15": m15, "h4": h4, "reference_levels": levels, "key_levels": [],
                    "last_available_m15": m15[-1]["time"] if m15 else None, "decisions": decisions,
                    "annotations": [event["annotation"] for event in self._events(case_id, "annotation")]}

    def record_decision(self, case_id: str, payload: dict) -> dict:
        with self.lock:
            if self._case_status(case_id) != "in_progress":
                raise ValueError("Case is not active")
            if payload.get("decision") not in {"buy", "sell", "wait", "discard", "data_issue"}:
                raise ValueError("Invalid decision")
            if not isinstance(payload.get("reason"), str) or not payload["reason"].strip():
                raise ValueError("Reason is required")
            if payload["decision"] in {"buy", "sell"}:
                for field in ("entry_price", "stop_loss", "take_profit"):
                    if not isinstance(payload.get(field), (int, float)) or not math.isfinite(payload[field]) or payload[field] <= 0:
                        raise ValueError(f"{field} is required for a trade")
                entry, stop, target = (payload[field] for field in ("entry_price", "stop_loss", "take_profit"))
                valid_geometry = stop < entry < target if payload["decision"] == "buy" else target < entry < stop
                if not valid_geometry:
                    raise ValueError("Trade prices must place entry between stop loss and take profit in the trade direction")
            if payload["decision"] == "discard" and not payload.get("discard_reason"):
                raise ValueError("discard_reason is required")
            if payload["decision"] == "data_issue" and not isinstance(payload.get("data_issue_reason"), str):
                raise ValueError("A data issue reason is required")
            if payload["decision"] == "data_issue" and not payload["data_issue_reason"].strip():
                raise ValueError("A data issue reason is required")
            cursor = self._cursor(case_id).replace(tzinfo=UTC)
            parsed_times = {}
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
                parsed_times[field] = instant.astimezone(UTC).replace(tzinfo=None)
            if "model1_anchor_at" in parsed_times:
                anchor = parsed_times["model1_anchor_at"]
                matching_bar = next((bar for bar in self._load_bars(case_id) if bar["instant"] == anchor), None)
                if matching_bar is None or anchor + M15 > cursor.replace(tzinfo=None):
                    raise ValueError("model1_anchor_at must identify a real closed M15 candle")
            if "model1_anchor_at" in parsed_times and "model1_confirmed_at" in parsed_times:
                if parsed_times["model1_confirmed_at"] < parsed_times["model1_anchor_at"] + M15:
                    raise ValueError("model1_confirmed_at cannot precede the anchor candle close")
            if "sweep_confirmed_at" in parsed_times and "model1_anchor_at" in parsed_times:
                if parsed_times["sweep_confirmed_at"] > parsed_times["model1_anchor_at"]:
                    raise ValueError("sweep confirmation cannot follow the Model #1 anchor")
            if "key_level_available_at" in parsed_times and "model1_anchor_at" in parsed_times:
                if parsed_times["key_level_available_at"] > parsed_times["model1_anchor_at"]:
                    raise ValueError("Key Level cannot be available after the Model #1 anchor")
            if self.snapshot(case_id)["case"]["integrity"] == "non_evaluable" and payload["decision"] != "data_issue":
                raise ValueError("Non-evaluable cases require a data issue, not a signal judgment")
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

    def _validate_annotation_source(self, case_id: str, timeframe: str, source_time: datetime,
                                     cursor: datetime) -> datetime | None:
        case = self.cases[case_id]
        if source_time > cursor:
            raise ValueError("source_time exceeds the replay cursor")
        if timeframe == "m15":
            bar = next((bar for bar in self._load_bars(case_id) if bar["instant"] == source_time), None)
            if bar is None or bar["instant"] + M15 > cursor:
                raise ValueError("source_time must identify a real closed M15 candle")
            return bar["instant"] + M15
        anchor_hours, span_hours = CONTEXT_TIMEFRAMES[timeframe]
        ny = source_time.replace(tzinfo=UTC).astimezone(NY)
        if ny.hour not in anchor_hours or feeder_open_utc(ny.date(), ny.hour) != source_time:
            raise ValueError(f"source_time is not aligned to a {timeframe} candle open")
        closing = bucket_close_utc(ny.date(), ny.hour, span_hours)
        bars = read_m15(self.data_paths[case["pair"]], source_time, min(closing, cursor))
        if not bars:
            raise ValueError("source_time has no available market data yet")
        return closing if closing <= cursor else None

    def record_annotation(self, case_id: str, payload: dict) -> dict:
        with self.lock:
            if self._case_status(case_id) != "in_progress":
                raise ValueError("Case is not active")
            annotation_type = payload.get("annotation_type")
            if annotation_type not in ANNOTATION_TYPES:
                raise ValueError("Invalid annotation_type")
            timeframe = payload.get("timeframe")
            if timeframe not in ANNOTATION_TIMEFRAMES:
                raise ValueError("Invalid timeframe")
            if annotation_type == "m15_anchor" and timeframe != "m15":
                raise ValueError("m15_anchor must be recorded on the m15 timeframe")
            cursor = self._cursor(case_id)
            raw_source = payload.get("source_time")
            requires_source = annotation_type in {"max", "min", "key_level", "m15_anchor"}
            if requires_source and not raw_source:
                raise ValueError("source_time is required for this annotation_type")
            source_time = source_available_at = None
            if raw_source:
                try:
                    source_time = datetime.fromisoformat(raw_source.replace("Z", "+00:00")).astimezone(UTC).replace(tzinfo=None)
                except (AttributeError, ValueError) as error:
                    raise ValueError("Invalid source_time") from error
                source_available_at = self._validate_annotation_source(case_id, timeframe, source_time, cursor)
            if annotation_type != "m15_anchor":
                price = payload.get("price")
                if not isinstance(price, (int, float)) or not math.isfinite(price) or price <= 0:
                    raise ValueError("price is required for this annotation_type")
            if annotation_type == "key_level":
                level_type = payload.get("documented_level_type")
                if not isinstance(level_type, str) or not level_type.strip():
                    raise ValueError("documented_level_type is required for a Key Level")
            now = datetime.now(UTC).isoformat()
            annotation = {"id": str(uuid.uuid4()), "case_id": case_id, "annotation_type": annotation_type,
                          "timeframe": timeframe, "time_convention": ANNOTATION_TIME_CONVENTIONS[timeframe],
                          "source_time": utc_text(source_time) if source_time else None,
                          "source_available_at": utc_text(source_available_at) if source_available_at else None,
                          "price": payload.get("price"), "documented_level_type": payload.get("documented_level_type"),
                          "notes": payload.get("notes"), "cursor_utc": utc_text(cursor),
                          "cursor_ny": cursor.replace(tzinfo=UTC).astimezone(NY).isoformat(),
                          "dataset_version": self._dataset_version(self.cases[case_id]["pair"]),
                          "rules_version": self.rules_version, "recorded_at": now}
            self._append({"kind": "annotation", "case_id": case_id, "annotation": annotation})
            return annotation

    def finish(self, case_id: str) -> dict:
        with self.lock:
            if self._case_status(case_id) != "in_progress":
                raise ValueError("Case is not active")
            snapshot = self.snapshot(case_id)
            decisions = self._events(case_id, "decision")
            non_evaluable = snapshot["case"]["integrity"] == "non_evaluable"
            data_issue = any(event["decision"]["decision"] == "data_issue" for event in decisions)
            if non_evaluable and not data_issue:
                raise ValueError("Non-evaluable case requires a recorded data issue")
            if not non_evaluable:
                if self._cursor(case_id) < window_end(self.cases[case_id]):
                    raise ValueError("Cannot finish before the documented review window end")
                if not decisions or decisions[-1]["decision"]["cursor_utc"] != snapshot["cursor_utc"]:
                    raise ValueError("A decision at the window end is required")
            metric_eligible = not non_evaluable and not data_issue
            self._append({"kind": "finish", "case_id": case_id, "metric_eligible": metric_eligible,
                          "recorded_at": datetime.now(UTC).isoformat()})
            return {"id": case_id, "status": "finished", "metric_eligible": metric_eligible}
