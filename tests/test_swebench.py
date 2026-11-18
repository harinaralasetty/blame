"""The SWE-bench reader. Fixtures are hand-written; the reader is unverified against real harness output."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from blame_cli.formats import detect_format, load_path, swebench
from blame_cli.inputs import load_inputs
from blame_cli.reports import build_report, markdown, static_html

from test_golden import check_golden


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/swebench-eval"
PATCH = "--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n"
PATCH_ID = "patch:" + hashlib.sha256(PATCH.encode()).hexdigest()[:12]


def write_instance(run: Path, task: str = "proj__lib-1", model: str = "org__model", report=None, patch=PATCH,
                   log: str | None = None, **entry) -> Path:
    directory = run / model / task
    directory.mkdir(parents=True, exist_ok=True)
    if report is None:
        report = {task: {"patch_is_None": False, "patch_exists": True, "patch_successfully_applied": True,
                         "resolved": False, "infra_failure": False} | entry}
    if report is not False:
        (directory / "report.json").write_text(report if isinstance(report, str) else json.dumps(report), encoding="utf-8")
    if patch is not None:
        (directory / "patch.diff").write_text(patch, encoding="utf-8")
    if log is not None:
        (directory / "run_instance.log").write_text(log, encoding="utf-8")
    return directory


def write_summary(run: Path, **ids) -> None:
    run.mkdir(parents=True, exist_ok=True)
    (run / "results.json").write_text(json.dumps(ids), encoding="utf-8")


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.logs = Path(tmp.name) / "evaluation"
        self.run = self.logs / "run-1"
        self.run.mkdir(parents=True)

    def load(self, summary: bool = True):
        if summary and not (self.run / "results.json").exists():
            write_summary(self.run)
        return swebench.load(self.run)

    def one(self, task: str = "proj__lib-1", **entry):
        write_instance(self.run, task, **entry)
        records, warnings = self.load()
        self.assertEqual(warnings, [])
        return next(record for record in records if record.task_id == task)


class DetectionTests(Case):
    def test_a_run_directory_and_a_directory_of_runs_are_swebench(self):
        write_instance(self.run)
        write_summary(self.run)
        for path in (self.run, self.logs):
            self.assertEqual(detect_format(path), "swebench")
            records, warnings = load_path(path)
            self.assertEqual(([r.job_id for r in records], [r.task_id for r in records], warnings),
                             (["run-1"], ["proj__lib-1"], []))

    def test_other_report_files_are_not_swebench(self):
        for number, report in enumerate(({"other": {"resolved": True}}, {"proj__lib-1": {"passed": True}},
                                         {"proj__lib-1": {"resolved": True}, "extra": {}}, "[]", "{")):
            run = self.logs.parent / f"other-{number}" / "run"
            write_instance(run, report=report)
            self.assertFalse(swebench.detect(run), report)
            with self.assertRaisesRegex(ValueError, "no reader recognises this directory.*Harbor.*; SWE-bench .a report.json"):
                detect_format(run)
        write_instance(self.run / "too" / "deep")
        self.assertFalse(swebench.detect(self.logs.parent))
        self.assertFalse(swebench.detect(self.run / "missing"))

    def test_forced_format_on_a_directory_without_results_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "no readable SWE-bench result found"):
            load_path(self.run, "swebench")


class MappingTests(Case):
    def test_unresolved_instance(self):
        status = {"FAIL_TO_PASS": {"success": ["t_a"], "failure": ["t_b", "t_c"]},
                  "PASS_TO_PASS": {"success": ["t_d"], "failure": []}}
        record = self.one(tests_status=status)
        self.assertEqual((record.task_id, record.model, record.agent, record.system, record.job_id, record.run_id),
                         ("proj__lib-1", "org__model", None, "org__model", "run-1", PATCH_ID))
        self.assertEqual((record.rubric_item_id, record.score, record.role, record.error, record.error_kind, record.judge_run),
                         ("resolved", 0.0, "candidate", None, None, None))
        self.assertEqual((record.instruction, record.rubric_item_text, record.task_version, record.output),
                         (None, None, None, PATCH))
        self.assertEqual(record.judge_reasoning, "patch_exists: true. patch_successfully_applied: true.\n"
                         "FAIL_TO_PASS: 1 passed, 2 failed (t_b, t_c).\nPASS_TO_PASS: 1 passed, 0 failed.")

    def test_resolved_and_gold(self):
        write_instance(self.run, resolved=True)
        write_instance(self.run, model="gold", resolved=True)
        records, _ = self.load()
        self.assertEqual([(r.model, r.role, r.score) for r in records],
                         [("gold", "reference", 1.0), ("org__model", "candidate", 1.0)])

    def test_resolved_must_be_a_boolean(self):
        write_instance(self.run, resolved="yes")
        with self.assertRaisesRegex(ValueError, r"^org__model/proj__lib-1/report.json: resolved must be true or false$"):
            self.load()

    def test_log_pattern_flags(self):
        flagged = self.one(patch_successfully_applied=False, infra_failure=True, infra_failure_reason="out_of_memory")
        self.assertEqual((flagged.score, flagged.error, flagged.error_kind),
                         (0.0, "SWE-bench log pattern: out_of_memory", "infra"))
        self.assertEqual(flagged.judge_reasoning, "patch_exists: true. patch_successfully_applied: false.\n"
                         "The harness found no parseable test output.")
        ambiguous = self.one(task="proj__lib-2", patch_successfully_applied=False, infra_failure_reason="missing_module")
        self.assertEqual((ambiguous.score, ambiguous.error, ambiguous.error_kind),
                         (0.0, "SWE-bench log pattern: missing_module", "unknown"))
        bare = self.one(task="proj__lib-0", infra_failure=True)
        self.assertEqual((bare.error, bare.error_kind), ("SWE-bench log pattern: no reason recorded", "infra"))

    def test_failed_test_names_are_capped_at_twenty_a_group(self):
        names = [f"t{number}" for number in range(25)]
        record = self.one(tests_status={"FAIL_TO_PASS": {"success": [], "failure": names}})
        self.assertEqual(record.judge_reasoning.splitlines()[1],
                         "FAIL_TO_PASS: 0 passed, 25 failed (" + ", ".join(names[:20]) + ", and 5 more).")

    def test_missing_patch_uses_the_run_id_and_warns(self):
        write_instance(self.run, patch=None)
        records, warnings = self.load()
        self.assertEqual((records[0].run_id, records[0].output), ("run-1", None))
        self.assertEqual(warnings, ["org__model/proj__lib-1: no patch.diff; the run id run-1 stands in for the patch."])

    def test_instance_without_a_report_is_ungraded(self):
        write_instance(self.run, report=False, log="\n".join(f"line {n}" for n in range(9)) + "\nsaved /home/somebody/logs/x\n")
        write_instance(self.run, task="proj__lib-2", report=False)
        records, warnings = self.load()
        self.assertEqual(warnings, [])
        self.assertEqual([(r.score, r.error_kind, r.error, r.run_id) for r in records],
                         [(None, "unknown", "line 5\nline 6\nline 7\nline 8\nsaved ~/logs/x", PATCH_ID),
                          (None, "unknown", "no report.json", PATCH_ID)])

    def test_unreadable_report_is_skipped_with_one_warning(self):
        write_instance(self.run)
        write_instance(self.run, task="proj__lib-2", report="{")
        write_summary(self.run, error_ids=["proj__lib-2"])
        records, warnings = self.load()
        self.assertEqual([r.task_id for r in records], ["proj__lib-1"])
        self.assertEqual(warnings, ["org__model/proj__lib-2/report.json: unreadable result file skipped "
                                    "(not a JSON report for this instance)."])

    def test_patch_text_is_redacted_but_the_run_id_hashes_the_file(self):
        patch = PATCH + "+# see /Users/somebody/notes.txt\n"
        record = self.one(patch=patch)
        self.assertTrue(record.output.endswith("+# see ~/notes.txt\n"))
        self.assertEqual(record.run_id, "patch:" + hashlib.sha256(patch.encode()).hexdigest()[:12])


class SummaryTests(Case):
    def test_missing_summary_warns(self):
        write_instance(self.run)
        _, warnings = self.load(summary=False)
        self.assertEqual(warnings, ["no results.json; empty patches and harness errors without an instance directory are not visible."])
        (self.run / "results.json").write_text("[]", encoding="utf-8")
        _, warnings = self.load()
        self.assertEqual(warnings, ["results.json: unreadable result file skipped (not a UTF-8 JSON object)."])

    def test_empty_patches_and_errors_with_one_model_directory(self):
        write_instance(self.run)
        write_summary(self.run, empty_patch_ids=["proj__lib-2"], error_ids=["proj__lib-3", "proj__lib-1"],
                      incomplete_ids=["proj__lib-4", "proj__lib-5"])
        records, warnings = self.load()
        self.assertEqual([(r.task_id, r.run_id, r.output, r.score, r.error, r.error_kind) for r in records],
                         [("proj__lib-1", PATCH_ID, PATCH, 0.0, None, None),
                          ("proj__lib-2", "patch:empty", "", 0.0, "empty patch", "agent"),
                          ("proj__lib-3", "run-1", None, None, "no report.json", "unknown")])
        self.assertEqual(warnings, ["results.json: 2 instances have no prediction (incomplete_ids) and are not in the report."])

    def test_summary_ids_need_a_model_to_belong_to(self):
        write_instance(self.run)
        write_instance(self.run, model="gold", resolved=True)
        (self.run / "gold" / "proj__lib-2").mkdir()
        write_summary(self.run, empty_patch_ids=["proj__lib-2", "proj__lib-3"], error_ids=["proj__lib-4", "../x", 7])
        records, warnings = self.load()
        self.assertEqual([(r.model, r.task_id, r.error) for r in records if r.error],
                         [("gold", "proj__lib-2", "no report.json")])
        self.assertEqual(warnings[-1], "results.json: 2 empty-patch or error ids could not be tied to a model directory and were skipped.")

    def test_only_a_summary_is_enough_to_read_a_run(self):
        (self.run / "org__model").mkdir()
        write_summary(self.run, empty_patch_ids=["proj__lib-2"])
        records, _ = load_path(self.run, "swebench")
        self.assertEqual([(r.model, r.score) for r in records], [("org__model", 0.0)])


class MergeTests(Case):
    def test_the_same_patch_graded_in_two_runs_becomes_two_judge_runs(self):
        write_instance(self.run)
        write_instance(self.logs / "run-0", resolved=True)
        write_instance(self.logs / "run-0", task="proj__lib-2")
        write_instance(self.logs / "run-2", patch=PATCH + "+more\n")
        for paths in ([self.logs], [self.run, self.logs / "run-0", self.logs / "run-2"]):
            records, _ = load_inputs([str(path) for path in paths])
            found = {(r.job_id, r.task_id, r.judge_run) for r in records}
            self.assertEqual(found, {("run-0", "proj__lib-1", 1), ("run-1", "proj__lib-1", 2),
                                     ("run-0", "proj__lib-2", None), ("run-2", "proj__lib-1", None)})
            report = build_report(records)
            self.assertEqual([item["label"] for item in report["items"] if item["record"]["job_id"] == "run-1"],
                             ["judge_unstable"])

    def test_both_invocations_give_the_same_items(self):
        together, _ = load_inputs([str(FIXTURE)])
        apart, _ = load_inputs([str(FIXTURE / "run-a"), str(FIXTURE / "run-b")])
        self.assertEqual(build_report(together)["items"], build_report(apart)["items"])
        self.assertEqual(together, apart)

    def test_formats_can_be_mixed(self):
        write_instance(self.run)
        write_summary(self.run)
        records, _ = load_inputs([str(ROOT / "fixtures/harbor-job"), str(self.run), str(ROOT / "fixtures/synthetic.jsonl")])
        self.assertEqual([r.job_id == "run-1" for r in records].index(True), 15)
        self.assertEqual(len(records), 15 + 1 + 36)


class FixtureTests(unittest.TestCase):
    def test_fixture_report(self):
        records, warnings = load_inputs([str(FIXTURE)])
        report = build_report(records, [w.replace(str(FIXTURE), "fixtures/swebench-eval") for w in warnings])
        check_golden(self, "swebench", report)
        self.assertEqual((report["scored_items"], report["lost_items"], report["ungraded_items"], report["reference_items"]),
                         (7, 6, 2, 2))
        self.assertEqual(len(report["warnings"]), 4)
        labels = [item["label"] for item in report["items"]]
        self.assertEqual({label: labels.count(label) for label in set(labels)},
                         {"judge_unstable": 1, "reference_fails": 2, "infra": 1, "unclassified_error": 3, "genuine_failure": 1})
        text = json.dumps(report) + markdown(report) + static_html(report)
        for word in ("/home/", "/Users/"):
            self.assertNotIn(word, text)

    def test_cli_reads_both_layouts(self):
        with tempfile.TemporaryDirectory() as tmp:
            for inputs in (["fixtures/swebench-eval"], ["fixtures/swebench-eval/run-a", "fixtures/swebench-eval/run-b"],
                           ["fixtures/swebench-eval", "--format", "swebench"]):
                result = subprocess.run([sys.executable, "-m", "blame_cli", "report", *inputs, "--out", tmp],
                                        cwd=ROOT, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("6 lost items, 2 ungraded", result.stdout)
                self.assertIn("judge_unstable", (Path(tmp) / "report.md").read_text(encoding="utf-8"))
            help_text = subprocess.run([sys.executable, "-m", "blame_cli", "report", "--help"], cwd=ROOT, text=True,
                                       capture_output=True).stdout
            self.assertIn("harbor and swebench are unverified against real harness output", " ".join(help_text.split()))


if __name__ == "__main__":
    unittest.main()
