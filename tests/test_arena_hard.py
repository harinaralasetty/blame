"""Pairwise conversion checks: order errors can fabricate judge instability."""

from copy import deepcopy
import unittest

from adapters.arena_hard import (
    BASELINE, JUDGE, candidate_score, convert_pair, game_prompt,
)
from blame_cli.detectors import triage
from blame_cli.model import Record


def pair(scores=("B>A", "A>B")):
    question = {"uid": "public-item", "prompt": "Write a greeting."}

    def answer(model, text):
        return {"uid": question["uid"], "ans_id": model + "-generation", "model": model,
                "messages": [{"role": "user", "content": question["prompt"]},
                             {"role": "assistant", "content": {"answer": text}}]}

    output = answer("candidate", "Hello.")
    baseline = answer(BASELINE, "Yo.")
    judgment = {"uid": question["uid"], "model": "candidate", "baseline": BASELINE,
                "judge": JUDGE, "games": [
                    {"score": scores[0], "judgment": "B wins.",
                     "user_prompt": game_prompt(question["prompt"], "Yo.", "Hello.")},
                    {"score": scores[1], "judgment": "A wins.",
                     "user_prompt": game_prompt(question["prompt"], "Hello.", "Yo.")}]}
    return question, output, baseline, judgment


class ArenaHardTests(unittest.TestCase):
    def test_all_score_mappings_account_for_order_and_collapse_strength(self):
        for score, expected in {"A>>B": (0, 1), "A>B": (0, 1), "A=B": (.5, .5),
                                "B>A": (1, 0), "B>>A": (1, 0)}.items():
            self.assertEqual(tuple(candidate_score(score, g) for g in (1, 2)), expected)
        for value in (None, "", "error", "A<B", 0):
            with self.subTest(value=value), self.assertRaises(ValueError):
                candidate_score(value, 1)

    def test_same_winner_after_swap_does_not_fabricate_instability(self):
        records = [Record.from_dict(r) for r in convert_pair(*pair())]
        self.assertEqual([r.score for r in records], [1, 1])
        self.assertEqual(records[0].judge_key, records[1].judge_key)
        self.assertEqual(triage(records), [])

    def test_real_reversal_fires_with_unchanged_generation_and_full_reasoning(self):
        records = [Record.from_dict(r) for r in convert_pair(*pair(("A>B", "A>B")))]
        verdicts = triage(records)
        self.assertEqual(len(verdicts), 1)
        self.assertEqual(verdicts[0]["label"], "judge_unstable")
        self.assertEqual(verdicts[0]["evidence"]["judge_scores"],
                         [{"judge_run": 1, "score": 0}, {"judge_run": 2, "score": 1}])
        self.assertEqual(records[0].judge_reasoning, "B wins.")
        self.assertIn("Yo.", records[0].rubric_item_text)
        self.assertIsNone(records[0].error)

    def test_mismatched_published_prompt_is_rejected_instead_of_joined(self):
        args = pair()
        bad = deepcopy(args)
        bad[3]["games"][1]["user_prompt"] += "a changed answer"
        with self.assertRaisesRegex(ValueError, "prompt/answer mismatch"):
            convert_pair(*bad)
        bad = deepcopy(args)
        bad[1]["messages"][0]["content"] = "Another prompt."
        with self.assertRaisesRegex(ValueError, "instruction differs"):
            convert_pair(*bad)
        bad = deepcopy(args)
        bad[3]["judge"] = "another-judge"
        with self.assertRaisesRegex(ValueError, "identity"):
            convert_pair(*bad)


if __name__ == "__main__":
    unittest.main()
