from copy import deepcopy
from dataclasses import asdict
import json
from pathlib import Path
import tempfile
import unittest

from blame_cli.inputs import inspect_records, load_inputs
from blame_cli.model import Record
from test_detectors import rec


ROOT = Path(__file__).resolve().parents[1]


class GenericTests(unittest.TestCase):
    def test_validation(self):
        for change in ({"score": -1}, {"score": 1.1}, {"score": True}, {"score": float("nan")},
                       {"score": float("inf")}, {"judge_run": True}, {"judge_run": "1"},
                       {"instruction": ""}, {"output": None}, {"error": {}}, {"task_id": 1}):
            with self.subTest(change=change):
                with self.assertRaises(ValueError):
                    Record.from_dict(asdict(rec()) | change)

    def test_generic_optional_fields(self):
        data = asdict(rec())
        del data["judge_run"]
        del data["error"]
        self.assertIsNone(Record.from_dict(data).judge_run)
        self.assertEqual(Record.from_dict(data).score, 0)

    def test_multiple_files_deduplicate_and_reject_conflicting_judges(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "input.jsonl"
            path.write_text(json.dumps(asdict(rec())) + "\n", encoding="utf-8")
            records, warnings = load_inputs([str(path), str(path)])
            self.assertEqual(len(records), 1)
            self.assertIn("duplicate", warnings[0])
            with path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(rec(score=1))) + "\n")
            with self.assertRaisesRegex(ValueError, "conflicting scores"):
                load_inputs([str(path)])

    def test_source_line_in_validation_error(self):
        with tempfile.TemporaryDirectory(dir=ROOT) as tmp:
            path = Path(tmp) / "bad.jsonl"
            path.write_text(json.dumps(asdict(rec())) + '\n{"score": 7}\n', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "bad.jsonl: line 2"):
                load_inputs([str(path)])


class InspectTests(unittest.TestCase):
    def setUp(self):
        self.log = json.loads((ROOT / "fixtures/inspect.json").read_text())

    def test_documented_handwritten_fixture(self):
        records, warnings = inspect_records(self.log)
        self.assertEqual(warnings, [])
        self.assertEqual(len(records), 2)
        blue, explain = records
        self.assertEqual(blue.task_id, "color:sample")
        self.assertEqual(blue.model, "synthetic/alpha")
        self.assertEqual(blue.run_id, "inspect-generation-1/epoch-1")
        self.assertEqual(blue.output, "Green is my choice.")
        self.assertEqual(blue.score, 0)
        self.assertEqual(explain.score, 0.5)
        self.assertEqual(blue.judge_run, 1)
        self.assertEqual(blue.judge_reasoning, "The response says green rather than blue.")

    def test_message_input_text_blocks_completion_and_score_metadata(self):
        sample = self.log["samples"][0]
        sample["input"] = [
            {"role": "system", "content": "You are helpful."},
            {"role": "user", "content": [{"type": "text", "text": "Answer blue."}]},
        ]
        sample["output"]["completion"] = "blue"
        sample["epoch"] = 2
        sample["scores"]["blue"]["metadata"]["judge_run"] = 4
        records, _ = inspect_records(self.log)
        self.assertEqual(records[0].instruction, "You are helpful.\nAnswer blue.")
        self.assertEqual(records[0].output, "blue")
        self.assertEqual(records[0].judge_run, 4)
        self.assertTrue(records[0].run_id.endswith("epoch-2"))

    def test_dictionary_scores_and_no_rubric_fallback(self):
        sample = self.log["samples"][0]
        sample["scores"] = {"rubric": {
            "value": {"format": True, "length": False}, "explanation": "Too short.",
            "metadata": {"rubric_items": {"format": "Use a paragraph."}},
        }}
        records, warnings = inspect_records(self.log)
        self.assertEqual([(r.rubric_item_id, r.score) for r in records],
                         [("rubric/format", 1), ("rubric/length", 0)])
        self.assertEqual(records[0].rubric_item_text, "Use a paragraph.")
        self.assertIn("rubric text unavailable", records[1].rubric_item_text)
        self.assertEqual(len(warnings), 1)

    def test_unscored_sample_warning_and_sample_error(self):
        self.log["status"] = "error"
        self.log["error"] = {"message": "Process stopped", "traceback": "synthetic"}
        sample = self.log["samples"][0]
        sample["error"] = {"message": "Artifact missing", "traceback": "synthetic"}
        self.log["samples"].append({"id": "unscored", "scores": None})
        records, warnings = inspect_records(self.log)
        self.assertEqual(records[0].error, "Artifact missing")
        self.assertEqual(len(warnings), 2)
        self.assertIn("no scores", warnings[1])

    def test_missing_judge_run_is_not_inferred_from_epoch(self):
        del self.log["samples"][0]["metadata"]["judge_run"]
        self.log["samples"][0]["epoch"] = 7
        records, _ = inspect_records(self.log)
        self.assertIsNone(records[0].judge_run)

    def test_reject_unsupported_instead_of_faking_scores_or_text(self):
        variants = []
        for value in ("P", "unknown", 2, float("nan"), [0, 1], None):
            log = deepcopy(self.log)
            log["samples"][0]["scores"]["blue"]["value"] = value
            variants.append(log)
        for content in ("attachment://abc", [{"type": "image", "image": "synthetic"}]):
            log = deepcopy(self.log)
            log["samples"][0]["input"] = content if isinstance(content, str) else [{"role": "user", "content": content}]
            variants.append(log)
        log = deepcopy(self.log)
        log["version"] = 1
        variants.append(log)
        log = deepcopy(self.log)
        log["samples"] = None
        variants.append(log)
        for log in variants:
            with self.subTest(log=log):
                with self.assertRaises(ValueError):
                    inspect_records(log)


if __name__ == "__main__":
    unittest.main()
