import csv
from html.parser import HTMLParser
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from blame_cli.inputs import load_inputs
from blame_cli.labels import score_labels, write_labels
from blame_cli.model import CLASSES
from blame_cli.reports import build_report, markdown, static_html
from test_detectors import rec


ROOT = Path(__file__).resolve().parents[1]


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.records, self.warnings = load_inputs([str(ROOT / "fixtures/synthetic.jsonl")])
        self.report = build_report(self.records, self.warnings)

    def test_fixture_shape_and_all_expected_verdicts(self):
        self.assertEqual(len(self.records), 36)
        self.assertEqual(len({r.task_id for r in self.records}), 3)
        self.assertEqual({r.model for r in self.records}, {"alpha", "beta", "gamma"})
        self.assertEqual({r.judge_run for r in self.records}, {1, 2})
        self.assertEqual({row["class"]: row["lost_items"] for row in self.report["by_class"]},
                         dict(zip(CLASSES, (4, 1, 6, 4, 6))))
        self.assertEqual(self.report["lost_points"], 21)
        # A formal greeting mismatch has no hidden anchors and some models pass.
        controls = [v for v in self.report["items"] if v["record"]["rubric_item_id"] == "formal"]
        self.assertEqual(len(controls), 4)
        self.assertTrue(all(v["label"] == "genuine_failure" and not v["matches"] for v in controls))
        for item in self.report["items"]:
            self.assertTrue(item["evidence"])
            self.assertTrue(0 <= item["confidence"] <= 1)
        flip = next(v for v in self.report["items"] if v["label"] == "judge_unstable")
        self.assertEqual(flip["evidence"]["flip_rate"], 1)

    def test_partial_loss_and_all_pass_model(self):
        report = build_report([rec(score=0.75), rec(model="beta", score=1)])
        self.assertEqual(report["lost_items"], 1)
        self.assertEqual(report["lost_points"], 0.25)
        self.assertEqual(report["by_model"][1]["lost_items"], 0)
        all_pass = build_report([rec(score=1)])
        self.assertEqual(all_pass["items"], [])
        self.assertEqual(all_pass["lost_points"], 0)

    def test_html_is_self_contained_and_escapes_untrusted_text(self):
        class Tags(HTMLParser):
            def __init__(self):
                super().__init__()
                self.tags = []
                self.attrs = []

            def handle_starttag(self, tag, attrs):
                self.tags.append(tag)
                self.attrs.extend(attrs)

        unsafe = '<script src="https://bad.example/x">& alert(1)</script> | text'
        report = build_report([rec(output=unsafe, instruction=unsafe, model=unsafe)])
        markup = static_html(report)
        parsed = Tags()
        parsed.feed(markup)
        self.assertIn("&lt;script", markup)
        self.assertNotIn("script", parsed.tags)
        self.assertEqual(parsed.tags.count("details"), 1)
        self.assertEqual(parsed.tags.count("table"), 2)
        self.assertTrue(all(name not in ("src", "href", "onclick") for name, _ in parsed.attrs))
        md = markdown(report)
        self.assertNotIn("<script", md)
        self.assertIn("&#124;", md)

    def test_cli_end_to_end_and_repeatable_reports(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            dest = Path(tmp) / "report"
            command = [sys.executable, "-m", "blame_cli", "report", "fixtures/synthetic.jsonl", "--out", str(dest)]
            result = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual({p.name for p in dest.iterdir()}, {"report.md", "report.json", "report.html"})
            first = {p.name: p.read_bytes() for p in dest.iterdir()}
            self.assertEqual(json.loads(first["report.json"])["lost_items"], 21)
            rerun = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(rerun.returncode, 0, rerun.stderr)
            self.assertEqual(first, {p.name: p.read_bytes() for p in dest.iterdir()})
            labels = Path(tmp) / "labels.csv"
            label = subprocess.run([str(ROOT / "blame"), "label", "fixtures/synthetic.jsonl", "--out", str(labels)],
                                   cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(label.returncode, 0, label.stderr)
            score = subprocess.run([str(ROOT / "blame"), "score", str(labels)],
                                   cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(score.returncode, 0, score.stderr)
            self.assertEqual(json.loads(score.stdout)["unlabeled_rows"], 21)

    def test_bad_input_fails_without_writing_report(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "invalid.jsonl"
            path.write_text("not json\n", encoding="utf-8")
            dest = Path(tmp) / "out"
            result = subprocess.run([sys.executable, "-m", "blame_cli", "report", str(path), "--out", str(dest)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("line 1", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(dest.exists())


class LabelTests(unittest.TestCase):
    def csv_path(self, tmp, rows):
        path = Path(tmp) / "labels.csv"
        with path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=["record_id", "predicted_label", "detector_labels", "human_label"])
            writer.writeheader()
            writer.writerows(rows)
        return str(path)

    def test_template_preserves_text_and_blanks(self):
        report = build_report([rec(output='a, "quote"\nand another line')])
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "labels.csv"
            write_labels(report, str(path))
            with path.open(newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["human_label"], "")
            self.assertEqual(rows[0]["output"], 'a, "quote"\nand another line')
            result = score_labels(str(path))
            self.assertEqual(result["labeled_rows"], 0)
            self.assertEqual(result["unlabeled_rows"], 1)
            self.assertIsNone(result["per_detector"]["infra"]["precision"])

    def test_precision_recall_with_false_positives_false_negatives_and_overlap(self):
        rows = [
            {"record_id": "1", "predicted_label": "infra", "detector_labels": "infra", "human_label": "infra"},
            {"record_id": "2", "predicted_label": "infra", "detector_labels": "infra", "human_label": "genuine_failure"},
            {"record_id": "3", "predicted_label": "genuine_failure", "detector_labels": "", "human_label": "infra"},
            {"record_id": "4", "predicted_label": "infra", "detector_labels": "infra|unstated_requirement", "human_label": "unstated_requirement"},
            {"record_id": "5", "predicted_label": "infra", "detector_labels": "infra", "human_label": ""},
        ]
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            result = score_labels(self.csv_path(tmp, rows))
        infra = result["per_detector"]["infra"]
        self.assertEqual((infra["tp"], infra["fp"], infra["fn"]), (1, 2, 1))
        self.assertAlmostEqual(infra["precision"], 1 / 3)
        self.assertEqual(infra["recall"], 0.5)
        self.assertEqual(result["per_detector"]["unstated_requirement"]["recall"], 1)
        self.assertEqual(result["per_verdict"]["unstated_requirement"]["recall"], 0)
        self.assertEqual(result["labeled_rows"], 4)
        self.assertEqual(result["unlabeled_rows"], 1)
        self.assertIsNone(result["per_detector"]["judge_unstable"]["recall"])

    def test_reject_invalid_labels_duplicate_ids_and_inconsistent_predictions(self):
        good = {"record_id": "1", "predicted_label": "infra", "detector_labels": "infra", "human_label": "infra"}
        cases = [[good, good]]
        for changes in ({"record_id": ""}, {"human_label": "made_up"}, {"predicted_label": "made_up"},
                        {"detector_labels": "infra|infra"}, {"detector_labels": "genuine_failure"},
                        {"detector_labels": ""}):
            cases.append([good | changes])
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            for rows in cases:
                with self.subTest(rows=rows):
                    with self.assertRaises(ValueError):
                        score_labels(self.csv_path(tmp, rows))


if __name__ == "__main__":
    unittest.main()
