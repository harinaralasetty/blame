"""Read generic JSONL and the documented Inspect v2 text JSON subset."""

import json
from pathlib import Path
from typing import Iterable

from .model import Record


def _text(content) -> str:
    if isinstance(content, str):
        result = content
    elif isinstance(content, list):
        if any(not isinstance(p, dict) or p.get("type") != "text"
               or not isinstance(p.get("text"), str) for p in content):
            raise ValueError("only text content is supported; export multimodal data to generic JSONL")
        result = "\n".join(p["text"] for p in content)
    else:
        raise ValueError("text content must be a string or list of text blocks")
    if "attachment://" in result:
        raise ValueError("unresolved Inspect attachment; resolve it before importing")
    return result


def _score(value) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, str) and value in ("C", "I"):
        return {"C": 1.0, "I": 0.0}[value]
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return value  # Record validates bounds and finiteness.
    raise ValueError(f"unsupported Inspect score {value!r}; use numeric [0,1], bool, C or I")


def _object(value, name: str) -> dict:
    if not isinstance(value, dict):
        raise ValueError(f"{name} must be an object")
    return value


def inspect_records(log: dict) -> tuple[list[Record], list[str]]:
    if log.get("version") != 2:
        raise ValueError("only Inspect JSON log version 2 is supported")
    status = log.get("status")
    if status not in ("success", "error", "cancelled", "started"):
        raise ValueError("unknown or missing Inspect status")
    spec = _object(log.get("eval"), "eval")
    for field in ("task", "model", "run_id"):
        if not isinstance(spec.get(field), str) or not spec[field].strip():
            raise ValueError(f"eval.{field} must be a nonempty string")
    samples = log.get("samples")
    if not isinstance(samples, list):
        raise ValueError("Inspect samples must be a list (header-only logs cannot be triaged)")
    warnings = []
    if status != "success":
        error = log.get("error") or {}
        warnings.append(f"Incomplete Inspect log: status={status}, error={error.get('message', '')!r}; only scored samples are included.")
    records = []
    for sample in samples:
        sample = _object(sample, "sample")
        sid = sample.get("id")
        if type(sid) not in (str, int):
            raise ValueError("sample.id must be a string or integer")
        epoch = sample.get("epoch", 1)
        if type(epoch) is not int or epoch < 1:
            raise ValueError("sample.epoch must be a positive integer")
        if sample.get("invalidation"):
            raise ValueError(f"sample {sid!r} is invalidated; export selected valid scores explicitly")
        scores = sample.get("scores")
        if not scores:
            warnings.append(f"Sample {sid!r} has no scores; omitted without inventing a lost point.")
            continue
        scores = _object(scores, "sample.scores")
        sample_input = sample.get("input")
        if isinstance(sample_input, list):
            instruction = "\n".join(_text(_object(m, "input message").get("content")) for m in sample_input)
        else:
            instruction = _text(sample_input)
        output = _object(sample.get("output") or {}, "sample.output")
        choices = output.get("choices", [])
        if not isinstance(choices, list):
            raise ValueError("output.choices must be a list")
        choice_text = ""
        for index, choice in enumerate(choices):
            message = _object(_object(choice, "choice").get("message"), "choice.message")
            text = _text(message.get("content", ""))
            if not text.strip() and message.get("tool_calls"):
                raise ValueError("tool-only outputs require an explicit generic text export")
            if index == 0:
                choice_text = text
        if isinstance(output.get("completion"), str):
            completion = _text(output["completion"])
        else:
            completion = choice_text
        error = sample.get("error")
        if error is not None:
            error = _object(error, "sample.error").get("message")
        smeta = _object(sample.get("metadata") or {}, "sample.metadata")
        for scorer, score in scores.items():
            score = _object(score, "score")
            meta = _object(score.get("metadata") or {}, "score.metadata")
            value = score.get("value")
            dimensions = value.items() if isinstance(value, dict) else [(None, value)]
            for dimension, scalar in dimensions:
                item_id = scorer if dimension is None else f"{scorer}/{dimension}"
                rubric = meta.get("rubric_item_text") if dimension is None else (
                    _object(meta.get("rubric_items") or {}, "metadata.rubric_items").get(dimension))
                if rubric is None:
                    rubric = f"Scorer: {item_id} (rubric text unavailable)"
                    warnings.append(f"Sample {sid!r}, {item_id}: no rubric text; unstated requirement detector abstains.")
                records.append(Record.from_dict({
                    "task_id": f"{spec['task']}:{sid}", "model": spec["model"],
                    "run_id": f"{spec['run_id']}/epoch-{epoch}",
                    "instruction": instruction, "rubric_item_id": item_id,
                    "rubric_item_text": rubric, "output": completion, "score": _score(scalar),
                    "judge_reasoning": score.get("explanation") or "",
                    "judge_run": meta.get("judge_run", smeta.get("judge_run")), "error": error,
                }))
    return records, warnings


def load_inputs(paths: Iterable[str]) -> tuple[list[Record], list[str]]:
    records = []
    warnings = []
    seen = set()
    judges = {}
    for path in paths:
        file = Path(path)
        if file.suffix == ".eval":
            raise ValueError(f"{path}: binary .eval files are unsupported; use Inspect text JSON")
        content = file.read_text(encoding="utf-8")
        try:
            try:
                whole = json.loads(content)
            except json.JSONDecodeError:
                whole = None
            # Generic fields win over unknown extras, even Inspect-shaped extras.
            generic = isinstance(whole, dict) and "task_id" in whole
            if isinstance(whole, dict) and not generic and ("eval" in whole or "samples" in whole):
                loaded, notes = inspect_records(whole)
                warnings.extend(f"{path}: {note}" for note in notes)
            else:
                loaded = []
                for number, line in enumerate(content.split("\n"), 1):
                    if not line.strip():
                        continue
                    try:
                        loaded.append(Record.from_dict(json.loads(line)))
                    except (ValueError, TypeError) as exc:
                        raise ValueError(f"line {number}: {exc}") from exc
            for record in loaded:
                if record.record_id in seen:
                    warnings.append(f"{path}: duplicate record {record.record_id[:12]} ignored.")
                    continue
                if record.judge_run is not None:
                    key = record.judge_key + (record.judge_run,)
                    if key in judges and judges[key] != record.score:
                        raise ValueError("conflicting scores for the same output and judge_run")
                    judges[key] = record.score
                records.append(record)
                seen.add(record.record_id)
        except (ValueError, TypeError, AttributeError, KeyError) as exc:
            raise ValueError(f"{path}: {exc}") from exc
    if not records:
        raise ValueError("no scored records found")
    return records, warnings
