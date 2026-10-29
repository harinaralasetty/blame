"""Retain full-run aggregates and the 20 manually audited items; raw bulk stays in data/."""

from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import sys

# Permit the documented `python3 realdata/arena_hard/summarize.py` invocation.
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from adapters.arena_hard import BENCH, JUDGE, MODELS, read_index
from blame_cli.reports import markdown


def choose_sample(items):
    selected = []
    # Four distinct answer pairs per model, in SHA-256(task_id) order.
    for model in MODELS:
        candidates = [v for v in items if v["label"] == "judge_unstable"
                      and v["record"]["model"] == model]
        seen = set()
        for v in sorted(candidates, key=lambda v: hashlib.sha256(v["record"]["task_id"].encode()).hexdigest()):
            key = v["record"]["task_id"]
            if key not in seen:
                seen.add(key)
                selected.append(v)
            if len(seen) == 4:
                break
    # Eight distinct cohort-loss prompts, in SHA-256(task_id + model) order.
    candidates = [v for v in items if v["label"] == "item_everyone_loses"]
    seen = set()
    for v in sorted(candidates, key=lambda v: hashlib.sha256(
            (v["record"]["task_id"] + v["record"]["model"]).encode()).hexdigest()):
        key = v["record"]["task_id"]
        if key not in seen:
            seen.add(key)
            selected.append(v)
        if len(seen) == 8:
            break
    if len(selected) != 20:
        raise ValueError("expected 12 judge and 8 cohort flags")
    return selected


def main():
    out = ROOT / "realdata/arena_hard"
    source = ROOT / "data/arena_hard"
    report = json.loads((source / "full-report/report.json").read_text())
    with (out / "handcheck.csv").open(newline="", encoding="utf-8") as f:
        checks = list(csv.DictReader(f))
    selected = choose_sample(report["items"])
    if [v["record_id"] for v in selected] != [row["record_id"] for row in checks]:
        raise ValueError("sample differs from audited IDs; perform a new hand-check")
    for item, row in zip(selected, checks):
        if item["label"] != row["verdict"] or row["correct"] not in ("yes", "no"):
            raise ValueError("verdict changed or invalid audit label; re-audit")

    context = []
    raw = {m: read_index(source / BENCH / f"model_judgment/{JUDGE}/{m}.jsonl") for m in MODELS}
    for v, row in zip(selected, checks):
        record = v["record"]
        uid = record["task_id"].split(":")[1]
        context.append({"sample_id": int(row["sample_id"]), "record_id": v["record_id"],
                        "source_path": f"{BENCH}/model_judgment/{JUDGE}/{record['model']}.jsonl",
                        "original_pair": raw[record["model"]][uid],
                        "cohort_scores": [{"model": m, "raw_scores": [g["score"] for g in raw[m][uid]["games"]]}
                                          for m in MODELS]})
    (out / "audit_evidence.json").write_text(json.dumps(context, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    metrics = []
    for detector in ("infra", "judge_unstable", "item_everyone_loses", "unstated_requirement", "genuine_failure"):
        sample = [row for row in checks if row["detector"] == detector]
        tp = sum(row["correct"] == "yes" for row in sample)
        metrics.append({"detector": detector, "checked": len(sample), "correct": tp,
                        "incorrect": len(sample) - tp,
                        "precision": tp / len(sample) if sample else None})
    report["retention"] = {
        "is_excerpt": True, "total_lost_items": report["lost_items"],
        "retained_items": len(selected), "omitted_items": report["lost_items"] - len(selected),
        "full_report": "data/arena_hard/full-report/report.json",
        "note": "All aggregate counts cover the full run; items contains only the 20 hand-checked verdicts.",
    }
    report["items"] = selected
    report["audit"] = {"reviewer": "Codex manual source/text inspection; not independent human gold labels",
                       "precision_scope": "Correctness of the documented detector predicate, not precision of eval-fault attribution.",
                       "metrics": metrics, "sample_id_counts": dict(Counter(r["detector"] for r in checks)),
                       "sampling": "Deterministic strata: four distinct pairs per model for judge_unstable; eight distinct prompts for item_everyone_loses. No replacement of unfavorable cases. 18 unique prompts; not a prevalence-weighted random sample."}
    (out / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    note = ("**Reduced artifact:** aggregates cover all 3,000 observations; only the 20 audited verdicts "
            "are retained below. 1,806 other lost observations are omitted. Full CLI Markdown/JSON/HTML "
            "remain in gitignored `data/arena_hard/full-report/`. See [FINDINGS](../FINDINGS.md) "
            "for score semantics and precision limits. This file was reduced from the CLI output; "
            "source text in retained records is unchanged.\n\n")
    (out / "report.md").write_text(note + markdown(report), encoding="utf-8")
    (out / "provenance.json").write_text((source / "generic.manifest.json").read_text(), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    print("Retained 20 drill-down items, full aggregates, source pairs, and provenance.")


if __name__ == "__main__":
    main()
