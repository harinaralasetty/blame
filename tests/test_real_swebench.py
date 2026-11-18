"""The SWE-bench reader against real harness output (fixtures/real-swebench, swebench 5.0.2)."""

import json
from pathlib import Path
import tempfile
import unittest

from blame_cli.formats import swebench
from blame_cli.inputs import load_inputs
from blame_cli.reports import build_report


ROOT = Path(__file__).resolve().parent.parent
RUN = ROOT / "fixtures/real-swebench/run"
ERRORS = ROOT / "fixtures/real-swebench/all-errors"


def _rows(records):
    return sorted((r.job_id, r.task_id, r.model, r.role, r.score, r.error_kind) for r in records)


class RealSwebenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.warnings = load_inputs([str(RUN)])
        cls.by_key = {(r.job_id, r.task_id): r for r in cls.records}

    def test_working_directory_gives_both_runs_and_the_empty_patch(self):
        self.assertEqual(self.warnings, [])
        self.assertEqual(_rows(self.records), [
            ("blame-m7-demo", "django__django-11099", "demo-model", "candidate", 0.0, "agent"),
            ("blame-m7-demo", "sympy__sympy-20590", "demo-model", "candidate", 0.0, None),
            ("blame-m7-gold", "sympy__sympy-20590", "gold", "reference", 1.0, None),
        ])

    def test_every_directory_level_reads_the_same(self):
        for inner in ("logs", "logs/run_evaluation"):
            records, warnings = load_inputs([str(RUN / inner)])
            self.assertEqual((_rows(records), warnings), (_rows(self.records), []), inner)
        records, warnings = load_inputs([str(RUN / "logs/run_evaluation/blame-m7-demo")])
        self.assertEqual((_rows(records), warnings), (_rows(self.records)[:2], []))

    def test_report_fields(self):
        gold = self.by_key["blame-m7-gold", "sympy__sympy-20590"]
        self.assertTrue(gold.output.startswith("diff --git a/sympy/core/_print_helpers.py"))
        self.assertIn("FAIL_TO_PASS: 1 passed, 0 failed.", gold.judge_reasoning)
        wrong = self.by_key["blame-m7-demo", "sympy__sympy-20590"]
        self.assertTrue(wrong.judge_reasoning.startswith("patch_exists: true. patch_successfully_applied: true."))
        self.assertIn("FAIL_TO_PASS: 0 passed, 1 failed (test_immutable).", wrong.judge_reasoning)
        self.assertIn("PASS_TO_PASS: 21 passed, 0 failed.", wrong.judge_reasoning)
        empty = self.by_key["blame-m7-demo", "django__django-11099"]
        self.assertEqual((empty.error, empty.output), ("empty patch", ""))

    def test_report_counts(self):
        report = build_report(self.records, [])
        self.assertEqual((report["scored_items"], report["lost_items"], report["reference_items"]), (2, 2, 1))

    def test_a_run_where_every_instance_errored_is_read(self):
        self.assertTrue(swebench.detect(ERRORS))
        records, warnings = load_inputs([str(ERRORS)])
        (record,) = records
        self.assertEqual((record.task_id, record.model, record.role, record.score, record.error_kind),
                         ("sympy__sympy-20590", "gold", "reference", None, "unknown"))
        self.assertIn("EvaluationError: Error in evaluation for sympy__sympy-20590", record.error)
        self.assertNotIn("/home/user", record.error)
        self.assertEqual(len(warnings), 1)
        self.assertIn("no patch.diff", warnings[0])


class HarnessSummaryTests(unittest.TestCase):
    """The per-model summary beside logs/, in a layout built here."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.cwd = Path(tmp.name)
        self.run = self.cwd / "logs/run_evaluation/r1"

    def _instance(self, model, task, resolved):
        where = self.run / model / task
        where.mkdir(parents=True)
        (where / "report.json").write_text(json.dumps({task: {"resolved": resolved}}), encoding="utf-8")
        (where / "patch.diff").write_text(f"diff {model} {task}\n", encoding="utf-8")

    def _summary(self, model, **ids):
        (self.cwd / f"{model}.r1.json").write_text(json.dumps(ids), encoding="utf-8")

    def test_each_summary_covers_its_own_model(self):
        self._instance("m-a", "t-1", True)
        self._instance("m-b", "t-1", False)
        self._summary("m-a", empty_patch_ids=["t-2"], error_ids=["t-3"])
        self._summary("m-b", empty_patch_ids=[], error_ids=[], incomplete_ids=["t-9"])
        records, warnings = swebench.load(self.cwd)
        self.assertEqual(sorted((r.model, r.task_id, r.score, r.error) for r in records), [
            ("m-a", "t-1", 1.0, None), ("m-a", "t-2", 0.0, "empty patch"), ("m-a", "t-3", None, "no report.json"),
            ("m-b", "t-1", 0.0, None)])
        self.assertEqual(warnings, ["r1/m-b.r1.json: 1 instances have no prediction (incomplete_ids) "
                                    "and are not in the report."])

    def test_a_model_with_only_empty_patches_has_no_directory(self):
        self._instance("m-a", "t-1", True)
        self._summary("m-b", empty_patch_ids=["t-1", "t-2"])
        records, _ = swebench.load(self.run)
        self.assertEqual(sorted((r.model, r.task_id, r.error) for r in records),
                         [("m-a", "t-1", None), ("m-b", "t-1", "empty patch"), ("m-b", "t-2", "empty patch")])

    def test_missing_summary_names_the_harness_file(self):
        self._instance("m-a", "t-1", True)
        _, warnings = swebench.load(self.run)
        self.assertEqual(warnings, ["results.json: not present, and no <model>.r1.json beside logs/, so empty patches "
                                    "and harness errors without an instance directory are not visible."])

    def test_another_runs_summary_is_not_read(self):
        self._instance("m-a", "t-1", True)
        (self.cwd / "m-a.r2.json").write_text(json.dumps({"empty_patch_ids": ["t-5"]}), encoding="utf-8")
        records, _ = swebench.load(self.run)
        self.assertEqual([r.task_id for r in records], ["t-1"])


if __name__ == "__main__":
    unittest.main()
