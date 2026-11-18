"""Outputs for v1 inputs must match what the 0.1.0 code (commit ce0a271) wrote.

The files in tests/golden/v1 were produced by that code and are never regenerated.
"""

import json
import os
from pathlib import Path
import tempfile
import unittest

from blame_cli.inputs import load_inputs
from blame_cli.labels import write_labels
from blame_cli.model import CLASSES, V1_FIELDS
from blame_cli.reports import build_report, markdown


ROOT = Path(__file__).resolve().parents[1]
GOLDEN = ROOT / "tests/golden"


def report_for(*inputs: str) -> dict:
    records, warnings = load_inputs([str(ROOT / name) for name in inputs])
    return build_report(records, warnings)


def v1_projection(report: dict, golden: dict) -> dict:
    """What a schema 2 report says about a v1 input, in v1 shape.

    Schema 2 adds keys and label rows; it must not change any value v1 reported.
    """
    def keep(row, like):
        return {key: row[key] for key in like}

    names = [row["class"] for row in golden["by_class"]]
    classes = {row["class"]: row for row in report["by_class"]}
    projected = {key: report[key] for key in golden}
    projected["schema_version"] = golden["schema_version"]
    projected["by_class"] = [keep(classes[name], golden["by_class"][0]) for name in names]
    projected["by_model"] = [keep(row, golden["by_model"][0]) for row in report["by_model"]]
    projected["items"] = [{**item, "record": keep(item["record"], V1_FIELDS)} for item in report["items"]]
    return projected


class V1GoldenTests(unittest.TestCase):
    def test_reports_match_0_1_0(self):
        for name, source in (("synthetic", "fixtures/synthetic.jsonl"), ("inspect", "fixtures/inspect.json")):
            with self.subTest(name=name):
                golden = json.loads((GOLDEN / f"v1/{name}.report.json").read_text(encoding="utf-8"))
                report = report_for(source)
                self.assertEqual(report["schema_version"], 2)
                self.assertEqual(v1_projection(report, golden), golden)
                # Nothing a v1 input cannot have: no new label, ungraded or reference count.
                v1_names = {row["class"] for row in golden["by_class"]}
                self.assertFalse([row for row in report["by_class"]
                                  if row["class"] not in v1_names and (row["lost_items"] or row["ungraded_items"])])
                self.assertEqual((report["ungraded_items"], report["reference_items"]), (0, 0))
                self.assertTrue(all(set(item["record"]) == set(V1_FIELDS) for item in report["items"]))

    def test_record_ids_match_0_1_0(self):
        records, _ = load_inputs([str(ROOT / "fixtures/synthetic.jsonl")])
        golden = (GOLDEN / "v1/synthetic.record_ids.txt").read_text(encoding="utf-8").split()
        self.assertEqual(len(golden), 36)
        self.assertEqual([record.record_id for record in records], golden)

    def test_labels_csv_is_byte_identical(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "labels.csv"
            write_labels(report_for("fixtures/synthetic.jsonl"), str(path))
            self.assertEqual(path.read_bytes(), (GOLDEN / "v1/synthetic.labels.csv").read_bytes())


BANNED_WORDING = ("broken test", "bad task", "flaky grader", "model at fault")


def check_golden(case: unittest.TestCase, name: str, report: dict) -> None:
    """Compare a report with tests/golden/<name>.report.{json,md}.

    UPDATE_GOLDEN=1 make test rewrites them; review the diff before committing.
    """
    texts = {"json": json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
             "md": markdown(report)}
    for suffix, text in texts.items():
        path = GOLDEN / f"{name}.report.{suffix}"
        if os.environ.get("UPDATE_GOLDEN") == "1":
            path.write_text(text, encoding="utf-8")
        case.assertEqual(text, path.read_text(encoding="utf-8"), f"{path.name} differs")
        for phrase in BANNED_WORDING:
            case.assertNotIn(phrase, text.lower())
    case.assertNotIn("/Users/", texts["json"])
    case.assertNotIn("/home/", texts["json"])


class V2GoldenTests(unittest.TestCase):
    def test_v2_fixture_report(self):
        report = report_for("fixtures/v2.jsonl")
        check_golden(self, "v2", report)
        # Every label is the verdict of at least one item.
        self.assertEqual({item["label"] for item in report["items"]}, set(CLASSES))
        self.assertEqual([row["class"] for row in report["by_class"]], list(CLASSES))
        for item in report["items"]:
            if item["label"] not in ("infra", "judge_unstable", "unstated_requirement", "genuine_failure"):
                self.assertIn("observed", item["evidence"])
        for row in report["by_task"]:
            self.assertTrue(row["next_step"].endswith("."))


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
