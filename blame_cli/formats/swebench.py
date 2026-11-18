"""Read SWE-bench harness output: one run directory or a directory of run directories.

Written from a reading of SWE-bench/SWE-bench at commit
02e7a74ffd0b707aab73d203fe87bdc7c76afc8e and unverified against real harness output.
The layout is <run_id>/<model_dir>/<instance_id>/{report.json, patch.diff,
run_instance.log} with the run summary at <run_id>/results.json.
"""

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from ..model import Record, validate
from . import redact


PROBE = ("SWE-bench (a report.json two or three levels below the directory whose single key is the name "
         "of the directory holding it, with a resolved value)")
GROUPS = ("FAIL_TO_PASS", "PASS_TO_PASS", "FAIL_TO_FAIL", "PASS_TO_FAIL")
NAMES = 20
LOG_LINES = 5


def _entry(file: Path) -> dict | None:
    """The instance's entry in a report.json, or None when the file is not such a report."""
    try:
        data = json.loads(file.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    if not isinstance(data, dict) or list(data) != [file.parent.name]:
        return None
    entry = data[file.parent.name]
    return entry if isinstance(entry, dict) and "resolved" in entry else None


def _is_run(path: Path) -> bool:
    return (path / "results.json").is_file() or any(_entry(file) for file in sorted(path.glob("*/*/report.json")))


def _runs(path: Path) -> list[Path]:
    if _is_run(path):
        return [path]
    return [child for child in sorted(path.iterdir()) if child.is_dir() and _is_run(child)]


def detect(path: Path) -> bool:
    return path.is_dir() and any(_entry(file) for pattern in ("*/*/report.json", "*/*/*/report.json")
                                 for file in sorted(path.glob(pattern)))


def _yes(value) -> str:
    return "true" if value is True else "false" if value is False else "not recorded"


def _reasoning(entry: dict) -> str:
    lines = [f"patch_exists: {_yes(entry.get('patch_exists'))}. "
             f"patch_successfully_applied: {_yes(entry.get('patch_successfully_applied'))}."]
    if entry.get("patch_successfully_applied") is False:
        lines.append("The harness found no parseable test output.")
    status = entry.get("tests_status")
    for group in GROUPS if isinstance(status, dict) else ():
        tests = status.get(group)
        if not isinstance(tests, dict):
            continue
        passed, failed = ([name for name in tests.get(key) or () if isinstance(name, str)] for key in ("success", "failure"))
        line = f"{group}: {len(passed)} passed, {len(failed)} failed"
        if failed:
            more = f", and {len(failed) - NAMES} more" if len(failed) > NAMES else ""
            line += " (" + ", ".join(failed[:NAMES]) + more + ")"
        lines.append(redact(line) + ".")
    return "\n".join(lines)


def _patch(instance: Path, job: str) -> tuple[str, str | None, bool]:
    """run_id, output and whether patch.diff was read."""
    try:
        raw = (instance / "patch.diff").read_bytes()
    except OSError:
        return job, None, False
    return "patch:" + hashlib.sha256(raw).hexdigest()[:12], redact(raw.decode("utf-8", errors="replace")), True


def _record(job: str, model: str, task: str, **fields) -> Record:
    return validate(Record(task_id=task, model=model, instruction=None, rubric_item_id="resolved",
                           rubric_item_text=None, judge_run=None, job_id=job,
                           role="reference" if model == "gold" else "candidate", **fields))


def _graded(entry: dict, instance: Path, job: str, run_id: str, output: str | None) -> Record:
    if not isinstance(entry["resolved"], bool):
        raise ValueError("resolved must be true or false")
    reason = entry.get("infra_failure_reason")
    flagged = entry.get("infra_failure") is True
    error = kind = None
    if flagged or reason:
        text = redact(reason) if isinstance(reason, str) and reason.strip() else "no reason recorded"
        error, kind = f"SWE-bench log pattern: {text}", "infra" if flagged else "unknown"
    return _record(job, instance.parent.name, instance.name, run_id=run_id, output=output,
                   score=1.0 if entry["resolved"] else 0.0, judge_reasoning=_reasoning(entry),
                   error=error, error_kind=kind)


def _ungraded(instance: Path, job: str, run_id: str, output: str | None) -> Record:
    try:
        lines = (instance / "run_instance.log").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    tail = "\n".join(line for line in lines[-LOG_LINES:]).strip()
    return _record(job, instance.parent.name, instance.name, run_id=run_id, output=output, score=None,
                   judge_reasoning="", error=redact(tail) if tail else "no report.json", error_kind="unknown")


def _ids(summary: dict, key: str) -> list[str]:
    found = summary.get(key)
    return sorted({item for item in found if isinstance(item, str) and item and Path(item).name == item
                   and item not in (".", "..")}) if isinstance(found, list) else []


def _summary(run: Path, prefix: str, models: list[Path], seen: set, records: list, warnings: list) -> None:
    file = run / "results.json"
    if not file.is_file():
        warnings.append(f"{prefix}no results.json; empty patches and harness errors without an instance "
                        "directory are not visible.")
        return
    try:
        summary = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(summary, dict):
            raise ValueError
    except (OSError, ValueError):
        warnings.append(f"{prefix}results.json: unreadable result file skipped (not a UTF-8 JSON object).")
        return
    lost = 0
    for key in ("empty_patch_ids", "error_ids"):
        for task in _ids(summary, key):
            owners = [model for model in models if (model / task).is_dir()] or (models if len(models) == 1 else [])
            lost += not owners
            for model in owners:
                if (model.name, task) in seen:
                    continue
                seen.add((model.name, task))
                if key == "empty_patch_ids":
                    records.append(_record(run.name, model.name, task, run_id="patch:empty", output="", score=0.0,
                                           judge_reasoning="", error="empty patch", error_kind="agent"))
                else:
                    records.append(_record(run.name, model.name, task, run_id=run.name, output=None, score=None,
                                           judge_reasoning="", error="no report.json", error_kind="unknown"))
    if lost:
        warnings.append(f"{prefix}results.json: {lost} empty-patch or error ids could not be tied to a model "
                        "directory and were skipped.")
    incomplete = summary.get("incomplete_ids")
    if isinstance(incomplete, list) and incomplete:
        warnings.append(f"{prefix}results.json: {len(incomplete)} instances have no prediction (incomplete_ids) "
                        "and are not in the report.")


def load(path: Path) -> tuple[list[Record], list[str]]:
    root = path.resolve()
    records, warnings = [], []
    for run in _runs(root):
        prefix = "" if run == root else run.name + "/"
        models = [child for child in sorted(run.iterdir()) if child.is_dir()]
        seen = set()
        for instance in (child for model in models for child in sorted(model.iterdir()) if child.is_dir()):
            where = f"{prefix}{instance.parent.name}/{instance.name}"
            report = instance / "report.json"
            entry = _entry(report)
            seen.add((instance.parent.name, instance.name))
            if report.is_file() and entry is None:
                warnings.append(f"{where}/report.json: unreadable result file skipped "
                                "(not a JSON report for this instance).")
                continue
            run_id, output, found = _patch(instance, run.name)
            if not found:
                warnings.append(f"{where}: no patch.diff; the run id {run.name} stands in for the patch.")
            try:
                records.append(_graded(entry, instance, run.name, run_id, output) if entry
                               else _ungraded(instance, run.name, run_id, output))
            except ValueError as exc:
                raise ValueError(f"{where}/report.json: {exc}") from exc
        _summary(run, prefix, models, seen, records, warnings)
    if not records:
        raise ValueError("no readable SWE-bench result found")
    return records, warnings


def merge(records: list[Record]) -> tuple[list[Record], list[str]]:
    """Number re-gradings: one instance, model and patch graded under several runs gets judge_run 1..n."""
    jobs: dict[tuple, set] = {}
    for record in records:
        jobs.setdefault(record.attempt_key, set()).add(record.job_id)
    order = {key: {job: number for number, job in enumerate(sorted(found), 1)}
             for key, found in jobs.items() if len(found) > 1}
    return [replace(record, judge_run=order[record.attempt_key][record.job_id])
            if record.attempt_key in order else record for record in records], []
