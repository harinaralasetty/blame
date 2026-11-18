"""The Harbor reader. Fixtures are hand-written; the reader is unverified against real harness output."""

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from blame_cli.formats import detect_format, harbor, load_path, redact
from blame_cli.inputs import load_inputs
from blame_cli.reports import build_report, markdown, static_html

from test_golden import check_golden


ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "fixtures/harbor-job"


def write_trial(job: Path, name: str = "task__t1", stdout: str | None = None, **changes) -> Path:
    data = {"id": "abcdef12-0000-4000-8000-000000000000", "task_name": "task", "trial_name": name,
            "trial_uri": "file:///home/example/jobs/" + name, "task_checksum": "sha-1",
            "config": {"trials_dir": "/home/example/jobs"},
            "agent_info": {"name": "agent-a", "version": "1", "model_info": {"name": "m", "provider": "p"}},
            "verifier_result": {"rewards": {"reward": 0}}, "exception_info": None} | changes
    trial = job / name
    trial.mkdir(parents=True)
    (trial / "result.json").write_text(json.dumps(data), encoding="utf-8")
    if stdout is not None:
        (trial / "verifier").mkdir()
        (trial / "verifier" / "test-stdout.txt").write_text(stdout, encoding="utf-8")
    return trial


def exception(name: str, message: str = "boom", **extra) -> dict:
    return {"exception_type": name, "exception_message": message,
            "exception_traceback": "File \"/home/example/x.py\"", **extra}


class Case(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.job = Path(tmp.name) / "job-1"
        self.job.mkdir()

    def one(self, name: str = "task__t1", **changes):
        trial = write_trial(self.job, name, **changes)
        records, warnings = harbor.load(trial)
        self.assertEqual(warnings, [])
        return records[0]


class DetectionTests(Case):
    def test_trial_job_and_jobs_directories_are_harbor(self):
        trial = write_trial(self.job)
        (self.job / "result.json").write_text('{"n_total_trials": 1}', encoding="utf-8")
        for path in (trial, self.job, self.job.parent):
            self.assertEqual(detect_format(path), "harbor")
            records, warnings = load_path(path)
            self.assertEqual(([r.run_id for r in records], [r.job_id for r in records], warnings),
                             (["task__t1@abcdef12"], ["job-1"], []))

    def test_three_levels_down_or_another_result_json_is_not_harbor(self):
        write_trial(self.job / "a" / "b")
        self.assertFalse(harbor.detect(self.job.parent))
        other = self.job.parent / "other"
        other.mkdir()
        (other / "result.json").write_text('{"trial_name": "x"}', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "no reader recognises this directory.*Harbor.*trial_name and agent_info"):
            detect_format(other)
        self.assertFalse(harbor.detect(other / "result.json"))

    def test_forced_format_on_a_directory_without_trials_is_an_error(self):
        with self.assertRaisesRegex(ValueError, "no readable Harbor trial result found"):
            load_path(self.job, "harbor")


class MappingTests(Case):
    def test_plain_failure(self):
        record = self.one(stdout="1 failed\n")
        self.assertEqual(
            (record.task_id, record.agent, record.model, record.system, record.run_id, record.job_id, record.task_version),
            ("task", "agent-a", "p/m", "agent-a / p/m", "task__t1@abcdef12", "job-1", "sha-1"))
        self.assertEqual((record.rubric_item_id, record.score, record.role, record.error, record.error_kind),
                         ("reward", 0.0, "candidate", None, None))
        self.assertEqual((record.instruction, record.rubric_item_text, record.output), (None, None, None))
        self.assertEqual(record.judge_reasoning, "1 failed\n")

    def test_model_provider_is_optional_and_model_may_be_absent(self):
        self.assertEqual(self.one(agent_info={"name": "agent-a", "version": "1", "model_info": {"name": "m"}}).model, "m")
        record = self.one(name="task__t2", agent_info={"name": "agent-a", "version": "1", "model_info": None})
        self.assertEqual((record.model, record.system), ("", "agent-a"))

    def test_oracle_is_the_reference_and_nop_is_skipped(self):
        write_trial(self.job, "task__ref", agent_info={"name": "oracle", "version": "1"})
        write_trial(self.job, "task__nop", agent_info={"name": "nop", "version": "1"})
        records, warnings = harbor.load(self.job)
        self.assertEqual([(r.agent, r.role) for r in records], [("oracle", "reference")])
        self.assertEqual(warnings, ["task__nop/result.json: trial of the nop agent skipped; it is not a system under test."])

    def test_missing_id_and_checksum(self):
        record = self.one(id=None, task_checksum=None)
        self.assertEqual((record.run_id, record.task_version), ("task__t1", None))

    def test_reward_key_selection(self):
        record = self.one(verifier_result={"rewards": {"reward": 1, "speed": 0.2, "style": 3}})
        self.assertEqual(record.score, 1.0)
        self.assertEqual(record.judge_reasoning, "Other reward keys, not scored: speed=0.2, style=3.")
        record = self.one(name="task__t2", verifier_result={"rewards": {"accuracy": 0.5}}, stdout="half\n")
        self.assertEqual((record.score, record.rubric_item_id), (0.5, "reward"))
        self.assertEqual(record.judge_reasoning, "Scored reward key: accuracy.\nhalf")

    def test_no_usable_reward_is_ungraded_never_zero(self):
        cases = ((None, "no verifier reward recorded"), ({"rewards": None}, "no verifier reward recorded"),
                 ({"rewards": {}}, "no verifier reward recorded"),
                 ({"rewards": {"a": 1, "b": 0}}, "no reward key to score among: a, b"),
                 ({"rewards": {"reward": 2}}, "reward reward=2 is not a number in [0, 1]"),
                 ({"rewards": {"reward": -0.5}}, "reward reward=-0.5 is not a number in [0, 1]"),
                 ({"rewards": {"reward": True}}, "reward reward=True is not a number in [0, 1]"),
                 ({"rewards": {"reward": "1"}}, "reward reward='1' is not a number in [0, 1]"))
        for number, (verifier, error) in enumerate(cases):
            record = self.one(name=f"task__n{number}", verifier_result=verifier)
            self.assertEqual((record.score, record.error, record.error_kind), (None, error, "unknown"))

    def test_exception_text_and_kind_come_from_the_name_table(self):
        cases = (("AgentTimeoutError", "agent", 0.0), ("VerifierTimeoutError", "grader", None),
                 ("SandboxBuildFailedError", "infra", None), ("RateLimitError", "infra", None),
                 ("APIResponseValidationError", "infra", None), ("BadRequestError", "setup", None),
                 ("CancelledError", "setup", None), ("RegradeError", "unknown", None),
                 ("NeverHeardOfItError", "unknown", 0.0))
        for number, (name, kind, score) in enumerate(cases):
            record = self.one(name=f"task__e{number}", exception_info=exception(name))
            self.assertEqual((record.error_kind, record.score), (kind, score), name)
            self.assertTrue(record.error.startswith(f"Harbor {name}: boom"), record.error)
        self.assertEqual(len(harbor.ERROR_KIND_BY_NAME), 8 + 4 + 29 + 17 + 1)
        self.assertEqual(sum(kind == "infra" for kind in harbor.ERROR_KIND_BY_NAME.values()), 12 + 16 + 1)

    def test_step_exception_is_used_when_the_trial_has_none(self):
        steps = [{"step_name": "one"}, {"step_name": "two", "exception_info": exception("BadRequestError", "first")},
                 {"step_name": "three", "exception_info": exception("AgentTimeoutError", "second")}]
        self.assertEqual(self.one(step_results=steps).error, "Harbor BadRequestError: first; "
                         "Harbor does not count the recorded reward (reward=0) for this trial")
        record = self.one(name="task__t2", step_results=steps, exception_info=exception("AgentTimeoutError", "trial"))
        self.assertEqual((record.error, record.error_kind, record.score), ("Harbor AgentTimeoutError: trial", "agent", 0.0))

    def test_policy_override(self):
        counted = self.one(exception_info=exception("ApiError", policy_override={"has_valid_reward": True}))
        self.assertEqual((counted.error_kind, counted.score, counted.error),
                         ("agent", 0.0, "Harbor ApiError: boom (policy_override has_valid_reward=true)"))
        dropped = self.one(name="task__t2", exception_info=exception("AgentTimeoutError", policy_override={"has_valid_reward": False}))
        self.assertEqual((dropped.error_kind, dropped.score), ("unknown", None))
        self.assertIn("(policy_override has_valid_reward=false)", dropped.error)
        other = self.one(name="task__t3", exception_info=exception("ApiError", policy_override={"should_retry": False}))
        self.assertEqual((other.error_kind, other.score), ("infra", None))
        self.assertNotIn("policy_override", other.error)

    def test_recorded_validity_wins_over_the_table(self):
        # reward_valid first, then the recorded policy, then the name table.
        policy = {"policy": {"has_valid_reward": False}}
        self.assertIsNone(self.one(exception_info=exception("NeverHeardOfItError", **policy)).score)
        self.assertEqual(self.one(name="task__t2", exception_info=exception("NeverHeardOfItError", **policy),
                                  reward_valid=True).score, 0.0)
        self.assertEqual(self.one(name="task__t3", exception_info=exception("ApiError", policy={"has_valid_reward": True})).score, 0.0)
        record = self.one(name="task__t4", reward_valid=False)
        self.assertEqual((record.score, record.error_kind), (None, "unknown"))
        self.assertIn("does not count the recorded reward", record.error)

    def test_test_output_tail_and_redaction(self):
        record = self.one(stdout="x" * 3000 + " opened /Users/somebody/proj/a.txt\n",
                          exception_info=exception("AgentTimeoutError", "log at /home/somebody/.cache/h.log"))
        self.assertEqual(len(record.judge_reasoning), 2000)
        self.assertTrue(record.judge_reasoning.endswith(" opened ~/proj/a.txt\n"))
        self.assertEqual(record.error, "Harbor AgentTimeoutError: log at ~/.cache/h.log")
        self.assertEqual(redact(r"C:\Users\somebody\a.txt and /usr/lib"), r"~\a.txt and /usr/lib")

    def test_unread_keys_never_reach_a_report(self):
        records, warnings = load_inputs([str(FIXTURE)])
        report = build_report(records, [w.replace(str(FIXTURE), "fixtures/harbor-job") for w in warnings])
        text = json.dumps(report) + markdown(report) + static_html(report)
        for word in ("trial_uri", "exception_traceback", "trials_dir", "/home/", "/Users/"):
            self.assertNotIn(word, text)

    def test_structural_errors_name_the_file(self):
        write_trial(self.job, task_name="")
        with self.assertRaisesRegex(ValueError, r"^task__t1/result.json: task_name must be a non-empty string$"):
            harbor.load(self.job)

    def test_unreadable_result_is_skipped_with_one_warning(self):
        write_trial(self.job)
        for name, text in (("task__bad", "{"), ("task__list", "[]")):
            (self.job / name).mkdir()
            (self.job / name / "result.json").write_text(text, encoding="utf-8")
        records, warnings = harbor.load(self.job)
        self.assertEqual(len(records), 1)
        self.assertEqual(warnings, ["task__bad/result.json: unreadable result file skipped (not valid UTF-8 JSON).",
                                    "task__list/result.json: unreadable result file skipped (not a JSON object)."])


class MergeTests(Case):
    def test_a_trial_read_under_two_jobs_is_kept_once(self):
        write_trial(self.job)
        write_trial(self.job.parent / "job-2")
        records, warnings = load_inputs([str(self.job), str(self.job.parent / "job-2")])
        self.assertEqual([r.job_id for r in records], ["job-1"])
        self.assertEqual(warnings, ["Harbor trial task__t1@abcdef12 of task task appears under jobs job-1 and job-2; "
                                    "the first copy is kept."])

    def test_the_same_directory_twice_is_a_plain_duplicate(self):
        write_trial(self.job)
        records, warnings = load_inputs([str(self.job), str(self.job)])
        self.assertEqual(len(records), 1)
        self.assertRegex(warnings[0], "duplicate record [0-9a-f]{12} ignored")

    def test_mixed_task_checksums_warn(self):
        write_trial(self.job)
        write_trial(self.job, "task__t2", id="12345678-0000", task_checksum="sha-2")
        records, warnings = load_inputs([str(self.job)])
        self.assertEqual(len(records), 2)
        self.assertEqual(warnings, ["Harbor task task has 2 task checksums across the supplied trials."])

    def test_formats_can_be_mixed_and_keep_input_order(self):
        write_trial(self.job)
        records, _ = load_inputs([str(ROOT / "fixtures/v2.jsonl"), str(self.job), str(ROOT / "fixtures/synthetic.jsonl")])
        self.assertEqual([r.task_id == "task" for r in records].index(True), 25)
        self.assertEqual(len(records), 25 + 1 + 36)


class FixtureTests(unittest.TestCase):
    def test_fixture_report(self):
        records, warnings = load_inputs([str(FIXTURE.relative_to(ROOT))] if Path.cwd() == ROOT else [str(FIXTURE)])
        report = build_report(records, [w.replace(str(FIXTURE), "fixtures/harbor-job") for w in warnings])
        check_golden(self, "harbor", report)
        self.assertEqual((report["scored_items"], report["lost_items"], report["ungraded_items"], report["reference_items"]),
                         (7, 6, 5, 3))
        self.assertEqual(len(report["warnings"]), 2)
        self.assertEqual({row["task_id"]: row["primary_label"] for row in report["by_task"]},
                         {"parse-log": "reference_fails", "sort-numbers": "reference_flaky"})
        matched = {match["label"] for item in report["items"] for match in item["matches"]}
        self.assertEqual(matched, {"infra", "setup_error", "grader_error", "reference_flaky", "reference_fails",
                                   "item_everyone_loses", "attempts_flip", "unclassified_error"})

    def test_cli_reads_the_directory_with_and_without_the_flag(self):
        with tempfile.TemporaryDirectory() as tmp:
            for extra in ([], ["--format", "harbor"]):
                result = subprocess.run([sys.executable, "-m", "blame_cli", "report", "fixtures/harbor-job", *extra,
                                         "--out", tmp], cwd=ROOT, text=True, capture_output=True)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn("6 lost items, 5 ungraded", result.stdout)
            wrong = subprocess.run([sys.executable, "-m", "blame_cli", "report", "fixtures", "--format", "harbor",
                                    "--out", tmp], cwd=ROOT, text=True, capture_output=True)
            self.assertEqual(wrong.returncode, 0, wrong.stderr)  # fixtures/ holds the job one level down
            help_text = subprocess.run([sys.executable, "-m", "blame_cli", "report", "--help"], cwd=ROOT, text=True,
                                       capture_output=True).stdout
            self.assertIn("unverified against real harness", " ".join(help_text.split()))


if __name__ == "__main__":
    unittest.main()
