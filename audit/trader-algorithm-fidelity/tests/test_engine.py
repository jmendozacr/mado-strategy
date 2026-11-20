import json
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import AuditEngine, feeder_open_utc


NY = ZoneInfo("America/New_York")


def write_bars(path, start, count, step=timedelta(minutes=15)):
    with path.open("x", encoding="utf-8") as stream:
        stream.write("<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n")
        for index in range(count):
            instant = start + index * step
            low = 1.1 + index * 0.00001
            stream.write(f"{instant:%Y.%m.%d}\t{instant:%H:%M:%S}\t{low:.5f}\t{low+0.0002:.5f}\t{low-0.0001:.5f}\t{low+0.0001:.5f}\n")


class ReplayTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent
        token = uuid.uuid4().hex
        self.csv = self.root / f"EURUSD_M15_fixture_{token}.csv"
        self.journal = self.root / f"journal_{token}.jsonl"
        write_bars(self.csv, datetime(2015, 1, 7, 0), 100)
        self.case = {"id": "fixture", "pair": "EURUSD", "date_ny": "2015-01-07", "model": "9am"}
        self.engine = AuditEngine([self.case], {"EURUSD": self.csv}, self.journal, "rules-v1")

    def tearDown(self):
        self.csv.unlink(missing_ok=True)
        self.journal.unlink(missing_ok=True)

    def test_m15_is_closed_before_reaching_frontend(self):
        snapshot = self.engine.start("fixture")
        cutoff = datetime.fromisoformat(snapshot["cursor_utc"])
        self.assertTrue(all(datetime.fromisoformat(bar["available_at"]) <= cutoff for bar in snapshot["m15"]))
        self.assertFalse(any(datetime.fromisoformat(bar["time"]) == cutoff for bar in snapshot["m15"]))
        next_snapshot = self.engine.next("fixture")
        self.assertEqual(len(next_snapshot["m15"]), len(snapshot["m15"]) + 1)

    def test_forming_h4_uses_closed_prefix_only(self):
        self.engine.start("fixture")
        snapshot = self.engine.next("fixture")
        current = snapshot["h4"][-1]
        self.assertFalse(current["complete"])
        self.assertIsNone(current["available_at"])
        self.assertEqual(current["high"], snapshot["m15"][-1]["high"])
        self.assertEqual(current["close"], snapshot["m15"][-1]["close"])

    def test_dst_offsets(self):
        self.assertEqual(feeder_open_utc(date(2015, 1, 7), 9), datetime(2015, 1, 7, 14))
        self.assertEqual(feeder_open_utc(date(2015, 7, 7), 9), datetime(2015, 7, 7, 13))

    def test_decisions_are_append_only_and_server_stamped(self):
        self.engine.start("fixture")
        first = self.engine.record_decision("fixture", {"decision": "wait", "reason": "Pending", "cursor_utc": "2099-01-01T00:00:00"})
        second = self.engine.record_decision("fixture", {"decision": "discard", "reason": "No valid CRT",
                                                         "discard_reason": "No valid CRT", "supersedes": first["id"]})
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first["cursor_utc"], "2099-01-01T00:00:00")
        self.assertEqual(first["rules_version"], "rules-v1")
        self.assertEqual(len(first["dataset_version"]), 64)
        self.assertEqual(first["last_available_m15"], self.engine.snapshot("fixture")["last_available_m15"])
        self.assertEqual(first["case_id"], "fixture")
        self.assertEqual(second["supersedes"], first["id"])
        self.assertEqual(len(self.engine.snapshot("fixture")["decisions"]), 2)
        self.engine.finish("fixture")
        restarted = AuditEngine([self.case], {"EURUSD": self.csv}, self.journal, "rules-v1")
        self.assertEqual(len(restarted.snapshot("fixture")["decisions"]), 2)
        self.assertEqual(restarted.list_cases()[0]["status"], "finished")
        with self.assertRaises(ValueError):
            restarted.next("fixture")

    def test_listing_never_reveals_selection_or_algorithm(self):
        listing = json.dumps(self.engine.list_cases()).lower()
        for forbidden in ("category", "stratum", "outcome", "signal", "trade", "selected_by"):
            self.assertNotIn(forbidden, listing)

    def test_future_claim_and_unpriced_trade_are_rejected(self):
        self.engine.start("fixture")
        self.assertEqual(self.engine.snapshot("fixture")["key_levels"], [])
        with self.assertRaises(ValueError):
            self.engine.record_decision("fixture", {"decision": "wait", "reason": "Pending",
                                                    "sweep_confirmed_at": "2099-01-01T00:00:00+00:00"})
        with self.assertRaises(ValueError):
            self.engine.record_decision("fixture", {"decision": "wait", "reason": "Pending",
                                                    "key_level_available_at": "2099-01-01T00:00:00+00:00"})
        with self.assertRaises(ValueError):
            self.engine.record_decision("fixture", {"decision": "buy", "reason": "Model confirmed"})
        with self.assertRaises(ValueError):
            self.engine.record_decision("fixture", {"decision": "discard", "reason": "No CRT"})

    def test_missing_current_m15_marks_case_non_evaluable(self):
        self.csv.unlink()
        write_bars(self.csv, datetime(2015, 1, 7, 0), 100)
        lines = self.csv.read_text(encoding="utf-8").splitlines()
        self.csv.write_text("\n".join(line for line in lines if "2015.01.07\t14:15:00" not in line) + "\n", encoding="utf-8")
        self.engine.start("fixture")
        self.engine.next("fixture")
        self.engine.next("fixture")
        snapshot = self.engine.snapshot("fixture")
        self.assertEqual(snapshot["case"]["integrity"], "non_evaluable")
        self.assertNotIn("2015-01-07T14:00:00+00:00", [bar["time"] for bar in snapshot["h4"]])


if __name__ == "__main__":
    unittest.main()
