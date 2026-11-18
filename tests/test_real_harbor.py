"""The Harbor reader against real harness output (fixtures/real-harbor, Harbor 0.24.0)."""

from pathlib import Path
import unittest

from blame_cli.inputs import load_inputs
from blame_cli.reports import build_report


ROOT = Path(__file__).resolve().parent.parent
FIXTURE = ROOT / "fixtures/real-harbor"


class RealHarborTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.records, cls.warnings = load_inputs([str(FIXTURE)])
        cls.by_job = {}
        for record in cls.records:
            cls.by_job.setdefault(record.job_id, []).append(record)

    def test_every_job_but_the_nop_job_is_read(self):
        self.assertEqual(sorted(self.by_job), ["broken-run", "cand-broken", "cand-slow", "cand-wrong", "oracle-run"])
        self.assertEqual(len(self.records), 6)
        self.assertEqual(len(self.warnings), 1)
        self.assertIn("nop agent skipped", self.warnings[0])

    def test_oracle_pass_is_a_reference(self):
        (record,) = self.by_job["oracle-run"]
        self.assertEqual((record.task_id, record.agent, record.role, record.score, record.error),
                         ("hello", "oracle", "reference", 1.0, None))
        self.assertEqual(record.judge_reasoning, "PASS hello.txt\n")
        self.assertEqual(len(record.task_version), 64)

    def test_wrong_answers_are_scored_failures_with_the_test_output(self):
        wrong = self.by_job["cand-wrong"]
        self.assertEqual(len(wrong), 2)
        self.assertEqual(len({record.run_id for record in wrong}), 2)
        for record in wrong:
            self.assertEqual((record.agent, record.role, record.model, record.score, record.error),
                             ("scripted", "candidate", "", 0.0, None))
            self.assertEqual(record.judge_reasoning, "FAIL hello.txt missing or wrong\n")

    def test_agent_timeout_keeps_its_reward(self):
        (record,) = self.by_job["cand-slow"]
        self.assertEqual((record.score, record.error_kind), (0.0, "agent"))
        self.assertEqual(record.error, "Harbor AgentTimeoutError: Agent execution timed out after 5.0 seconds")

    def test_failed_image_build_is_ungraded_and_says_the_agent_never_started(self):
        for job in ("broken-run", "cand-broken"):
            (record,) = self.by_job[job]
            self.assertIsNone(record.score)
            self.assertEqual(record.error_kind, "unknown")
            self.assertTrue(record.error.startswith("Harbor RuntimeError: Docker compose command failed"))
            self.assertIn("the agent never started", record.error)

    def test_report_labels(self):
        report = build_report(self.records, [])
        self.assertEqual((report["scored_items"], report["lost_items"], report["ungraded_items"],
                          report["reference_items"]), (3, 3, 1, 2))
        labels = {task["task_id"]: task["labels"] for task in report["by_task"]}
        self.assertEqual(labels, {"hello": {"genuine_failure": 2}, "slow": {"genuine_failure": 1},
                                  "broken": {"unclassified_error": 1}})
        self.assertEqual([row["model"] for row in report["by_model"]], ["scripted"])


if __name__ == "__main__":
    unittest.main()
