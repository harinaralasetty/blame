from dataclasses import replace
import unittest

from blame_cli.detectors import (
    HeuristicReasoner, infra, item_everyone_loses, judge_unstable,
    triage, unstated_requirement,
)
from blame_cli.model import Record


def rec(**changes):
    base = Record("task", "alpha", "run", "Write a greeting.", "item",
                  "Use a formal greeting.", "Yo.", 0, "Too informal.", 1)
    return replace(base, **changes)


class InfraTests(unittest.TestCase):
    def test_rule_table_positive_examples(self):
        examples = {
            "timeout": ["timeout", "ERROR: request timed out", "Connection timeout: upstream"],
            "rate_limit": ["HTTP 429", "429 Too Many Requests", "rate limit exceeded", "Error: rate-limited"],
            "server_error": ["HTTP 503", "HTTP error: 502 Bad Gateway", "500 Internal Server Error", "Bad gateway", "gateway timeout"],
            "missing_artifact": ["Missing artifact: result.json", "Artifact not found: result.csv"],
            "empty_output": ["", " \n\t"],
        }
        for rule, outputs in examples.items():
            for output in outputs:
                with self.subTest(output=output):
                    finding = infra(rec(output=output))
                    self.assertIsNotNone(finding)
                    self.assertEqual(finding.evidence["rule"], rule)
                    self.assertEqual(finding.evidence["quote"], output)
        self.assertEqual(infra(rec(error="Sandbox exited with code 2")).evidence["rule"], "error_field")

    def test_error_discussion_is_not_infrastructure_failure(self):
        for output in ("Use timeout=30 and retry HTTP 429.", "The server returned HTTP 500 yesterday.",
                       "There is no missing artifact.", "The number is 429.",
                       "Timeouts are common; here is a working answer.", "5xx means a server error."):
            with self.subTest(output=output):
                self.assertIsNone(infra(rec(output=output)))
        self.assertIsNone(infra(rec(score=1, output="")))
        self.assertIsNone(infra(rec(error="")))


class JudgeTests(unittest.TestCase):
    def test_pairwise_flip_rate_and_quotes(self):
        a = rec()
        peers = [a, rec(judge_run=2, score=1), rec(judge_run=3, score=0)]
        result = judge_unstable(a, peers)
        self.assertAlmostEqual(result.evidence["flip_rate"], 2 / 3)
        self.assertEqual(result.evidence["judge_pairs"], 3)
        self.assertEqual(result.evidence["output_quote"], a.output)
        self.assertEqual(judge_unstable(a, peers + [a]).evidence["judge_pairs"], 3)

    def test_all_identity_boundaries(self):
        a = rec()
        for changes in ({"output": "Different."}, {"model": "beta"}, {"run_id": "run-2"},
                        {"rubric_item_id": "other"}, {"task_id": "other"},
                        {"instruction": "Other instruction."}, {"rubric_item_text": "Other rubric."}):
            with self.subTest(changes=changes):
                self.assertIsNone(judge_unstable(a, [a, rec(score=1, judge_run=2, **changes)]))
        for other in (rec(judge_run=None, score=1), rec(judge_run=1, score=1), rec(judge_run=2)):
            self.assertIsNone(judge_unstable(a, [a, other]))
        self.assertIsNone(judge_unstable(rec(judge_run=None), [a, rec(score=1, judge_run=2)]))


class EveryoneTests(unittest.TestCase):
    def test_zero_across_models_and_runs(self):
        a = rec()
        peers = [a, rec(model="beta"), rec(model="beta", run_id="run-2")]
        finding = item_everyone_loses(a, peers)
        self.assertEqual(finding.evidence["model_count"], 2)
        self.assertEqual(finding.evidence["zero_count"], 3)
        self.assertEqual(finding.evidence["run_count"], 3)

    def test_abstain_on_single_model_partial_credit_or_changed_rubric(self):
        a = rec()
        self.assertIsNone(item_everyone_loses(a, [a, rec(run_id="run-2")]))
        for other in (rec(model="beta", score=0.1), rec(model="beta", score=1),
                      rec(model="beta", instruction="Different."),
                      rec(model="beta", rubric_item_text="Changed rubric.")):
            self.assertIsNone(item_everyone_loses(a, [a, other]))


class UnstatedTests(unittest.TestCase):
    def test_missing_anchors_and_closest_sentence(self):
        reasoner = HeuristicReasoner()
        result = reasoner.missing_requirements(
            "Write a greeting. Include the payload mass.",
            'Must include "ORBIT-7", Ada Lovelace and a payload mass of 12 kg.')
        self.assertEqual(set(result["missing_terms"]), {"ORBIT-7", "Ada Lovelace", "12", "kg"})
        self.assertEqual(result["closest_instruction_sentence"], "Include the payload mass.")

    def test_anchor_types(self):
        for rubric, term in (("Must include 12.", "12"), ("Use kg.", "kg"),
                             ("Must mention Ada Lovelace.", "Ada Lovelace"),
                             ("Use NASA.", "NASA"), ('Must include “orbit”.', "orbit"),
                             ("Must include 'orbit'.", "orbit")):
            with self.subTest(rubric=rubric):
                result = HeuristicReasoner().missing_requirements("Write a greeting.", rubric)
                self.assertIn(term, result["missing_terms"])

    def test_literal_presence_boundaries_and_abstentions(self):
        reasoner = HeuristicReasoner()
        for instruction, rubric in (
            ('Include 12 KG and ada lovelace and "blue".', 'Must include 12 kg, Ada Lovelace and "BLUE".'),
            ("Write a greeting.", "Use a formal greeting."),
            ("Write a greeting.", 'Must not include "secret".'),
            ("Write a greeting.", 'Include a greeting, for example "hello".'),
            ("Write a greeting.", 'Include "hello" or "hi".'),
            ("Write a greeting.", 'The answer could say "hi".'),
        ):
            with self.subTest(rubric=rubric):
                self.assertIsNone(reasoner.missing_requirements(instruction, rubric))
        result = reasoner.missing_requirements("Return 120 items in kilograms.", "Must include 12 kg.")
        self.assertEqual(result["missing_terms"], ["12", "kg"])

    def test_injected_reasoner_and_default(self):
        class StubReasoner:
            def missing_requirements(self, instruction, rubric):
                return {"missing_terms": ["injected"], "closest_instruction_sentence": instruction}
        self.assertEqual(unstated_requirement(rec(), StubReasoner()).evidence["missing_terms"], ["injected"])
        self.assertEqual(triage([rec()])[0]["label"], "genuine_failure")
        self.assertLess(triage([rec()])[0]["confidence"], 0.6)
        self.assertEqual(triage([rec()], StubReasoner())[0]["label"], "unstated_requirement")

    def test_precedence_preserves_overlapping_matches(self):
        a = rec(output="", rubric_item_text='Must include "secret".')
        result = triage([a, replace(a, model="beta")])[0]
        self.assertEqual(result["label"], "infra")
        self.assertEqual([m["label"] for m in result["matches"]],
                         ["infra", "item_everyone_loses", "unstated_requirement"])


if __name__ == "__main__":
    unittest.main()
