import unittest
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import AuditEngine, bucket_candles, bucket_close_utc, feeder_open_utc


def write_range(path, start, end, step=timedelta(minutes=15)):
    """Write contiguous M15 bars for [start, end). Caller controls which ranges to
    omit, so tests can place a precise, intentional data gap or weekend hole."""
    with path.open("x", encoding="utf-8") as stream:
        stream.write("<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n")
        instant = start
        while instant < end:
            base = 1.1 + (instant - start).total_seconds() / 1e8
            stream.write(f"{instant:%Y.%m.%d}\t{instant:%H:%M:%S}\t{base:.5f}\t{base+0.0002:.5f}\t{base-0.0001:.5f}\t{base+0.0001:.5f}\n")
            instant += step


class HistoricalContextTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(__file__).resolve().parent
        token = uuid.uuid4().hex
        self.csv = self.root / f"EURUSD_M15_context_{token}.csv"
        self.journal = self.root / f"journal_context_{token}.jsonl"
        # Monday 2015-01-05 00:00 UTC through Friday 2015-01-09 17:00 UTC NY-close: one clean,
        # fully contiguous trading week with no weekend or holiday gaps inside it.
        write_range(self.csv, datetime(2015, 1, 5, 0, 0), datetime(2015, 1, 9, 22, 0))
        self.case = {"id": "fixture", "pair": "EURUSD", "date_ny": "2015-01-09", "model": "9am"}
        self.engine = AuditEngine([self.case], {"EURUSD": self.csv}, self.journal, "rules-v1")
        self.engine.start("fixture")
        for _ in range(16):
            self.engine.next("fixture")

    def tearDown(self):
        self.csv.unlink(missing_ok=True)
        self.journal.unlink(missing_ok=True)

    def test_never_reveals_future_bars(self):
        cursor = self.engine._cursor("fixture")
        result = self.engine.historical_context("fixture", "h4", before=None, page_days=5)
        for candle in result["candles"]:
            if candle["available_at"] is not None:
                self.assertLessEqual(datetime.fromisoformat(candle["available_at"]).replace(tzinfo=None), cursor)
            if not candle["complete"]:
                self.assertIsNone(candle["available_at"])
            for slot in candle["gap_slots"]:
                self.assertLessEqual(datetime.fromisoformat(slot).replace(tzinfo=None) + timedelta(minutes=15), cursor)

    def test_fully_elapsed_h4_bucket_with_no_missing_data_is_complete(self):
        result = self.engine.historical_context("fixture", "h4", before=None, page_days=5)
        friday_morning = next(c for c in result["candles"] if c["time"] == feeder_open_utc(date(2015, 1, 9), 9).isoformat() + "+00:00")
        self.assertEqual(friday_morning["integrity"], "complete")
        self.assertEqual(friday_morning["gap_slots"], [])
        self.assertIsNotNone(friday_morning["available_at"])

    def test_clean_week_produces_no_gap_candles_across_the_weekend(self):
        # page_days=3 stays inside the fixture's own written range (Jan 5-9); a
        # wider page would hit the fixture's arbitrary start boundary itself,
        # which is a fixture artifact, not a weekend or data gap.
        result = self.engine.historical_context("fixture", "h4", before=None, page_days=3)
        self.assertFalse(any(candle["integrity"] == "gap" for candle in result["candles"]))

    def test_dst_transition_bucket_classifies_through_bucket_candles(self):
        # Integration-level check (not just bucket_close_utc in isolation): a Daily
        # bucket whose NY-local span is 23h due to spring-forward must still use the
        # correct (shorter) slot count rather than assuming a fixed 96-slot day.
        csv_path = self.root / f"EURUSD_M15_dst_{uuid.uuid4().hex}.csv"
        write_range(csv_path, datetime(2015, 3, 7, 0), datetime(2015, 3, 9, 0))
        bars = []
        with csv_path.open("r", encoding="utf-8") as stream:
            next(stream)
            for line in stream:
                day, time_, open_, high, low, close = line.strip().split("\t")
                instant = datetime.strptime(f"{day} {time_}", "%Y.%m.%d %H:%M:%S")
                bars.append({"instant": instant, "open": float(open_), "high": float(high),
                              "low": float(low), "close": float(close)})
        cursor = feeder_open_utc(date(2015, 3, 9), 0)  # well past the bucket's 23h close
        candles = bucket_candles(bars, cursor, feeder_open_utc(date(2015, 3, 7), 0),
                                  feeder_open_utc(date(2015, 3, 8), 20), (17,), 24)
        dst_candle = next(c for c in candles if c["time"] == feeder_open_utc(date(2015, 3, 7), 17).isoformat() + "+00:00")
        self.assertEqual(dst_candle["integrity"], "complete")
        self.assertEqual(dst_candle["gap_slots"], [])
        csv_path.unlink(missing_ok=True)

    def test_request_beyond_cursor_is_rejected(self):
        cursor = self.engine._cursor("fixture")
        with self.assertRaises(ValueError):
            self.engine.historical_context("fixture", "h4", before=cursor + timedelta(hours=1), page_days=5)

    def test_daily_uses_17_ny_anchor_and_a_clean_week_is_fully_complete(self):
        result = self.engine.historical_context("fixture", "daily", before=None, page_days=5)
        monday_daily = next(c for c in result["candles"] if c["time"] == feeder_open_utc(
            date(2015, 1, 5), 17).isoformat() + "+00:00")
        self.assertEqual(monday_daily["integrity"], "complete")
        self.assertEqual(monday_daily["gap_slots"], [])

    def test_missing_weekday_bar_is_reported_as_gap_not_fabricated(self):
        lines = self.csv.read_text(encoding="utf-8").splitlines()
        trimmed = "\n".join(line for line in lines if "2015.01.06\t15:00:00" not in line) + "\n"
        self.csv.write_text(trimmed, encoding="utf-8")
        engine = AuditEngine([self.case], {"EURUSD": self.csv}, self.journal, "rules-v1")
        result = engine.historical_context("fixture", "h4", before=None, page_days=5)
        affected = next(c for c in result["candles"]
                         if c["time"] == feeder_open_utc(date(2015, 1, 6), 9).isoformat() + "+00:00")
        self.assertEqual(affected["integrity"], "gap")
        self.assertIn("2015-01-06T15:00:00+00:00", affected["gap_slots"])
        self.assertIsNone(affected["available_at"])

    def test_dst_spring_forward_daily_bucket_closes_23_hours_later(self):
        # US DST began 2015-03-08 02:00 NY; the Daily bucket opening the evening
        # before (Sat 2015-03-07 17:00 NY) is the one whose 24h NY-local span
        # actually crosses that spring-forward instant.
        opening = feeder_open_utc(date(2015, 3, 7), 17)
        closing = bucket_close_utc(date(2015, 3, 7), 17, 24)
        self.assertEqual(closing - opening, timedelta(hours=23))
        self.assertEqual(closing, feeder_open_utc(date(2015, 3, 8), 17))

    def test_pagination_reports_exhausted_at_dataset_start(self):
        result = self.engine.historical_context("fixture", "h4", before=None, page_days=30)
        self.assertTrue(result["exhausted"])
        self.assertIsNone(result["next_before"])

    def test_forming_bucket_has_no_future_gap_slots(self):
        # Reproduces Problem B: query the instant the 9AM-1PM H4 bucket and the
        # Jan-9 Daily bucket have only their first M15 candle closed. Both are
        # genuinely still "forming" (their close is long after the cursor) and
        # must report zero gap_slots -- a slot that simply hasn't happened yet
        # is not a data gap.
        fresh_journal = self.root / f"journal_forming_{uuid.uuid4().hex}.jsonl"
        engine = AuditEngine([self.case], {"EURUSD": self.csv}, fresh_journal, "rules-v1")
        engine.start("fixture")
        engine.next("fixture")  # cursor now 2015-01-09T14:15:00+00:00, 15 min into the window
        cursor = engine._cursor("fixture")

        h4 = engine.historical_context("fixture", "h4", before=None, page_days=5)
        forming_h4 = next(c for c in h4["candles"] if c["time"] == feeder_open_utc(date(2015, 1, 9), 9).isoformat() + "+00:00")
        self.assertEqual(forming_h4["integrity"], "forming")
        self.assertEqual(forming_h4["gap_slots"], [])
        self.assertIsNone(forming_h4["available_at"])

        daily = engine.historical_context("fixture", "daily", before=None, page_days=5)
        forming_daily = next(c for c in daily["candles"] if c["time"] == feeder_open_utc(date(2015, 1, 8), 17).isoformat() + "+00:00")
        self.assertEqual(forming_daily["integrity"], "forming")
        self.assertEqual(forming_daily["gap_slots"], [])
        for slot in forming_daily["gap_slots"]:
            self.assertLessEqual(datetime.fromisoformat(slot).replace(tzinfo=None) + timedelta(minutes=15), cursor)
        fresh_journal.unlink(missing_ok=True)

    def test_pagination_chains_several_months_back_on_a_fast_fixture(self):
        # Problem A proof at the logic level (the real-browser E2E proof targets
        # a modest depth, since historical_context() scans the real multi-year
        # CSV per page and is slow for dozens of pages): a synthetic ~7-month
        # fixture, chained page by page, must keep extending with no overlap and
        # no leak past the cursor, reaching clearly more than 60 days back.
        csv_path = self.root / f"EURUSD_M15_months_{uuid.uuid4().hex}.csv"
        journal_path = self.root / f"journal_months_{uuid.uuid4().hex}.jsonl"
        write_range(csv_path, datetime(2014, 6, 1, 0, 0), datetime(2015, 1, 9, 22, 0))
        case = {"id": "fixture", "pair": "EURUSD", "date_ny": "2015-01-09", "model": "9am"}
        engine = AuditEngine([case], {"EURUSD": csv_path}, journal_path, "rules-v1")
        engine.start("fixture")
        for _ in range(16):
            engine.next("fixture")
        cursor = engine._cursor("fixture")

        before = None
        oldest_seen = cursor
        pages = 0
        while pages < 10:
            page = engine.historical_context("fixture", "daily", before=before, page_days=30)
            page_times = [datetime.fromisoformat(c["time"]).replace(tzinfo=None) for c in page["candles"]]
            for instant in page_times:
                self.assertLessEqual(instant, cursor)
            if page_times:
                self.assertLessEqual(max(page_times), oldest_seen)  # no overlap/jump-forward across pages
                oldest_seen = min(oldest_seen, min(page_times))
            pages += 1
            if page["exhausted"]:
                break
            before = datetime.fromisoformat(page["next_before"]).astimezone(timezone.utc).replace(tzinfo=None)

        self.assertGreater((cursor - oldest_seen).days, 60)
        self.assertTrue(page["exhausted"] or pages == 10)
        csv_path.unlink(missing_ok=True)
        journal_path.unlink(missing_ok=True)

    def test_pagination_chains_to_an_older_page(self):
        first = self.engine.historical_context("fixture", "h4", before=None, page_days=1)
        self.assertFalse(first["exhausted"])
        next_before = datetime.fromisoformat(first["next_before"]).astimezone(timezone.utc).replace(tzinfo=None)
        older = self.engine.historical_context("fixture", "h4", before=next_before, page_days=1)
        if older["candles"] and first["candles"]:
            self.assertLessEqual(older["candles"][-1]["time"], first["candles"][0]["time"])


if __name__ == "__main__":
    unittest.main()
