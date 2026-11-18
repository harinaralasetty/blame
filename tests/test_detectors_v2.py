"""The detectors added with record schema 2, and the harness-aware infra rule."""

import csv
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest

from blame_cli.detectors import (
    DETECTORS, attempts_flip, build_index, grader_error, infra, item_everyone_loses,
    reference_fails, reference_flaky, setup_error, triage, unclassified_error,
)
from blame_cli.inputs import load_inputs
from blame_cli.labels import score_labels, write_labels
from blame_cli.model import CLASSES, LABELS, Record, validate
from blame_cli.reports import build_report


ROOT = Path(__file__).resolve().parents[1]


def trial(**changes) -> Record:
    values = {"task_id": "t1", "model": "", "agent": "agent-a", "run_id": "trial-1", "instruction": None,
              "rubric_item_id": "reward", "rubric_item_text": None, "output": None, "score": 0.0,
              "judge_reasoning": "", "task_version": "sha-1", "job_id": "job-1"}
    return validate(Record(**(values | changes)))


def reference(**changes) -> Record:
    return trial(**({"agent": "oracle", "role": "reference"} | changes))


def verdict(records, record=None):
    """(label, matches) for one record, the first by default."""
    wanted = (record or records[0]).record_id
    item = next(v for v in triage(records) if v["record_id"] == wanted)
    return item["label"], [m["label"] for m in item["matches"]]


class LabelTableTests(unittest.TestCase):
    def test_detectors_follow_label_precedence(self):
        self.assertEqual(tuple(name for name, _ in DETECTORS), CLASSES[:-1])
        self.assertEqual(len(CLASSES), 11)
        self.assertEqual(CLASSES[-1], "genuine_failure")
        self.assertEqual({info.category for info in LABELS},
                         {"infra", "setup", "grader", "task", "instruction", "unexplained"})
        for info in LABELS:
            self.assertTrue(info.next_step.endswith("."))


class ErrorKindTests(unittest.TestCase):
    def test_harness_class_replaces_the_v1_error_rule(self):
        finding = infra(trial(score=None, error="sandbox died", error_kind="infra"))
        self.assertEqual((finding.confidence, finding.evidence["rule"], finding.evidence["quote"]),
                         (0.80, "error_kind", "sandbox died"))
        for kind in ("setup", "grader", "agent", "unknown"):
            self.assertIsNone(infra(trial(error="boom", error_kind=kind, output="")))
        # No class: 0.1.0 behaviour, a non-empty error is infra at 0.99.
        self.assertEqual(infra(trial(error="boom")).confidence, 0.99)
        self.assertIsNone(infra(trial()))

    def test_each_error_class_gets_its_label(self):
        cases = (("setup", setup_error, "setup_error", 0.85), ("grader", grader_error, "grader_error", 0.85),
                 ("unknown", unclassified_error, "unclassified_error", 0.40))
        for kind, rule, label, strength in cases:
            record = trial(score=None, error="recorded text", error_kind=kind)
            finding = rule(record)
            self.assertEqual((finding.label, finding.confidence, finding.evidence["error"]),
                             (label, strength, "recorded text"))
            self.assertEqual(verdict([record]), (label, [label]))
            for other in (setup_error, grader_error, unclassified_error):
                if other is not rule:
                    self.assertIsNone(other(record))

    def test_agent_error_stays_a_default_failure_with_the_error_shown(self):
        record = trial(error="Harbor AgentTimeoutError: stopped", error_kind="agent")
        item = triage([record])[0]
        self.assertEqual((item["label"], item["matches"]), ("genuine_failure", []))
        self.assertEqual(item["evidence"]["error"], "Harbor AgentTimeoutError: stopped")
        self.assertNotIn("error", triage([trial()])[0]["evidence"])


class ReferenceTests(unittest.TestCase):
    def test_reference_fails_strength_depends_on_attempts_and_versions(self):
        record = trial()
        one = reference_fails(record, build_index([record, reference()]))
        self.assertEqual(one.confidence, 0.75)
        two = reference_fails(record, build_index([record, reference(), reference(run_id="trial-2")]))
        self.assertEqual(two.confidence, 0.90)
        self.assertEqual(two.evidence["observed"], "The reference solution did not pass in 2 of 2 attempts.")
        self.assertEqual(two.evidence["task_version"], "same as this attempt")
        for a, b in ((None, "sha-1"), ("sha-1", None), (None, None)):
            cand = trial(task_version=a)
            capped = reference_fails(cand, build_index([cand, reference(task_version=b),
                                                        reference(task_version=b, run_id="trial-2")]))
            self.assertEqual((capped.confidence, capped.evidence["task_version"]),
                             (0.60, "task version not available"))

    def test_reference_on_another_task_version_is_ignored(self):
        record = trial()
        index = build_index([record, reference(task_version="sha-2"), reference(task_version="sha-2", run_id="trial-2", score=1.0)])
        self.assertIsNone(reference_fails(record, index))
        self.assertIsNone(reference_flaky(record, index))

    def test_reference_pass_or_no_reference_abstains(self):
        record = trial()
        self.assertIsNone(reference_fails(record, build_index([record])))
        self.assertIsNone(reference_fails(record, build_index([record, reference(score=1.0)])))
        self.assertIsNone(reference_flaky(record, build_index([record, reference(score=1.0)])))
        self.assertIsNone(reference_flaky(record, build_index([record, reference()])))
        # A reference result on another check of the task says nothing about this one.
        self.assertIsNone(reference_fails(record, build_index([record, reference(rubric_item_id="other")])))

    def test_reference_flaky_needs_a_pass_and_a_scored_failure(self):
        record = trial()
        refs = [reference(score=1.0), reference(run_id="trial-2", score=0.5)]
        finding = reference_flaky(record, build_index([record, *refs]))
        self.assertEqual((finding.confidence, finding.evidence["observed"]),
                         (0.85, "The reference solution passed 1 of 2 attempts."))
        self.assertEqual(verdict([record, *refs])[0], "reference_flaky")

    def test_excluded_reference_attempts_are_no_evidence(self):
        record = trial()
        broken = [reference(run_id=f"trial-{n}", score=score, error="x", error_kind=kind)
                  for n, (kind, score) in enumerate((("infra", None), ("setup", 0.0), ("grader", 0.0)), 2)]
        ungraded = reference(run_id="trial-9", score=None, error="no reward", error_kind="unknown")
        index = build_index([record, *broken, ungraded])
        self.assertIsNone(reference_fails(record, index))
        self.assertIsNone(reference_flaky(record, index))
        # With one real pass, excluded failures still do not make the reference look unsteady.
        self.assertIsNone(reference_flaky(record, build_index([record, reference(score=1.0), *broken, ungraded])))
        # An error the harness counts as a valid failure stays in.
        counted = reference(run_id="trial-8", error="x", error_kind="agent")
        self.assertEqual(reference_fails(record, build_index([record, counted])).confidence, 0.75)

    def test_reference_records_are_never_triaged(self):
        self.assertEqual(triage([reference(), reference(run_id="trial-2", score=None, error="x")]), [])

    def test_reference_label_outranks_everyone_loses_and_both_are_kept(self):
        records = [trial(), trial(agent="agent-b"), reference(), reference(run_id="trial-2")]
        self.assertEqual(verdict(records), ("reference_fails", ["reference_fails", "item_everyone_loses"]))


class EveryoneLosesV2Tests(unittest.TestCase):
    def test_strength_grows_with_the_number_of_systems(self):
        for count, strength in ((2, 0.50), (3, 0.70), (4, 0.70), (5, 0.90), (7, 0.90)):
            group = [trial(agent=f"agent-{n}") for n in range(count)]
            finding = item_everyone_loses(group[0], group)
            self.assertEqual(finding.confidence, strength)
            self.assertEqual(finding.evidence["observed"], f"No supplied system scored above zero ({count} systems).")
        self.assertIsNone(item_everyone_loses(trial(), [trial(), trial(run_id="trial-2")]))

    def test_same_model_under_two_agents_is_two_systems(self):
        group = [trial(model="m"), trial(model="m", agent="agent-b")]
        self.assertEqual(item_everyone_loses(group[0], group).evidence["models"], ["agent-a / m", "agent-b / m"])

    def test_mixed_task_versions_abstain(self):
        group = [trial(), trial(agent="agent-b", task_version="sha-2")]
        self.assertIsNone(item_everyone_loses(group[0], group))
        group = [trial(), trial(agent="agent-b", task_version=None)]
        self.assertIsNone(item_everyone_loses(group[0], group))

    def test_ungraded_excluded_and_reference_records_are_left_out(self):
        base = [trial(), trial(agent="agent-b")]
        extras = [trial(agent="agent-c", score=None, error="x", error_kind="unknown"),
                  trial(agent="agent-d", score=1.0, error="x", error_kind="infra"),
                  trial(agent="agent-e", error="x", error_kind="setup"),
                  trial(agent="agent-f", error="x", error_kind="grader"),
                  reference(score=1.0)]
        finding = item_everyone_loses(base[0], base + extras)
        self.assertEqual((finding.evidence["model_count"], finding.confidence), (2, 0.50))
        # Excluded attempts alone are not a cohort, and an excluded record gets no cohort label.
        self.assertIsNone(item_everyone_loses(base[0], [base[0], extras[2], extras[3]]))
        self.assertIsNone(item_everyone_loses(extras[2], base + extras))
        # An error the harness counts as a valid failure is a real zero.
        counted = trial(agent="agent-g", error="x", error_kind="agent")
        self.assertEqual(item_everyone_loses(base[0], base + [counted]).evidence["model_count"], 3)
        self.assertIsNone(item_everyone_loses(base[0], base + [trial(agent="agent-h", score=1.0)]))


class AttemptsFlipTests(unittest.TestCase):
    def test_fires_when_the_same_system_also_passed(self):
        records = [trial(), trial(run_id="trial-2", score=1.0), trial(run_id="trial-3", score=0.5)]
        finding = attempts_flip(records[0], build_index(records))
        self.assertEqual((finding.confidence, finding.evidence["observed"], finding.evidence["passed_run_ids"]),
                         (0.40, "This system passed 1 of 3 attempts.", ["trial-2"]))
        self.assertEqual(verdict(records), ("attempts_flip", ["attempts_flip"]))
        self.assertEqual(verdict(records, records[2])[0], "attempts_flip")

    def test_abstains_without_a_pass_by_the_same_system_on_the_same_check(self):
        record = trial()
        for other in (trial(run_id="trial-2"), trial(run_id="trial-2", score=1.0, agent="agent-b"),
                      trial(run_id="trial-2", score=1.0, rubric_item_id="other"),
                      trial(run_id="trial-2", score=1.0, task_id="t2"),
                      trial(run_id="trial-2", score=None, error="x", error_kind="unknown"),
                      reference(run_id="trial-2", score=1.0)):
            with self.subTest(other=other):
                self.assertIsNone(attempts_flip(record, build_index([record, other])))

    def test_two_gradings_of_one_attempt_are_not_two_attempts(self):
        records = [trial(output="x", judge_run=1), trial(output="x", judge_run=2, score=1.0)]
        self.assertIsNone(attempts_flip(records[0], build_index(records)))
        self.assertEqual(verdict(records)[0], "judge_unstable")

    def test_excluded_attempts_do_not_count_either_way(self):
        passed = trial(run_id="trial-2", score=1.0)
        for kind in ("infra", "setup", "grader"):
            failed = trial(error="x", error_kind=kind)
            self.assertIsNone(attempts_flip(failed, build_index([failed, passed])))
        v1_infra = trial(error="x")
        self.assertIsNone(attempts_flip(v1_infra, build_index([v1_infra, passed])))
        self.assertEqual(verdict([v1_infra, passed]), ("infra", ["infra"]))

    def test_no_v1_fixture_can_trigger_it(self):
        for name in ("fixtures/synthetic.jsonl", "fixtures/inspect.json"):
            records, _ = load_inputs([str(ROOT / name)])
            runs = {}
            for record in records:
                runs.setdefault((record.system, record.item_key), set()).add(record.run_id)
            self.assertEqual({len(group) for group in runs.values()}, {1}, name)
            self.assertFalse([v for v in triage(records) if any(m["label"] == "attempts_flip" for m in v["matches"])])

    def test_repeated_runs_of_v1_records_can_get_the_label(self):
        # The documented behaviour change: 0.1.0 called this a genuine failure.
        base = Record("task", "alpha", "run-1", "Write a greeting.", "item", "Use a formal greeting.", "Yo.", 0, "Too informal.")
        self.assertEqual(verdict([base, replace(base, run_id="run-2", output="Good day.", score=1)])[0], "attempts_flip")


class LabelFileTests(unittest.TestCase):
    def score(self, rows):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.csv"
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            return score_labels(str(path))

    def test_human_label_accepts_all_eleven_labels(self):
        rows = [{"record_id": str(n), "predicted_label": "genuine_failure", "detector_labels": "",
                 "human_label": label} for n, label in enumerate(CLASSES)]
        result = self.score(rows)
        self.assertEqual(result["labeled_rows"], 11)
        self.assertEqual(list(result["per_verdict"]), list(CLASSES))
        self.assertEqual(result["per_detector"]["reference_fails"]["support"], 1)

    def test_new_detector_labels_follow_precedence(self):
        row = {"record_id": "1", "predicted_label": "reference_fails",
               "detector_labels": "reference_fails|item_everyone_loses|attempts_flip", "human_label": "attempts_flip"}
        self.assertEqual(self.score([row])["per_detector"]["attempts_flip"]["tp"], 1)
        with self.assertRaisesRegex(ValueError, "precedence"):
            self.score([row | {"predicted_label": "attempts_flip"}])

    def test_0_1_0_label_file_still_scores(self):
        text = (ROOT / "tests/golden/v1/synthetic.labels.csv").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.csv"
            rows = list(csv.DictReader(text.splitlines(keepends=True)))
            for row in rows:
                row["human_label"] = row["predicted_label"]
            with path.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            result = score_labels(str(path))
        self.assertEqual((result["labeled_rows"], result["unlabeled_rows"]), (21, 0))
        self.assertEqual(result["per_verdict"]["infra"]["precision"], 1.0)

    def test_v2_fixture_round_trips_through_label_and_score(self):
        records, warnings = load_inputs([str(ROOT / "fixtures/v2.jsonl")])
        report = build_report(records, warnings)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "labels.csv"
            write_labels(report, str(path))
            result = score_labels(str(path))
        self.assertEqual(result["unlabeled_rows"], len(report["items"]))


if __name__ == "__main__":
    unittest.main()
