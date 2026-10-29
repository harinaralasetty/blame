"""Synthetic regressions for the independent review findings."""

from dataclasses import asdict
import csv
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from blame_cli.detectors import HeuristicReasoner, triage
from blame_cli.inputs import inspect_records, load_inputs
from blame_cli.labels import score_labels, write_labels
from blame_cli.model import Record
from blame_cli.reports import build_report
from test_detectors import rec


ROOT = Path(__file__).resolve().parents[1]


class ReviewRound1Tests(unittest.TestCase):
    def test_1_explanations_and_bare_numbers_are_not_infra(self):
        outputs = (
            "429", "500", "503",
            "Timeout is a useful mechanism; configure retries and continue.",
            "Rate limit algorithms include token buckets and sliding windows.",
            "HTTP 500 means the server encountered an unexpected condition.",
            "Error: timeout is a useful mechanism.",
            "Request timed out. This phrase describes a possible failure.",
            "500 Internal Server Error means something went wrong.",
            "Missing artifact is a term used in build systems.",
        )
        for output in outputs:
            with self.subTest(output=output):
                self.assertEqual(triage([rec(output=output)])[0]["label"], "genuine_failure")
        # An error-shaped answer must not hide actual judge disagreement.
        records = [rec(output="429"), rec(output="429", score=1, judge_run=2)]
        self.assertEqual(triage(records)[0]["label"], "judge_unstable")

    def test_2_safe_csv_cells_retain_original_record(self):
        for payload in ("=1+1", "+1+1", "-1+1", "@SUM(1,1)", "\t=1+1", "\r=1+1", "\n=1+1", "  =1+1"):
            with self.subTest(payload=repr(payload)), tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                record = rec(task_id=payload, model=payload, run_id=payload,
                             rubric_item_id=payload, instruction=payload,
                             rubric_item_text=payload, output=payload, judge_reasoning=payload)
                path = Path(tmp) / "labels.csv"
                write_labels(build_report([record]), str(path))
                with path.open(encoding="utf-8", newline="") as handle:
                    row = next(csv.DictReader(handle))
                for field in ("task_id", "model", "run_id", "rubric_item_id", "instruction",
                              "rubric_item_text", "output", "judge_reasoning"):
                    self.assertEqual(row[field], "'" + payload)
                self.assertEqual(json.loads(row["original_record_json"]), asdict(record))
                self.assertEqual(score_labels(str(path))["unlabeled_rows"], 1)

    def test_3_writer_long_answer_can_be_scored(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "labels.csv"
            write_labels(build_report([rec(output="x" * 131073)]), str(path))
            result = subprocess.run([sys.executable, "-B", "-m", "blame_cli", "score", str(path)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout)["unlabeled_rows"], 1)

    def test_3_csv_errors_have_path_line_and_status_2(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "broken.csv"
            path.write_text('record_id,predicted_label,detector_labels,human_label\n"unterminated', encoding="utf-8")
            result = subprocess.run([sys.executable, "-B", "-m", "blame_cli", "score", str(path)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(str(path), result.stderr)
            self.assertIn("line 2", result.stderr)
            self.assertIn("CSV", result.stderr)
            self.assertNotIn("Traceback", result.stderr)

    def test_4_tool_only_choices_rejected_with_serialized_completion(self):
        for completion in (None, "", " ", "serialized text"):
            with self.subTest(completion=completion):
                log = json.loads((ROOT / "fixtures/inspect.json").read_text())
                output = {"choices": [{"message": {"role": "assistant", "content": "",
                                                   "tool_calls": [{"id": "1", "function": "calculate", "arguments": {}}]}}]}
                if completion is not None:
                    output["completion"] = completion
                log["samples"][0]["output"] = output
                with self.assertRaisesRegex(ValueError, "tool-only"):
                    inspect_records(log)

    def test_5_generic_extra_inspect_fields_are_ignored(self):
        for extra in ({"eval": None}, {"samples": []}, {"eval": {}, "samples": [], "version": 2}):
            with self.subTest(extra=extra), tempfile.TemporaryDirectory(dir=ROOT) as tmp:
                path = Path(tmp) / "generic.jsonl"
                path.write_text(json.dumps(asdict(rec()) | extra), encoding="utf-8")
                records, warnings = load_inputs([str(path)])
                self.assertEqual(records, [rec()])
                self.assertEqual(warnings, [])

    def test_5_jsonl_only_splits_on_newlines(self):
        text = "first\u2028second\u2029third\u0085fourth"
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "unicode.jsonl"
            path.write_text(json.dumps(asdict(rec(output=text)), ensure_ascii=False) + "\r\n" +
                            json.dumps(asdict(rec(task_id="other"))) + "\n", encoding="utf-8")
            records, _ = load_inputs([str(path)])
            self.assertEqual(len(records), 2)
            self.assertEqual(records[0].output, text)

    def test_6_judge_groups_are_scanned_once(self):
        # Count identity reads to detect rescanning without timing-sensitive assertions.
        original = Record.judge_key.fget
        for scores in ([0] * 40, [0, 0.5, 1, 0] * 10):
            with self.subTest(disagreement=len(set(scores)) > 1):
                reads = 0

                def counted(record):
                    nonlocal reads
                    reads += 1
                    return original(record)

                records = [rec(score=score, judge_run=i) for i, score in enumerate(scores)]
                with patch.object(Record, "judge_key", property(counted)):
                    verdicts = triage(records)
                self.assertLessEqual(reads, 4 * len(records))
                if len(set(scores)) > 1:
                    evidence = verdicts[0]["evidence"]
                    expected = sum(a != b for i, a in enumerate(scores) for b in scores[i + 1:])
                    self.assertEqual(evidence["different_score_pairs"], expected)
                    self.assertEqual(evidence["judge_pairs"], 780)
                else:
                    self.assertTrue(all(v["label"] == "genuine_failure" for v in verdicts))

    def test_7_complete_numeric_tokens(self):
        reasoner = HeuristicReasoner()
        for instruction, required in (("Use 12.5 kg.", "12"), ("Use 112 kg.", "12"),
                                      ("Use -12 kg.", "12"), ("Use 12%.", "12"),
                                      ("Use 12 kg.", "12.5"), ("Use 12.50 kg.", "12.5"),
                                      ("Use 12e3 kg.", "12")):
            with self.subTest(instruction=instruction, required=required):
                result = reasoner.missing_requirements(instruction, f"Must use {required} kg.")
                self.assertIsNotNone(result)
                self.assertIn(required, result["missing_terms"])
        self.assertIsNone(reasoner.missing_requirements("Use 12 kg.", "Must use 12 kg."))
        self.assertIsNone(reasoner.missing_requirements("Use 12.5 kg.", "Must use 12.5 kg."))

    def test_7_prohibitions_and_examples_abstain(self):
        for rubric in ("Must avoid mentioning NASA.", "Must omit NASA.", "Must exclude NASA.",
                       "Must include a greeting; examples include NASA.",
                       "Must include a greeting; for instance NASA."):
            with self.subTest(rubric=rubric):
                self.assertIsNone(HeuristicReasoner().missing_requirements("Write a greeting.", rubric))

    def test_8_mit_license_and_metadata(self):
        license_path = ROOT / "LICENSE"
        self.assertTrue(license_path.is_file(), "root LICENSE is missing")
        license_text = license_path.read_text(encoding="utf-8")
        self.assertIn("MIT License", license_text)
        self.assertIn("Copyright (c) 2026 Hari Naralasetty", license_text)
        self.assertIn("Permission is hereby granted, free of charge", license_text)
        import tomllib
        metadata = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        self.assertEqual(metadata["project"]["license"], "MIT")
        self.assertIn("MIT", (ROOT / "README.md").read_text(encoding="utf-8"))

    def test_9_oversized_integer_is_contextual_status_2(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "huge-score.jsonl"
            path.write_text(json.dumps(asdict(rec()) | {"score": 10 ** 400}) + "\n", encoding="utf-8")
            out = Path(tmp) / "report"
            result = subprocess.run([sys.executable, "-B", "-m", "blame_cli", "report", str(path), "--out", str(out)],
                                    cwd=ROOT, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertIn(f"{path}: line 1:", result.stderr)
            self.assertIn("score must be a finite number in [0, 1]", result.stderr)
            self.assertNotIn("Traceback", result.stderr)
            self.assertFalse(out.exists())


if __name__ == "__main__":
    unittest.main()
