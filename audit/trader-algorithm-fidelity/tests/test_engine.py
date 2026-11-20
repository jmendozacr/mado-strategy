import json
import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import AuditEngine, current_open, feeder_open_utc, window_end


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
        initial = self.engine.start("fixture")
        snapshot = self.engine.next("fixture")
        current = snapshot["h4"][-1]
        self.assertFalse(current["complete"])
        self.assertIsNone(current["available_at"])
        self.assertEqual(current["high"], snapshot["m15"][-1]["high"])
        self.assertEqual(current["close"], snapshot["m15"][-1]["close"])

    def test_dst_offsets(self):
        self.assertEqual(feeder_open_utc(date(2015, 1, 7), 9), datetime(2015, 1, 7, 14))
        self.assertEqual(feeder_open_utc(date(2015, 7, 7), 9), datetime(2015, 7, 7, 13))

    def test_documented_review_windows_are_four_ny_hours_across_dst(self):
        for model in ("1am", "9am"):
            for day in ("2015-01-07", "2015-07-07"):
                with self.subTest(model=model, day=day):
                    case = {"date_ny": day, "model": model}
                    self.assertEqual(window_end(case) - current_open(case), timedelta(hours=4))

    def test_decisions_are_append_only_and_server_stamped(self):
        initial = self.engine.start("fixture")
        first = self.engine.record_decision("fixture", {"decision": "wait", "reason": "Pending", "cursor_utc": "2099-01-01T00:00:00"})
        for _ in range(16):
            self.engine.next("fixture")
        second = self.engine.record_decision("fixture", {"decision": "discard", "reason": "No valid CRT",
                                                         "discard_reason": "No valid CRT", "supersedes": first["id"]})
        self.assertNotEqual(first["id"], second["id"])
        self.assertNotEqual(first["cursor_utc"], "2099-01-01T00:00:00")
        self.assertEqual(first["rules_version"], "rules-v1")
        self.assertEqual(len(first["dataset_version"]), 64)
        self.assertEqual(first["last_available_m15"], initial["last_available_m15"])
        self.assertEqual(first["case_id"], "fixture")
        self.assertEqual(second["supersedes"], first["id"])
        self.assertEqual(len(self.engine.snapshot("fixture")["decisions"]), 2)
        self.engine.finish("fixture")
        restarted = AuditEngine([self.case], {"EURUSD": self.csv}, self.journal, "rules-v1")
        self.assertEqual(len(restarted.snapshot("fixture")["decisions"]), 2)
        self.assertEqual(restarted.list_cases()[0]["status"], "finished")
        with self.assertRaises(ValueError):
            restarted.next("fixture")

    def test_wait_cannot_finish_before_the_documented_window_ends(self):
        self.engine.start("fixture")
        self.engine.record_decision("fixture", {"decision": "wait", "reason": "Still observing"})
        with self.assertRaisesRegex(ValueError, "window end"):
            self.engine.finish("fixture")

    def test_evaluable_case_requires_terminal_cursor_decision_to_finish(self):
        self.engine.start("fixture")
        for _ in range(16):
            self.engine.next("fixture")
        with self.assertRaisesRegex(ValueError, "decision at the window end"):
            self.engine.finish("fixture")
        final = self.engine.record_decision("fixture", {"decision": "wait", "reason": "No trade by window close"})
        self.assertEqual(final["cursor_utc"], "2015-01-07T18:00:00+00:00")
        self.assertTrue(self.engine.finish("fixture")["metric_eligible"])

    def test_anchor_must_match_a_real_closed_m15_open(self):
        self.engine.start("fixture")
        self.engine.next("fixture")
        self.engine.next("fixture")
        valid = "2015-01-07T14:15:00+00:00"
        self.engine.record_decision("fixture", {"decision": "wait", "reason": "Observed", "model1_anchor_at": valid})
        for invalid in ("2015-01-07T14:30:00+00:00", "2015-01-07T14:16:00+00:00", "2015-01-07T14:01:00+00:00"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                self.engine.record_decision("fixture", {"decision": "wait", "reason": "Observed", "model1_anchor_at": invalid})

    def test_trade_geometry_and_event_order_are_validated(self):
        self.engine.start("fixture")
        base = {"decision": "buy", "reason": "Uncertain read, prices are tentative", "entry_price": 1.2,
                "stop_loss": 1.1, "take_profit": 1.3}
        self.engine.record_decision("fixture", base)
        self.engine.record_decision("fixture", {"decision": "sell", "reason": "Uncertain read, retain caveat",
                                                 "entry_price": 1.2, "stop_loss": 1.3, "take_profit": 1.1})
        for fields in (
            {**base, "stop_loss": 1.25},
            {**base, "take_profit": 1.15},
            {**base, "entry_price": float("nan")},
            {"decision": "sell", "reason": "Read", "entry_price": 1.2, "stop_loss": 1.1, "take_profit": 1.3},
            {"decision": "wait", "reason": "Read", "model1_anchor_at": "2015-01-07T14:00:00+00:00",
             "model1_confirmed_at": "2015-01-07T14:10:00+00:00"},
            {"decision": "wait", "reason": "Read", "sweep_confirmed_at": "2015-01-07T14:30:00+00:00",
             "key_level_available_at": "2015-01-07T14:15:00+00:00"},
            {"decision": "wait", "reason": "Read", "key_level_available_at": "2015-01-07T14:30:00+00:00",
             "model1_anchor_at": "2015-01-07T14:15:00+00:00"},
        ):
            with self.subTest(fields=fields), self.assertRaises(ValueError):
                self.engine.record_decision("fixture", fields)

    def test_non_evaluable_case_requires_data_issue_and_is_excluded_from_metrics(self):
        lines = self.csv.read_text(encoding="utf-8").splitlines()
        self.csv.write_text("\n".join(line for line in lines if "2015.01.07\t14:15:00" not in line) + "\n", encoding="utf-8")
        self.engine.start("fixture")
        self.engine.next("fixture")
        self.engine.next("fixture")
        self.assertEqual(self.engine.snapshot("fixture")["case"]["integrity"], "non_evaluable")
        with self.assertRaisesRegex(ValueError, "data issue"):
            self.engine.record_decision("fixture", {"decision": "wait", "reason": "No signal"})
        self.engine.record_decision("fixture", {"decision": "data_issue", "reason": "Cannot assess",
                                                 "data_issue_reason": "Missing M15 candle"})
        result = self.engine.finish("fixture")
        self.assertFalse(result["metric_eligible"])
        self.assertEqual(self.engine.snapshot("fixture")["case"]["integrity"], "non_evaluable")

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
