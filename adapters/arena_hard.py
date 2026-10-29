"""Arena-Hard v0.1 published pairwise judgments -> blame generic JSONL.

See adapters/README.md for score semantics, field mapping and reproduction.
Only HTTPS downloads with curl are used; no HF client, credentials or dependencies.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


REVISION = "15f3746e21432264ce9b453999bde4f3c946d2e6"
REPO = "https://huggingface.co/datasets/lmarena-ai/arena-hard-auto"
JUDGE = "gpt-4-1106-preview"
BASELINE = "gpt-4-0314"
MODELS = ("claude-3-opus-20240229", "gpt-3.5-turbo-0125", "llama-3-70b-instruct")
BENCH = "data/arena-hard-v0.1"
FILES = ("README.md", f"{BENCH}/question.jsonl",
         *(f"{BENCH}/model_answer/{m}.jsonl" for m in (BASELINE, *MODELS)),
         *(f"{BENCH}/model_judgment/{JUDGE}/{m}.jsonl" for m in MODELS))


def read_index(path):
    result = {}
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row["uid"] in result:
                raise ValueError(f"duplicate uid in {path}: {row['uid']}")
            result[row["uid"]] = row
    return result


def answer_text(answer):
    messages = answer["messages"]
    if (len(messages) != 2 or messages[0]["role"] != "user"
            or messages[1]["role"] != "assistant"):
        raise ValueError("expected a single-turn user/assistant conversation")
    value = messages[1]["content"]["answer"]
    if not isinstance(value, str):
        raise ValueError("answer must be text")
    return value


def game_prompt(question, left, right):
    return (f"<|User Prompt|>\n{question}\n\n"
            f"<|The Start of Assistant A's Answer|>\n{left}\n<|The End of Assistant A's Answer|>\n\n"
            f"<|The Start of Assistant B's Answer|>\n{right}\n<|The End of Assistant B's Answer|>")


def candidate_score(score, game):
    # Game 1: candidate is B; game 2: candidate is A. Collapse strength, not ties.
    if game not in (1, 2):
        raise ValueError("game must be 1 or 2")
    if score == "A=B":
        return 0.5
    if score not in ("A>B", "A>>B", "B>A", "B>>A"):
        raise ValueError(f"unsupported or missing pairwise score: {score!r}")
    winner = score[0]
    return float(winner == ("B" if game == 1 else "A"))


def convert_pair(question, answer, baseline, judgment):
    uid = question["uid"]
    if any(row["uid"] != uid for row in (answer, baseline, judgment)):
        raise ValueError("question/answer/judgment uid mismatch")
    if (answer["model"] != judgment["model"] or baseline["model"] != BASELINE
            or judgment["baseline"] != BASELINE or judgment["judge"] != JUDGE):
        raise ValueError("unexpected model, baseline or judge identity")
    prompt = question["prompt"]
    if any(row["messages"][0]["content"] != prompt for row in (answer, baseline)):
        raise ValueError("answer instruction differs from question")
    output, reference = answer_text(answer), answer_text(baseline)
    games = judgment["games"]
    if len(games) != 2:
        raise ValueError("expected exactly two order-swapped games")
    rubric = ("Pairwise preference against the fixed gpt-4-0314 answer: "
              "win=1, tie=0.5, loss=0; preference strength is collapsed. "
              "This is a relative preference, not absolute answer correctness.\n\n"
              "Baseline answer (identical in both games):\n" + reference)
    records = []
    for game_id, game in enumerate(games, 1):
        left, right = (reference, output) if game_id == 1 else (output, reference)
        if game["user_prompt"] != game_prompt(prompt, left, right):
            raise ValueError(f"{uid}: game {game_id} prompt/answer mismatch")
        if not isinstance(game["judgment"], str):
            raise ValueError("judge reasoning must be text")
        records.append(dict(
            task_id=f"arena-hard-v0.1:{uid}", model=answer["model"],
            run_id=answer["ans_id"], instruction=prompt,
            rubric_item_id=f"preference-vs-{BASELINE}", rubric_item_text=rubric,
            output=output, score=candidate_score(game["score"], game_id),
            judge_reasoning=game["judgment"], judge_run=game_id, error=None,
        ))
    return records


def download(root):
    for filename in FILES:
        path = root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        # Re-download to ensure an existing file cannot silently select another revision.
        subprocess.run(["curl", "--fail", "--location", "--silent", "--show-error",
                        "--retry", "2", "--max-time", "120",
                        f"{REPO}/resolve/{REVISION}/{filename}", "--output", str(path)], check=True)


def convert(root, out):
    bench = root / BENCH
    questions = read_index(bench / "question.jsonl")
    baseline = read_index(bench / f"model_answer/{BASELINE}.jsonl")
    records = []
    for model in MODELS:
        answers = read_index(bench / f"model_answer/{model}.jsonl")
        judgments = read_index(bench / f"model_judgment/{JUDGE}/{model}.jsonl")
        if set(questions) != set(answers) or set(questions) != set(judgments):
            raise ValueError(f"{model}: incomplete question/answer/judgment coverage")
        for uid in sorted(questions):
            records.extend(convert_pair(questions[uid], answers[uid], baseline[uid], judgments[uid]))
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    manifest = {"dataset": "lmarena-ai/arena-hard-auto / arena-hard-v0.1",
                "revision": REVISION, "license": "Apache-2.0 (dataset card)",
                "judge": JUDGE, "baseline": BASELINE, "models": list(MODELS),
                "prompts": len(questions), "records": len(records),
                "generic_sha256": hashlib.sha256(out.read_bytes()).hexdigest(),
                "files": [{"path": name, "url": f"{REPO}/resolve/{REVISION}/{name}",
                           "bytes": (root / name).stat().st_size,
                           "sha256": hashlib.sha256((root / name).read_bytes()).hexdigest()}
                          for name in FILES]}
    out.with_suffix(".manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=Path("data/arena_hard"))
    parser.add_argument("--out", type=Path, default=Path("data/arena_hard/generic.jsonl"))
    parser.add_argument("--download", action="store_true")
    args = parser.parse_args()
    if args.download:
        download(args.source)
    manifest = convert(args.source, args.out)
    print(f"Wrote {manifest['records']} observations for {manifest['prompts']} prompts to {args.out}")


if __name__ == "__main__":
    main()
