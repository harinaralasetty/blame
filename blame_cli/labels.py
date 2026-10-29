"""Human labeling and unweighted one-vs-rest precision/recall."""

import csv
import json
from pathlib import Path
import sys

from .model import CLASSES


CSV_FIELDS = (
    "record_id", "task_id", "model", "run_id", "rubric_item_id", "judge_run",
    "instruction", "rubric_item_text", "output", "score", "judge_reasoning",
    "predicted_label", "detector_labels", "confidence", "evidence", "human_label",
    "original_record_json",
)


def _spreadsheet_cell(value):
    """Escape formula prefixes, including those hidden behind whitespace."""
    if isinstance(value, str) and (value.startswith(("\t", "\r", "\n"))
                                  or value.lstrip().startswith(("=", "+", "-", "@"))):
        return "'" + value
    return value


def write_labels(report: dict, path: str) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for item in report["items"]:
            record = item["record"]
            row = {
                **{key: record[key] for key in CSV_FIELDS if key in record},
                "record_id": item["record_id"], "predicted_label": item["label"],
                "detector_labels": "|".join(match["label"] for match in item["matches"]),
                "confidence": item["confidence"],
                "evidence": json.dumps(item["evidence"], ensure_ascii=False), "human_label": "",
                # JSON starts with '{', so original text stays inert in spreadsheets.
                "original_record_json": json.dumps(record, ensure_ascii=False),
            }
            writer.writerow({key: _spreadsheet_cell(value) for key, value in row.items()})


def _metrics(rows: list[dict], detectors: bool) -> dict:
    result = {}
    for label in CLASSES:
        tp = fp = fn = 0
        for row in rows:
            predicted = (label in row["detectors"] if detectors and label != "genuine_failure"
                         else row["predicted_label"] == label)
            actual = row["human_label"] == label
            tp += predicted and actual
            fp += predicted and not actual
            fn += not predicted and actual
        result[label] = {
            "tp": tp, "fp": fp, "fn": fn, "support": tp + fn,
            "precision": tp / (tp + fp) if tp + fp else None,
            "recall": tp / (tp + fn) if tp + fn else None,
        }
    return result


def _read_labels(reader: csv.DictReader) -> tuple[list[dict], int]:
    rows = []
    skipped = 0
    seen = set()
    required = {"record_id", "predicted_label", "detector_labels", "human_label"}
    if not required <= set(reader.fieldnames or ()):
        raise ValueError("CSV must contain " + ", ".join(sorted(required)))
    for number, row in enumerate(reader, 2):
        if None in row or any(row.get(key) is None for key in required):
            raise ValueError(f"CSV row {number}: malformed row")
        rid = row["record_id"].strip()
        if not rid or rid in seen:
            raise ValueError(f"CSV row {number}: empty or duplicate record_id")
        seen.add(rid)
        prediction = row["predicted_label"].strip()
        human = row["human_label"].strip()
        detectors = row["detector_labels"].split("|") if row["detector_labels"] else []
        if (prediction not in CLASSES or (human and human not in CLASSES)
                or any(label not in CLASSES[:-1] for label in detectors)
                or len(detectors) != len(set(detectors))):
            raise ValueError(f"CSV row {number}: invalid label; allowed human labels: {', '.join(CLASSES)}")
        expected = next((label for label in CLASSES[:-1] if label in detectors), "genuine_failure")
        if prediction != expected:
            raise ValueError(f"CSV row {number}: prediction disagrees with detector precedence")
        if not human:
            skipped += 1
            continue
        rows.append({"predicted_label": prediction, "human_label": human, "detectors": detectors})
    return rows, skipped


def score_labels(path: str) -> dict:
    # Accept any field that fits a Python string, as the writer does. Actual size
    # remains bounded by available memory, like JSONL input and report rendering.
    previous_limit = csv.field_size_limit(sys.maxsize)
    try:
        with Path(path).open(encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle, strict=True)
            try:
                rows, skipped = _read_labels(reader)
            except csv.Error as exc:
                raise ValueError(f"{path}: CSV line {reader.reader.line_num}: {exc}") from exc
    finally:
        csv.field_size_limit(previous_limit)
    return {"labeled_rows": len(rows), "unlabeled_rows": skipped,
            "note": "Blank human labels excluded; undefined precision/recall is null. Counts are per scored observation. Synthetic labels do not establish real precision.",
            "per_detector": _metrics(rows, True), "per_verdict": _metrics(rows, False)}
