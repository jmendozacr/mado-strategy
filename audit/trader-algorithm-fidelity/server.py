"""Local-only HTTP API for the causal replay MVP."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from engine import AuditEngine, CONTEXT_DEFAULT_PAGE_DAYS
from selection import PAIRS


HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]


def create_engine(journal: Path | None = None) -> AuditEngine:
    manifest = json.loads((HERE / "pilot_manifest.json").read_text(encoding="utf-8"))
    paths = {pair: next((REPO / "data").glob(f"{pair}_M15_*.csv")) for pair in PAIRS}
    rules = hashlib.sha256()
    for path in sorted((REPO / "docs").glob("charter-*.md")):
        rules.update(path.name.encode())
        rules.update(path.read_bytes())
    for relative in ("audit/2026-11-17-causal-lookahead-audit/causal_intrabar.py",
                     "audit/2026-11-17-causal-lookahead-audit/causal_anchor_v2.py",
                     "detector/core/config.py",
                     "detector/experimental/htf_trigger_1am_9am_backtest.py"):
        rules.update((REPO / relative).read_bytes())
    return AuditEngine(manifest["cases"], paths, journal or HERE / "runtime/events.jsonl", rules.hexdigest())


def handler_for(engine: AuditEngine):
    class Handler(BaseHTTPRequestHandler):
        def _send(self, status: int, payload: object):
            body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except (BrokenPipeError, ConnectionAbortedError, ConnectionResetError):
                return

        def _route(self):
            split = urlsplit(self.path)
            path = split.path
            if path == "/api/health" and self.command == "GET":
                return {"status": "ok"}
            if path == "/api/cases" and self.command == "GET":
                return engine.list_cases()
            segments = path.strip("/").split("/")
            if len(segments) != 4 or segments[:2] != ["api", "cases"]:
                raise KeyError("Unknown route")
            case_id, action = segments[2:]
            if self.command == "GET" and action == "replay":
                return engine.snapshot(case_id)
            if self.command == "GET" and action == "context":
                query = parse_qs(split.query)
                timeframe = query.get("timeframe", [""])[0]
                before_raw = query.get("before", [None])[0]
                before = None
                if before_raw:
                    before = datetime.fromisoformat(before_raw.replace("Z", "+00:00")) \
                        .astimezone(timezone.utc).replace(tzinfo=None)
                page_days = int(query.get("page_days", [str(0)])[0]) or CONTEXT_DEFAULT_PAGE_DAYS
                return engine.historical_context(case_id, timeframe, before, page_days)
            if self.command != "POST":
                raise KeyError("Unknown route")
            if action == "start":
                return engine.start(case_id)
            if action == "next":
                return engine.next(case_id)
            if action == "finish":
                return engine.finish(case_id)
            if action == "decisions":
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 65536:
                    raise ValueError("Invalid request body")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Decision must be an object")
                return engine.record_decision(case_id, payload)
            if action == "annotations":
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0 or length > 65536:
                    raise ValueError("Invalid request body")
                payload = json.loads(self.rfile.read(length))
                if not isinstance(payload, dict):
                    raise ValueError("Annotation must be an object")
                return engine.record_annotation(case_id, payload)
            raise KeyError("Unknown route")

        def do_GET(self):
            self._handle()

        def do_POST(self):
            self._handle()

        def _handle(self):
            try:
                result = self._route()
                if result is not None:
                    self._send(200, result)
            except KeyError:
                self._send(404, {"error": "Not found"})
            except (ValueError, json.JSONDecodeError) as error:
                self._send(400, {"error": str(error)})
            except Exception:
                self._send(500, {"error": "Internal server error"})

        def log_message(self, format, *args):
            return

    return Handler


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--journal", type=Path)
    args = parser.parse_args()
    server = ThreadingHTTPServer(("127.0.0.1", args.port), handler_for(create_engine(args.journal)))
    print(f"Audit API listening on http://127.0.0.1:{args.port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
