"""Regression tests for the findings in docs/CHECK-cross-format.md, by finding number."""

from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from blame_cli.detectors import triage
from blame_cli.formats import detect_format, harbor, redact, swebench
from blame_cli.formats._text import ERROR_CHARS, OUTPUT_CHARS
from blame_cli.inputs import load_inputs
from blame_cli.model import Record, validate
from blame_cli.reports import build_report

from test_harbor import exception, write_trial
from test_swebench import PATCH, write_instance, write_summary


ROOT = Path(__file__).resolve().parents[1]


def generic(**changes) -> Record:
    fields = {"task_id": "t", "model": "m", "run_id": "r", "instruction": "i", "rubric_item_id": "c",
              "rubric_item_text": "x", "output": "o", "score": 0.0, "judge_reasoning": "", "error": None} | changes
    return validate(Record(**fields))


def cli(*args: str):
    return subprocess.run([sys.executable, "-m", "blame_cli", *args], cwd=ROOT, text=True, capture_output=True)


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)

    def report(self, *paths, fmt: str = "auto"):
        records, warnings = load_inputs([str(path) for path in paths], fmt)
        return records, warnings, build_report(records, warnings)


class Finding1StraySummary(Case):
    def test_a_stray_results_json_does_not_hide_the_run_below_it(self):
        logs = self.tmp / "d"
        write_instance(logs / "run1", task="i-1", model="m")
        write_summary(logs / "run1")
        write_summary(logs, error_ids=[])
        for fmt in ("auto", "swebench"):
            records, warnings, _ = self.report(logs, fmt=fmt)
            self.assertEqual([(r.task_id, r.model, r.job_id, r.score) for r in records], [("i-1", "m", "run1", 0.0)])
            self.assertEqual(warnings, [f"{logs}: results.json: not read; it sits beside the run directories, "
                                        "not inside one."])

    def test_a_summary_alone_still_marks_a_run(self):
        run = self.tmp / "run1"
        (run / "m").mkdir(parents=True)
        write_summary(run, empty_patch_ids=["i-1"])
        for path in (run, self.tmp):
            records, _, _ = self.report(path, fmt="swebench")
            self.assertEqual([(r.task_id, r.job_id) for r in records], [("i-1", "run1")])


class Finding2JobIdentity(Case):
    def gradings(self, first: str, second: str):
        write_instance(self.tmp / first, task="i-1", model="m", resolved=False)
        write_instance(self.tmp / second, task="i-1", model="m", resolved=True)
        for run in (first, second):
            write_summary(self.tmp / run)

    def test_same_named_runs_under_two_roots_are_paired(self):
        self.gradings("p1/run", "p2/run")
        for paths in ((self.tmp / "p1", self.tmp / "p2"), (self.tmp / "p1/run", self.tmp / "p2/run")):
            records, warnings, report = self.report(*paths)
            self.assertEqual([(r.job_id, r.judge_run) for r in records], [("p1/run", 1), ("p2/run", 2)])
            self.assertEqual(warnings, [])
            self.assertEqual((report["scored_items"], report["lost_items"], report["items"][0]["label"]),
                             (2, 1, "judge_unstable"))

    def test_the_verdict_does_not_depend_on_run_directory_names(self):
        self.gradings("q1/run1", "q2/run2")
        _, _, named = self.report(self.tmp / "q1", self.tmp / "q2")
        self.gradings("p1/run", "p2/run")
        _, _, same = self.report(self.tmp / "p1", self.tmp / "p2")
        for key in ("scored_items", "lost_items", "by_class"):
            self.assertEqual(named[key], same[key])
        self.assertEqual([i["confidence"] for i in named["items"]], [i["confidence"] for i in same["items"]])

    def test_a_run_supplied_twice_is_read_once(self):
        self.gradings("p1/run", "p2/run")
        records, warnings, _ = self.report(self.tmp / "p1", self.tmp / "p1/run")
        self.assertEqual([(r.job_id, r.judge_run) for r in records], [("run", None)])
        self.assertEqual(warnings, ["SWE-bench run run was supplied more than once; it is read once."])

    def test_harbor_trial_under_same_named_jobs_is_kept_once_with_a_warning(self):
        write_trial(self.tmp / "p1/job", "t1__a", verifier_result={"rewards": {"reward": 0.0}})
        write_trial(self.tmp / "p2/job", "t1__a", verifier_result={"rewards": {"reward": 1.0}})
        records, warnings, report = self.report(self.tmp / "p1/job", self.tmp / "p2/job")
        self.assertEqual([r.score for r in records], [0.0])
        self.assertEqual(warnings, ["Harbor trial t1__a@abcdef12 of task task was supplied more than once; "
                                    "the first copy is kept; the copies differ."])
        self.assertEqual(report["scored_items"], 1)


class Finding3Ungraded(Case):
    def test_generic_ungraded_agent_error_is_not_a_genuine_failure(self):
        verdict = triage([generic(score=None, error="agent crashed", error_kind="agent")])[0]
        self.assertEqual((verdict["label"], verdict["confidence"]), ("unclassified_error", 0.40))
        self.assertIn("no score", verdict["evidence"]["observed"])

    def test_graded_agent_error_keeps_the_default_label(self):
        self.assertEqual(triage([generic(error="agent crashed", error_kind="agent")])[0]["label"], "genuine_failure")

    def test_no_ungraded_record_ever_gets_the_default_label(self):
        for kind in (None, "infra", "setup", "grader", "agent", "unknown"):
            verdict = triage([generic(score=None, error="x", error_kind=kind)])[0]
            self.assertNotEqual(verdict["label"], "genuine_failure", kind)

    def test_harbor_agent_timeout_without_verifier_result(self):
        write_trial(self.tmp / "job", verifier_result=None, exception_info=exception("AgentTimeoutError"))
        records, _, report = self.report(self.tmp / "job")
        self.assertEqual((records[0].score, records[0].error_kind), (None, "agent"))
        self.assertEqual((report["ungraded_items"], report["items"][0]["label"]), (1, "unclassified_error"))

    def test_harbor_override_overruled_by_the_recorded_policy_reads_one_way(self):
        info = exception("ApiError", policy={"has_valid_reward": False}, policy_override={"has_valid_reward": True})
        write_trial(self.tmp / "job", exception_info=info)
        records, _, report = self.report(self.tmp / "job")
        self.assertIn("overruled by the recorded policy", records[0].error)
        self.assertNotIn("policy_override has_valid_reward=true);", records[0].error)
        self.assertNotEqual(report["items"][0]["label"], "genuine_failure")


class Finding4ReferenceSentence(Case):
    def reference(self, *records) -> str:
        return build_report(list(records))["by_task"][0]["reference"]

    def test_excluded_reference_attempts_are_left_out_and_counted(self):
        left = "; 1 left out (harness error, not graded or another task version)"
        ref = {"agent": "oracle", "role": "reference"}
        self.assertEqual(self.reference(generic(), generic(**ref, error="boom")), "no usable reference attempt" + left)
        self.assertEqual(self.reference(generic(task_version="v2"), generic(**ref, task_version="v1")),
                         "no usable reference attempt" + left)
        self.assertEqual(self.reference(generic(), generic(**ref, run_id="a", score=1.0), generic(**ref, run_id="b"),
                                        generic(**ref, run_id="c", error="x", error_kind="infra")),
                         "passed 1 of 2 attempts" + left)

    def test_attempts_are_counted_not_records(self):
        ref = {"agent": "oracle", "role": "reference"}
        records = [generic(rubric_item_id=item) for item in "abc"] + [generic(**ref, rubric_item_id=item) for item in "abc"]
        self.assertEqual(self.reference(*records), "passed 0 of 1 attempts")

    def test_harbor_reference_with_an_infra_exception(self):
        job = self.tmp / "job"
        write_trial(job)
        write_trial(job, "task__o", id="99999999-0000", agent_info={"name": "oracle", "version": "1"},
                    exception_info=exception("ApiError", reward_valid=True))
        _, _, report = self.report(job)
        self.assertEqual(report["by_task"][0]["reference"],
                         "no usable reference attempt; 1 left out (harness error, not graded or another task version)")
        self.assertEqual(report["items"][0]["label"], "genuine_failure")


class Finding5Redact(Case):
    def test_repository_paths_and_urls_are_unchanged(self):
        for text in ("diff --git a/src/home/views.py b/src/home/views.py", "https://example.com/home/index.html",
                     "--- a/home/x.py", "docs/Users/guide.md", "~/home/x"):
            self.assertEqual(redact(text), text)

    def test_absolute_home_paths_are_shortened(self):
        for text, want in (("/home/example/x.py", "~/x.py"), ("see /Users/somebody/notes.txt", "see ~/notes.txt"),
                           ('File "/home/example/x.py"', 'File "~/x.py"'), ("file:///home/example/jobs", "file://~/jobs"),
                           ("C:\\Users\\somebody\\x", "~\\x"), ("cwd=/home/example", "cwd=~")):
            self.assertEqual(redact(text), want)


class Finding6EmptyPatch(Case):
    def test_whitespace_patch_and_listed_empty_patch_get_one_treatment(self):
        run = self.tmp / "run1"
        write_instance(run, task="i-1", model="m", patch="  \n", report={"i-1": {"resolved": False}})
        write_instance(run, task="i-2", model="m", patch="", report=False)
        write_summary(run, empty_patch_ids=["i-3"], error_ids=["i-2"])
        records, _, report = self.report(run)
        self.assertEqual([(r.task_id, r.run_id, r.output, r.score, r.error, r.error_kind) for r in records],
                         [(task, "patch:empty", "", 0.0, "empty patch", "agent") for task in ("i-1", "i-2", "i-3")])
        self.assertEqual({item["label"] for item in report["items"]}, {"genuine_failure"})
        self.assertEqual(report["by_class"][0]["lost_items"], 0)   # infra


class Finding7ValueTypes(Case):
    def test_wrong_tests_status_types_are_ignored_with_a_warning_naming_the_file(self):
        run = self.tmp / "run1"
        write_instance(run, tests_status={"FAIL_TO_PASS": {"success": "abc", "failure": 7},
                                          "PASS_TO_PASS": {"success": ["t_a"], "failure": []}})
        write_summary(run)
        result = cli("report", str(run), "--out", str(self.tmp / "out"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertNotIn("object is not iterable", result.stderr)
        self.assertIn("org__model/proj__lib-1/report.json: tests_status FAIL_TO_PASS is not lists of test names "
                      "and was ignored.", result.stderr)
        records, _ = swebench.load(run)
        self.assertEqual(records[0].judge_reasoning, "patch_exists: true. patch_successfully_applied: true.\n"
                         "PASS_TO_PASS: 1 passed, 0 failed.")

    def test_other_wrong_types_never_give_a_raw_python_message(self):
        for number, entry in enumerate(({"tests_status": []}, {"tests_status": {"FAIL_TO_PASS": [1]}},
                                        {"infra_failure_reason": 7}, {"patch_exists": "x"})):
            run = self.tmp / f"r{number}" / "run1"
            write_instance(run, **entry)
            write_summary(run, error_ids="x", empty_patch_ids=[1, None], incomplete_ids={})
            records, _ = load_inputs([str(run)])
            self.assertEqual(len(records), 1)

    def test_summary_only_run_keeps_its_explanation(self):
        run = self.tmp / "run1"
        write_summary(run, error_ids=["i-1"])
        result = cli("report", "--format", "swebench", str(run), "--out", str(self.tmp / "out"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("no readable SWE-bench result found: results.json: 1 empty-patch or error ids could not be "
                      "tied to a model directory and were skipped.", result.stderr)

    def test_a_reader_bug_is_not_reported_as_an_input_error(self):
        run = self.tmp / "run1"
        write_instance(run)
        original = swebench._reasoning
        swebench._reasoning = lambda entry: entry["missing"]
        self.addCleanup(setattr, swebench, "_reasoning", original)
        with self.assertRaises(KeyError):
            load_inputs([str(run)])


class Finding10BadHarborTrial(Case):
    def test_a_bad_trial_is_skipped_with_a_warning_naming_the_file(self):
        job = self.tmp / "job"
        write_trial(job)
        write_trial(job, "task__a", id="1", agent_info=None)
        write_trial(job, "task__b", id="2", task_name=7)
        write_trial(job, "task__c", id="3", exception_info={"exception_message": "no type"})
        write_trial(job, "task__d", id="4", exception_info="boom")
        records, warnings = harbor.load(job)
        self.assertEqual([r.run_id for r in records], ["task__t1@abcdef12"])
        self.assertEqual(len(warnings), 4)
        for name, warning in zip("abcd", warnings):
            self.assertRegex(warning, rf"^task__{name}/result.json: .*trial skipped")
        self.assertIn("exception_info must be an object or null", warnings[3])

    def test_a_job_with_only_bad_trials_is_an_error_that_names_them(self):
        job = self.tmp / "job"
        write_trial(job, task_name="")
        with self.assertRaisesRegex(ValueError, "no readable Harbor trial result found: task__t1/result.json: "
                                                r"trial skipped \(task_name must be a non-empty string\)\."):
            harbor.load(job)


class Finding11CorruptReport(Case):
    def test_a_corrupt_report_listed_as_an_error_is_an_ungraded_record(self):
        run = self.tmp / "run1"
        write_instance(run)
        write_instance(run, task="proj__lib-2", report="{", log="Traceback\nBuildImageError: boom\n")
        write_instance(run, task="proj__lib-3", report="{")
        write_instance(run, task="proj__lib-4", resolved="yes")
        write_summary(run, error_ids=["proj__lib-2", "proj__lib-4"])
        records, warnings = swebench.load(run)
        self.assertEqual([(r.task_id, r.score, r.error, r.error_kind) for r in records],
                         [("proj__lib-1", 0.0, None, None),
                          ("proj__lib-2", None, "Traceback\nBuildImageError: boom", "unknown"),
                          ("proj__lib-4", None, "report.json could not be read", "unknown")])
        skipped = ("/report.json: unreadable result file skipped (not a JSON report for this instance with a true "
                   "or false resolved value).")
        self.assertEqual(warnings, [f"org__model/proj__lib-{n}{skipped}" for n in (2, 3, 4)])


class Finding12Caps(Case):
    def test_swebench_patch_and_error_text_are_capped(self):
        run = self.tmp / "run1"
        write_instance(run, patch=PATCH + "+x\n" * 1_000_000)
        write_instance(run, task="proj__lib-2", infra_failure=True, infra_failure_reason="r" * 3_000_000)
        write_instance(run, task="proj__lib-3", report=False, log="e" * 3_000_000)
        records, _ = swebench.load(run)
        note = " more characters not copied]"
        self.assertLess(len(records[0].output), OUTPUT_CHARS + 60)
        self.assertTrue(records[0].output.endswith(note))
        for record in records[1:]:
            self.assertLess(len(record.error), ERROR_CHARS + 100)
            self.assertTrue(record.error.endswith(note))

    def test_harbor_exception_message_is_capped(self):
        write_trial(self.tmp / "job", exception_info=exception("ApiError", "m" * 3_000_000))
        records, _ = harbor.load(self.tmp / "job")
        self.assertLess(len(records[0].error), ERROR_CHARS + 200)
        self.assertIn(" more characters not copied]", records[0].error)


class Finding15Symlink(Case):
    def test_a_symlinked_run_is_not_a_second_grading(self):
        logs = self.tmp / "logs"
        write_instance(logs / "run1")
        write_summary(logs / "run1")
        (logs / "run2").symlink_to(logs / "run1", target_is_directory=True)
        records, warnings, report = self.report(logs)
        self.assertEqual([(r.job_id, r.judge_run) for r in records], [("run1", None)])
        self.assertEqual(report["lost_items"], 1)
        self.assertEqual(warnings, ["SWE-bench run run1 was supplied more than once; it is read once."])


class Finding17Wording(Case):
    def test_missing_summary_warning_does_not_read_as_a_path(self):
        logs = self.tmp / "logs"
        write_instance(logs / "run1")
        write_instance(logs / "run2", task="proj__lib-2")
        write_summary(logs / "run2")
        _, warnings = swebench.load(logs)
        self.assertEqual(warnings, ["run1/results.json: not present, so empty patches and harness errors without an "
                                    "instance directory are not visible."])

    def test_a_directory_with_only_a_truncated_result_names_the_file(self):
        for name, file in (("a", "run1/m/i-1/report.json"), ("b", "trial/result.json")):
            path = self.tmp / name / file
            path.parent.mkdir(parents=True)
            path.write_text('{"i-1": {"resol', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, f"no reader recognises this directory.* Found {file}, which could "
                                                    "not be read as either"):
                detect_format(self.tmp / name)


class Finding19Docs(unittest.TestCase):
    def test_make_demo_builds_every_ignored_demo_directory(self):
        makefile = (ROOT / "Makefile").read_text(encoding="utf-8")
        ignored = (ROOT / ".gitignore").read_text(encoding="utf-8").split()
        for name in ("demo", "demo-inspect", "demo-harbor", "demo-swebench"):
            self.assertIn(f"--out {name}\n", makefile)
            self.assertIn(name + "/", ignored)
        self.assertIn(".DS_Store", ignored)   # finding 21

    def test_changelog_lists_every_format(self):
        text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
        self.assertIn("--format auto|generic|harbor|inspect|swebench", text)


if __name__ == "__main__":
    unittest.main()
