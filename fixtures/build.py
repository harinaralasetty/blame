"""Rebuild the synthetic 3 tasks x 3 models x 2 judges x 2 rubric items."""

import json
from pathlib import Path


def build():
    rows = []
    tasks = (
        ("availability:sample", "Answer with a factual sentence about the sky.", (
            ("available", "Return a complete sentence."),
            ("correct", "Give a factual answer."))),
        ("color:sample", "Answer with the word blue. Explain briefly.", (
            ("blue", 'Must include "blue".'),
            ("explain", "Explain briefly."))),
        ("greeting:sample", "Write a greeting.", (
            ("hidden", 'Must include "ORBIT-7", Ada Lovelace and 12 kg.'),
            ("formal", "Use a formal greeting."))),
    )
    for task, instruction, items in tasks:
        for model in ("alpha", "beta", "gamma"):
            for judge in (1, 2):
                if task.startswith("availability"):
                    output = "ERROR: request timed out" if model == "alpha" else "The sky is blue."
                    scores = (0, 0) if model == "alpha" else ((1, judge - 1) if model == "beta" else (1, 1))
                elif task.startswith("color"):
                    output = "green" if model == "alpha" else "Green is my choice."
                    scores = (0, 0 if model == "alpha" else 1)
                else:
                    output = {"alpha": "Yo.", "beta": "Hi.", "gamma": "Hello, Ada Lovelace. ORBIT-7 weighs 12 kg."}[model]
                    scores = (1, 1) if model == "gamma" else (0, 0)
                for (item, rubric), score in zip(items, scores):
                    rows.append({
                        "task_id": task, "model": model, "run_id": "generation-1/epoch-1",
                        "instruction": instruction, "rubric_item_id": item,
                        "rubric_item_text": rubric, "output": output, "score": score,
                        "judge_reasoning": "Synthetic rubric passed." if score else "Synthetic rubric not satisfied.",
                        "judge_run": judge,
                    })
    return rows


if __name__ == "__main__":
    path = Path(__file__).with_name("synthetic.jsonl")
    path.write_text("".join(json.dumps(row) + "\n" for row in build()), encoding="utf-8")
