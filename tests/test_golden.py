"""Outputs for v1 inputs must match what the 0.1.0 code (commit ce0a271) wrote.

The files in tests/golden/v1 were produced by that code and are never regenerated.
"""

import json
from pathlib import Path
import tempfile
import unittest

from blame_cli.inputs import load_inputs
from blame_cli.labels import write_labels
from blame_cli.reports import build_report


ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests/golden"


def report_for(*inputs: str) -> dict:
    records, warnings = load_inputs([str(ROOT / name) for name in inputs])
    return build_report(records, warnings)


class V1GoldenTests(unittest.TestCase):
    def test_reports_match_0_1_0(self):
        for name, source in (("synthetic", "fixtures/synthetic.jsonl"), ("inspect", "fixtures/inspect.json")):
            with self.subTest(name=name):
                golden = json.loads((GOLDEN / f"v1/{name}.report.json").read_text(encoding="utf-8"))
                self.assertEqual(report_for(source), golden)

    def test_labels_csv_is_byte_identical(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "labels.csv"
            write_labels(report_for("fixtures/synthetic.jsonl"), str(path))
            self.assertEqual(path.read_bytes(), (GOLDEN / "v1/synthetic.labels.csv").read_bytes())


ARENA_HARD = ROOT / "data/arena_hard/generic.jsonl"


class ArenaHardTotalsTests(unittest.TestCase):
    @unittest.skipUnless(ARENA_HARD.is_file(), "data/arena_hard/generic.jsonl is absent (gitignored study data); totals not checked")
    def test_published_totals_are_reproduced(self):
        report = report_for("data/arena_hard/generic.jsonl")
        self.assertEqual((report["scored_items"], report["lost_items"], report["lost_points"]), (3000, 1826, 1609.0))
        counts = {row["class"]: row["lost_items"] for row in report["by_class"] if row["lost_items"]}
        self.assertEqual(counts, {"judge_unstable": 606, "item_everyone_loses": 204, "genuine_failure": 1016})


if __name__ == "__main__":
    unittest.main()
