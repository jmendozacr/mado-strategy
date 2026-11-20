import json
import unittest
import uuid
from datetime import datetime, timedelta
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import AuditEngine


def write_bars(path, start, count, step=timedelta(minutes=15)):
    with path.open("x", encoding="utf-8") as stream:
        stream.write("<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n")
        for index in range(count):
            instant = start + index * step
            low = 1.1 + index * 0.00001
            stream.write(f"{instant:%Y.%m.%d}\t{instant:%H:%M:%S}\t{low:.5f}\t{low+0.0002:.5f}\t{low-0.0001:.5f}\t{low+0.0001:.5f}\n")


class AnnotationTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent
        token = uuid.uuid4().hex
        self.csv = self.root / f"EURUSD_M15_annotations_{token}.csv"
        self.journal = self.root / f"journal_annotations_{token}.jsonl"
        write_bars(self.csv, datetime(2015, 1, 5, 0), 2000)  # 20+ contiguous days
        self.case = {"id": "fixture", "pair": "EURUSD", "date_ny": "2015-01-07", "model": "9am", "category": "hidden_trade"}
        self.engine = AuditEngine([self.case], {"EURUSD": self.csv}, self.journal, "rules-v1")
        self.engine.start("fixture")
        for _ in range(8):
            self.engine.next("fixture")

    def tearDown(self):
        self.csv.unlink(missing_ok=True)
        self.journal.unlink(missing_ok=True)

    def test_m15_anchor_requires_a_real_closed_candle(self):
        cursor = self.engine._cursor("fixture")
        closed = next(bar["instant"] for bar in self.engine._load_bars("fixture") if bar["instant"] + timedelta(minutes=15) <= cursor)
        saved = self.engine.record_annotation("fixture", {
            "annotation_type": "m15_anchor", "timeframe": "m15", "source_time": closed.isoformat() + "Z",
        })
        self.assertEqual(saved["source_time"], closed.isoformat() + "+00:00")
        for bad in (cursor.isoformat() + "Z", (closed + timedelta(minutes=7)).isoformat() + "Z"):
            with self.assertRaises(ValueError):
                self.engine.record_annotation("fixture", {"annotation_type": "m15_anchor", "timeframe": "m15", "source_time": bad})

    def test_key_level_requires_documented_type_and_aligned_source(self):
        with self.assertRaises(ValueError):
            self.engine.record_annotation("fixture", {
                "annotation_type": "key_level", "timeframe": "h4",
                "source_time": "2015-01-05T10:00:00Z", "price": 1.1,
            })
        with self.assertRaises(ValueError):  # misaligned (not a feeder-hour open)
            self.engine.record_annotation("fixture", {
                "annotation_type": "key_level", "timeframe": "h4", "source_time": "2015-01-05T11:00:00Z",
                "price": 1.1, "documented_level_type": "Order Block",
            })
        saved = self.engine.record_annotation("fixture", {
            "annotation_type": "key_level", "timeframe": "h4", "source_time": "2015-01-05T10:00:00Z",
            "price": 1.1, "documented_level_type": "Order Block",
        })
        self.assertEqual(saved["documented_level_type"], "Order Block")
        self.assertEqual(saved["time_convention"], "ny_feeder_h4")

    def test_daily_key_level_uses_17_ny_time_convention(self):
        saved = self.engine.record_annotation("fixture", {
            "annotation_type": "key_level", "timeframe": "daily", "source_time": "2015-01-05T22:00:00Z",
            "price": 1.1, "documented_level_type": "FVG",
        })
        self.assertEqual(saved["time_convention"], "ny_17_00_daily")

    def test_max_min_reject_a_future_or_nonexistent_candle(self):
        cursor = self.engine._cursor("fixture")
        with self.assertRaises(ValueError):
            self.engine.record_annotation("fixture", {
                "annotation_type": "max", "timeframe": "m15", "price": 1.15,
                "source_time": (cursor + timedelta(minutes=15)).isoformat() + "Z",
            })
        with self.assertRaises(ValueError):
            self.engine.record_annotation("fixture", {
                "annotation_type": "min", "timeframe": "m15", "price": 1.05,
                "source_time": "1999-01-01T00:00:00Z",
            })

    def test_horizontal_level_needs_price_but_not_a_source_candle(self):
        saved = self.engine.record_annotation("fixture", {"annotation_type": "horizontal_level",
                                                           "timeframe": "h4", "price": 1.12345})
        self.assertIsNone(saved["source_time"])
        with self.assertRaises(ValueError):
            self.engine.record_annotation("fixture", {"annotation_type": "horizontal_level", "timeframe": "h4"})

    def test_annotation_persists_with_timestamp_and_provenance_and_never_touches_decisions(self):
        self.engine.record_decision("fixture", {"decision": "wait", "reason": "Observing"})
        saved = self.engine.record_annotation("fixture", {"annotation_type": "max", "timeframe": "m15",
                                                           "price": 1.2, "source_time": "2015-01-07T13:45:00Z"})
        self.assertIn("recorded_at", saved)
        self.assertIn("cursor_utc", saved)
        self.assertEqual(saved["dataset_version"] and len(saved["dataset_version"]), 64)
        restarted = AuditEngine([self.case], {"EURUSD": self.csv}, self.journal, "rules-v1")
        snapshot = restarted.snapshot("fixture")
        self.assertEqual(len(snapshot["annotations"]), 1)
        self.assertEqual(snapshot["annotations"][0]["id"], saved["id"])
        self.assertEqual(len(snapshot["decisions"]), 1)
        self.assertNotIn("category", json.dumps(saved))
        self.assertNotIn("category", json.dumps(snapshot["annotations"]))


if __name__ == "__main__":
    unittest.main()
