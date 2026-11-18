"""Record schema 2: optional fields, ungraded and reference records, None-safe output."""

from dataclasses import asdict
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from blame_cli.detectors import triage
from blame_cli.inputs import load_inputs
from blame_cli.labels import score_labels, write_labels
from blame_cli.model import Record, V1_FIELDS, record_dict, validate
from blame_cli.reports import MISSING, build_report, markdown, static_html
from test_detectors import rec


ROOT = Path(__file__).resolve().parents[1]


def bare(**changes) -> Record:
    """A record as a results-only format gives it: no instruction, rubric text or output."""
    values = {"task_id": "t1", "model": "", "agent": "agent-a", "run_id": "trial-1", "instruction": None,
              "rubric_item_id": "reward", "rubric_item_text": None, "output": None, "score": 0.0,
              "judge_reasoning": ""}
    return validate(Record(**(values | changes)))


class RecordV2Tests(unittest.TestCase):
    def test_v1_record_dict_and_id_ignore_default_v2_fields(self):
        record = Record.from_dict(asdict(rec()))
        self.assertEqual(tuple(record_dict(record)), V1_FIELDS)
        self.assertEqual(Record.from_dict(record_dict(record)).record_id, record.record_id)
        self.assertEqual(Record.from_dict(asdict(record)), record)
        tagged = Record.from_dict(asdict(record) | {"agent": "a", "job_id": "j"})
        self.assertEqual(record_dict(tagged) | {}, record_dict(record) | {"agent": "a", "job_id": "j"})
        self.assertNotEqual(tagged.record_id, record.record_id)
        self.assertEqual((record.system, tagged.system), ("alpha", "a / alpha"))
        self.assertEqual(tagged.attempt_key, ("task", "a / alpha", "run"))

    def test_generic_reader_accepts_v2_keys_and_rejects_bad_values(self):
        base = asdict(rec())
        ok = Record.from_dict(base | {"role": "reference", "error_kind": "agent", "task_version": "v3", "error": "x"})
        self.assertEqual((ok.role, ok.error_kind, ok.task_version), ("reference", "agent", "v3"))
        for change in ({"role": "judge"}, {"error_kind": "network"}, {"agent": ""}, {"job_id": 7},
                       {"task_version": ["v1"]}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                Record.from_dict(base | change)

    def test_null_score_needs_an_error(self):
        base = asdict(rec())
        ungraded = Record.from_dict(base | {"score": None, "error": "verifier crashed"})
        self.assertIsNone(ungraded.score)
        for change in ({"score": None}, {"score": None, "error": "  "}):
            with self.subTest(change=change), self.assertRaisesRegex(ValueError, "score must be a finite number"):
                Record.from_dict(base | change)
        missing = dict(base, error="boom")
        del missing["score"]
        with self.assertRaisesRegex(ValueError, "score must be a finite number"):
            Record.from_dict(missing)

    def test_validate_rules_for_other_readers(self):
        self.assertEqual(bare().system, "agent-a")
        for change in ({"task_id": " "}, {"run_id": ""}, {"rubric_item_id": ""}, {"agent": None},
                       {"score": None}, {"score": 1.5}, {"score": float("nan")}, {"score": True},
                       {"role": "oracle"}, {"error_kind": "other"}):
            with self.subTest(change=change), self.assertRaises(ValueError):
                bare(**change)

    def test_conflicting_error_kind_for_one_attempt_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "in.jsonl"
            rows = [asdict(rec(error="x")) | {"error_kind": "infra"},
                    asdict(rec(error="x", rubric_item_id="other")) | {"error_kind": "setup"}]
            path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "conflicting error_kind"):
                load_inputs([str(path)])


class ReportV2Tests(unittest.TestCase):
    def test_counting_separates_ungraded_and_reference_records(self):
        records = [bare(score=1.0), bare(run_id="trial-2", score=0.25),
                   bare(run_id="trial-3", score=None, error="no reward file"),
                   bare(agent="oracle", role="reference", score=0.0),
                   bare(agent="oracle", role="reference", run_id="trial-2", score=1.0)]
        report = build_report(records)
        self.assertEqual((report["scored_items"], report["lost_items"], report["lost_points"],
                          report["ungraded_items"], report["reference_items"]), (2, 1, 0.75, 1, 2))
        self.assertIn("1 attempts were never graded and are listed as ungraded.", report["counting"])
        self.assertEqual([item["record"]["score"] for item in report["items"]], [0.25, None])
        self.assertEqual([row["model"] for row in report["by_model"]], ["agent-a"])
        self.assertEqual((report["by_model"][0]["scored_items"], report["by_model"][0]["ungraded_items"]), (2, 1))
        self.assertEqual(sum(row["lost_items"] for row in report["by_class"]), 1)
        self.assertEqual(sum(row["ungraded_items"] for row in report["by_class"]), 1)
        task = report["by_task"][0]
        self.assertEqual((task["task_id"], task["systems_attempted"], task["systems_failed"], task["reference"]),
                         ("t1", 1, 1, "passed 1 of 2 attempts"))
        self.assertTrue(task["next_step"])
        self.assertEqual(task["labels"], {"infra": 1, "reference_flaky": 2, "attempts_flip": 1})

    def test_task_table_without_reference_and_with_ungraded_reference(self):
        self.assertEqual(build_report([bare()])["by_task"][0]["reference"], "no reference run supplied")
        report = build_report([bare(), bare(agent="oracle", role="reference", score=None, error="x")])
        self.assertEqual(report["by_task"][0]["reference"], "passed 0 of 0 attempts; 1 not graded")
        self.assertEqual(build_report([bare(score=1.0)])["by_task"], [])

    def test_missing_text_fields_pass_through_all_three_renderers(self):
        records = [bare(), bare(run_id="trial-2", score=None, error="no reward file")]
        self.assertEqual(len(triage(records)), 2)
        report = build_report(records)
        json.dumps(report, allow_nan=False)
        for text in (markdown(report), static_html(report)):
            self.assertIn(MISSING, text)
            self.assertIn("not graded" if text.startswith("#") else "no reward file", text)
            self.assertIn("rule strength", text)
            self.assertIn("Failed tasks", text)
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "labels.csv"
            write_labels(report, str(path))
            with path.open(encoding="utf-8", newline="") as handle:
                rows = list(csv.DictReader(handle))
            self.assertEqual([row["score"] for row in rows], ["0.0", ""])
            self.assertEqual(json.loads(rows[0]["original_record_json"]), record_dict(records[0]))
            self.assertEqual(score_labels(str(path))["unlabeled_rows"], 2)


class FormatFlagTests(unittest.TestCase):
    def run_cli(self, *args):
        return subprocess.run([sys.executable, "-m", "blame_cli", *args], cwd=ROOT, text=True, capture_output=True)

    def test_format_flag_forces_a_reader(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            out = str(Path(tmp) / "out")
            self.assertEqual(self.run_cli("report", "fixtures/inspect.json", "--format", "inspect", "--out", out).returncode, 0)
            forced = self.run_cli("report", "fixtures/inspect.json", "--format", "generic", "--out", out)
            self.assertEqual(forced.returncode, 2)
            self.assertIn("fixtures/inspect.json: line 1", forced.stderr)
            self.assertEqual(self.run_cli("label", "fixtures/synthetic.jsonl", "--format", "generic",
                                          "--out", str(Path(tmp) / "l.csv")).returncode, 0)
            self.assertEqual(self.run_cli("report", "fixtures/synthetic.jsonl", "--format", "nope", "--out", out).returncode, 2)

    def test_unrecognised_directory_is_an_error(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            result = self.run_cli("report", tmp, "--out", str(Path(tmp) / "out"))
            self.assertEqual(result.returncode, 2)
            self.assertIn("blame: ", result.stderr)


if __name__ == "__main__":
    unittest.main()
