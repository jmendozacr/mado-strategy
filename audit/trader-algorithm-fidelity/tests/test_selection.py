import sys
import json
from collections import Counter
import unittest
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from selection import PAIRS, generate_manifest, no_sweep_proven


def bars(start, count, high=1.2, low=1.1):
    return [{"instant": start + i * timedelta(minutes=15), "open": 1.15,
             "high": high, "low": low, "close": 1.15} for i in range(count)]


class SelectionTests(unittest.TestCase):
    def test_no_sweep_requires_complete_reference_and_activation(self):
        reference = bars(datetime(2015, 1, 7, 10), 16)
        activation = bars(datetime(2015, 1, 7, 14), 8, high=1.19, low=1.11)
        self.assertTrue(no_sweep_proven(reference + activation, datetime(2015, 1, 7, 10),
                                        datetime(2015, 1, 7, 14), datetime(2015, 1, 7, 16)))
        self.assertFalse(no_sweep_proven(reference + activation[:-1], datetime(2015, 1, 7, 10),
                                         datetime(2015, 1, 7, 14), datetime(2015, 1, 7, 16)))
        self.assertFalse(no_sweep_proven(reference + bars(datetime(2015, 1, 7, 14), 8, high=1.21),
                                         datetime(2015, 1, 7, 10), datetime(2015, 1, 7, 14),
                                         datetime(2015, 1, 7, 16)))

    def test_checked_in_pilot_reproduces_from_fixed_seed(self):
        here = Path(__file__).resolve().parents[1]
        root = here.parents[1]
        paths = {pair: next((root / "data").glob(f"{pair}_M15_*.csv")) for pair in PAIRS}
        trades = root / "audit/2026-11-17-causal-lookahead-audit/trades_d3_c2_2015plus_run2.csv"
        recorded = json.loads((here / "pilot_manifest.json").read_text(encoding="utf-8"))["cases"]
        self.assertEqual(generate_manifest(paths, trades), recorded)
        self.assertEqual(Counter(case["category"] for case in recorded),
                         {"with_trade": 10, "no_signal": 10, "boundary_or_gap": 10})


if __name__ == "__main__":
    unittest.main()
