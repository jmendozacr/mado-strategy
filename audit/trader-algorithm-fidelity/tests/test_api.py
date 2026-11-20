import json
import sys
import threading
import unittest
import urllib.request
import uuid
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import AuditEngine
import server
from server import handler_for


class ApiBoundaryTests(unittest.TestCase):
    def setUp(self):
        root = Path(__file__).resolve().parent
        token = uuid.uuid4().hex
        self.csv = root / f"EURUSD_M15_fixture_{token}.csv"
        self.journal = root / f"journal_{token}.jsonl"
        with self.csv.open("x", encoding="utf-8") as stream:
            stream.write("<DATE>\t<TIME>\t<OPEN>\t<HIGH>\t<LOW>\t<CLOSE>\n")
            for i in range(100):
                at = datetime(2015, 1, 7) + i * timedelta(minutes=15)
                stream.write(f"{at:%Y.%m.%d}\t{at:%H:%M:%S}\t1.1\t1.2\t1.0\t1.15\n")
        self.original = self.csv.read_bytes()
        case = {"id": "fixture", "pair": "EURUSD", "date_ny": "2015-01-07", "model": "9am",
                "category": "hidden_trade"}
        self.engine = AuditEngine([case], {"EURUSD": self.csv}, self.journal, "rules-v1")
        self.http = ThreadingHTTPServer(("127.0.0.1", 0), handler_for(self.engine))
        self.thread = threading.Thread(target=self.http.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.http.server_port}"

    def tearDown(self):
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=2)
        self.assertEqual(self.csv.read_bytes(), self.original)
        self.csv.unlink(missing_ok=True)
        self.journal.unlink(missing_ok=True)

    def request(self, route, method="GET", payload=None):
        body = json.dumps(payload).encode("utf-8") if payload is not None else None
        request = urllib.request.Request(self.base + route, data=body, method=method)
        if body is not None:
            request.add_header("Content-Type", "application/json")
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.load(response)

    def test_api_never_delivers_future_bars_or_selection_metadata(self):
        listing = self.request("/api/cases")
        self.assertEqual(set(listing[0]), {"id", "pair", "date_ny", "model", "status"})
        self.request("/api/cases/fixture/start", "POST")
        snapshot = self.request("/api/cases/fixture/next", "POST")
        cursor = datetime.fromisoformat(snapshot["cursor_utc"])
        self.assertTrue(all(datetime.fromisoformat(bar["available_at"]) <= cursor for bar in snapshot["m15"]))
        self.assertTrue(all(bar["available_at"] is None for bar in snapshot["h4"] if not bar["complete"]))
        response = json.dumps(snapshot).lower()
        for forbidden in ("hidden_trade", "category", "outcome", "selected_by", "algorithm"):
            self.assertNotIn(forbidden, response)

    def test_case_cannot_finish_without_human_decision(self):
        self.request("/api/cases/fixture/start", "POST")
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/api/cases/fixture/finish", "POST")
        self.assertEqual(error.exception.code, 400)

    def test_api_rejects_anchor_whose_m15_has_not_closed(self):
        snapshot = self.request("/api/cases/fixture/start", "POST")
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.request("/api/cases/fixture/decisions", "POST", {
                "decision": "wait", "reason": "Anchor is still forming",
                "model1_anchor_at": snapshot["cursor_utc"],
            })
        self.assertEqual(error.exception.code, 400)

    def test_api_server_does_not_serve_frontend_or_private_files(self):
        self.assertEqual(self.request("/api/health"), {"status": "ok"})
        for path in ("/", "/app.js", "/pilot_manifest.json", "/runtime/events.jsonl", "/selection.py",
                     "/../data/EURUSD_M15_200305042100_202611122345.csv"):
            with self.assertRaises(urllib.error.HTTPError) as error:
                urllib.request.urlopen(self.base + path, timeout=5)
            self.assertEqual(error.exception.code, 404)

    def test_human_opportunity_can_be_saved_on_algorithm_no_signal_case(self):
        self.engine.cases["fixture"]["category"] = "no_signal"
        self.request("/api/cases/fixture/start", "POST")
        decision = self.request("/api/cases/fixture/decisions", "POST", {
            "decision": "buy", "reason": "Human marked Model #1", "model1_exists": True,
            "entry_price": 1.15, "stop_loss": 1.14, "take_profit": 1.18,
        })
        self.assertEqual(decision["decision"], "buy")
        self.assertEqual(self.request("/api/cases/fixture/finish", "POST")["status"], "finished")


class StartupTests(unittest.TestCase):
    def test_cli_uses_isolated_journal_when_requested(self):
        journal = Path("runtime/browser-check.jsonl")
        with patch("sys.argv", ["server.py", "--port", "8766", "--journal", str(journal)]), \
             patch("server.ThreadingHTTPServer"), \
             patch("server.create_engine") as create_engine:
            server.main()
        create_engine.assert_called_once_with(journal)


if __name__ == "__main__":
    unittest.main()
