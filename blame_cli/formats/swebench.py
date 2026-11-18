"""Read SWE-bench harness output: one run directory or a directory of run directories.

Written from a reading of SWE-bench/SWE-bench at commit
02e7a74ffd0b707aab73d203fe87bdc7c76afc8e and checked against the output of swebench 5.0.2
(fixtures/real-swebench). The harness writes, under the directory it is run from,
logs/run_evaluation/<run_id>/{run.json, <model_dir>/<instance_id>/{report.json, patch.diff,
run_instance.log}} and one summary per model at <model_dir>.<run_id>.json beside logs/.
A results.json inside the run directory is read as a summary too. The working directory,
logs/, run_evaluation/ or one run directory may be given.
"""

from dataclasses import replace
import hashlib
import json
from pathlib import Path

from ..model import Record, validate
from ._text import ERROR_CHARS, OUTPUT_CHARS, clip, redact


PROBE = ("SWE-bench (a report.json two or three levels below the directory whose single key is the name "
         "of the directory holding it, with a true or false resolved value; or a run directory holding "
         "run.json and a run_instance.log two levels down; logs/run_evaluation is looked into)")
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
    return entry if isinstance(entry, dict) and isinstance(entry.get("resolved"), bool) else None


def _has_report(path: Path) -> bool:
    """Whether path is a run directory: a report two levels down, or the harness's run.json and an instance log."""
    return any(_entry(file) for file in sorted(path.glob("*/*/report.json"))) or (
        (path / "run.json").is_file() and any(path.glob("*/*/run_instance.log")))


def _base(path: Path) -> Path:
    """The directory of run directories when path is the harness's working directory or its logs/."""
    for inner in (path / "logs" / "run_evaluation", path / "run_evaluation"):
        if inner.is_dir() and (inner.parent.name == "logs"):
            return inner
    return path


def _runs(path: Path) -> list[Path]:
    """The run directories at or under path.

    The layout decides: a directory with a report two levels down is a run. A results.json
    marks a run only where no report says otherwise, so a stray one cannot hide a run.
    """
    if _has_report(path):
        return [path]
    children = [child for child in sorted(path.iterdir()) if child.is_dir()]
    summary = [child for child in children if (child / "results.json").is_file()]
    if any(_has_report(child) for child in children):
        return [child for child in children if child in summary or _has_report(child)]
    return [path] if (path / "results.json").is_file() else summary


def detect(path: Path) -> bool:
    if not path.is_dir():
        return False
    path = _base(path)
    return _has_report(path) or any(_has_report(child) for child in sorted(path.iterdir()) if child.is_dir())


def _yes(value) -> str:
    return "true" if value is True else "false" if value is False else "not recorded"


def _reasoning(entry: dict) -> tuple[str, list[str]]:
    """The grader text, and the tests_status groups whose values are not lists of names."""
    lines = [f"patch_exists: {_yes(entry.get('patch_exists'))}. "
             f"patch_successfully_applied: {_yes(entry.get('patch_successfully_applied'))}."]
    if entry.get("patch_successfully_applied") is False:
        lines.append("The harness found no parseable test output.")
    status = entry.get("tests_status")
    bad = []
    for group in GROUPS if isinstance(status, dict) else ():
        tests = status.get(group)
        if tests is None:
            continue
        found = [tests.get(key, []) for key in ("success", "failure")] if isinstance(tests, dict) else [None]
        if any(not isinstance(names, list) or any(not isinstance(name, str) for name in names) for names in found):
            bad.append(group)
            continue
        passed, failed = found
        line = f"{group}: {len(passed)} passed, {len(failed)} failed"
        if failed:
            more = f", and {len(failed) - NAMES} more" if len(failed) > NAMES else ""
            line += " (" + ", ".join(failed[:NAMES]) + more + ")"
        lines.append(redact(clip(line, ERROR_CHARS)) + ".")
    return "\n".join(lines), bad


def _patch(instance: Path, job: str) -> tuple[str, str | None, bool]:
    """run_id, output and whether patch.diff was read. A patch of only white space is the empty patch."""
    try:
        raw = (instance / "patch.diff").read_bytes()
    except OSError:
        return job, None, False
    if not raw.strip():
        return "patch:empty", "", True
    text = raw.decode("utf-8", errors="replace")
    return "patch:" + hashlib.sha256(raw).hexdigest()[:12], redact(clip(text, OUTPUT_CHARS)), True


def _record(job: str, model: str, task: str, **fields) -> Record:
    return validate(Record(task_id=task, model=model, instruction=None, rubric_item_id="resolved",
                           rubric_item_text=None, judge_run=None, job_id=job,
                           role="reference" if model == "gold" else "candidate", **fields))


def _empty(job: str, model: str, task: str, reasoning: str = "") -> Record:
    """An empty patch: the harness counts it as submitted and not resolved, and it is the agent's."""
    return _record(job, model, task, run_id="patch:empty", output="", score=0.0, judge_reasoning=reasoning,
                   error="empty patch", error_kind="agent")


def _graded(entry: dict, instance: Path, job: str, run_id: str, output: str | None, reasoning: str) -> Record:
    reason = entry.get("infra_failure_reason")
    flagged = entry.get("infra_failure") is True
    error = kind = None
    if flagged or reason:
        text = redact(clip(reason, ERROR_CHARS)) if isinstance(reason, str) and reason.strip() else "no reason recorded"
        error, kind = f"SWE-bench log pattern: {text}", "infra" if flagged else "unknown"
    elif output == "" and not entry["resolved"]:
        return _empty(job, instance.parent.name, instance.name, reasoning)
    return _record(job, instance.parent.name, instance.name, run_id=run_id, output=output,
                   score=1.0 if entry["resolved"] else 0.0, judge_reasoning=reasoning, error=error, error_kind=kind)


def _ungraded(instance: Path, job: str, run_id: str, output: str | None) -> Record:
    if output == "":
        return _empty(job, instance.parent.name, instance.name)
    try:
        lines = (instance / "run_instance.log").read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        lines = []
    tail = "\n".join(line for line in lines[-LOG_LINES:]).strip()
    missing = "report.json could not be read" if (instance / "report.json").is_file() else "no report.json"
    return _record(job, instance.parent.name, instance.name, run_id=run_id, output=output, score=None,
                   judge_reasoning="", error=redact(clip(tail, ERROR_CHARS)) if tail else missing, error_kind="unknown")


def _instance(instance: Path, job: str, entry: dict | None, where: str, warnings: list) -> Record:
    run_id, output, found = _patch(instance, job)
    if not found:
        warnings.append(f"{where}: no patch.diff; the run id {job} stands in for the patch.")
    if entry is None:
        return _ungraded(instance, job, run_id, output)
    reasoning, bad = _reasoning(entry)
    warnings.extend(f"{where}/report.json: tests_status {group} is not lists of test names and was ignored."
                    for group in bad)
    return _graded(entry, instance, job, run_id, output, reasoning)


def _ids(summary: dict, key: str) -> list[str]:
    found = summary.get(key)
    return sorted({item for item in found if isinstance(item, str) and item and Path(item).name == item
                   and item not in (".", "..")}) if isinstance(found, list) else []


def _summaries(run: Path, models: list[Path]) -> list[tuple[str, Path, list[Path]]]:
    """(name, file, model directories it covers) for each run summary found.

    results.json in the run directory covers every model. The harness itself writes
    <model_dir>.<run_id>.json in its working directory, beside logs/run_evaluation.
    """
    found = []
    if (run / "results.json").is_file():
        found.append(("results.json", run / "results.json", models))
    if run.parent.name == "run_evaluation" and run.parent.parent.name == "logs":
        tail = f".{run.name}.json"
        for file in sorted(run.parent.parent.parent.glob("*" + tail)):
            if file.is_file() and file.name != tail:
                found.append((file.name, file, [run / file.name[:-len(tail)]]))
    return found


def _summary(run: Path, prefix: str, models: list[Path], seen: set, records: list, warnings: list) -> None:
    files = _summaries(run, models)
    if not files:
        beside = run.parent.name == "run_evaluation" and run.parent.parent.name == "logs"
        warnings.append(f"{prefix}results.json: not present, " +
                        (f"and no <model>.{run.name}.json beside logs/, " if beside else "") +
                        "so empty patches and harness errors without an instance directory are not visible.")
    for name, file, covered in files:
        _read_summary(run, prefix, f"{prefix}{name}", file, covered, seen, records, warnings)


def _read_summary(run: Path, prefix: str, name: str, file: Path, models: list[Path], seen: set, records: list,
                  warnings: list) -> None:
    try:
        summary = json.loads(file.read_text(encoding="utf-8"))
        if not isinstance(summary, dict):
            raise ValueError
    except (OSError, ValueError):
        warnings.append(f"{name}: unreadable result file skipped (not a UTF-8 JSON object).")
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
                    records.append(_empty(run.name, model.name, task))
                elif (model / task).is_dir():   # its report.json was skipped as unreadable
                    records.append(_instance(model / task, run.name, None, f"{prefix}{model.name}/{task}", warnings))
                else:
                    records.append(_record(run.name, model.name, task, run_id=run.name, output=None, score=None,
                                           judge_reasoning="", error="no report.json", error_kind="unknown"))
    if lost:
        warnings.append(f"{name}: {lost} empty-patch or error ids could not be tied to a model "
                        "directory and were skipped.")
    incomplete = summary.get("incomplete_ids")
    if isinstance(incomplete, list) and incomplete:
        warnings.append(f"{name}: {len(incomplete)} instances have no prediction (incomplete_ids) "
                        "and are not in the report.")


def load(path: Path) -> tuple[list[Record], list[str]]:
    root = _base(path.resolve())
    records, warnings = [], []
    runs = _runs(root)
    if root not in runs and (root / "results.json").is_file():
        warnings.append("results.json: not read; it sits beside the run directories, not inside one.")
    for run in runs:
        prefix = "" if run == root else run.name + "/"
        models = [child for child in sorted(run.iterdir()) if child.is_dir()]
        seen = set()
        for instance in (child for model in models for child in sorted(model.iterdir()) if child.is_dir()):
            where = f"{prefix}{instance.parent.name}/{instance.name}"
            report = instance / "report.json"
            entry = _entry(report)
            if report.is_file() and entry is None:
                # Not marked as seen: if results.json lists the instance as an error it is still reported.
                warnings.append(f"{where}/report.json: unreadable result file skipped "
                                "(not a JSON report for this instance with a true or false resolved value).")
                continue
            seen.add((instance.parent.name, instance.name))
            records.append(_instance(instance, run.name, entry, where, warnings))
        _summary(run, prefix, models, seen, records, warnings)
    if not records:
        raise ValueError("no readable SWE-bench result found" + (": " + " ".join(warnings) if warnings else ""))
    return records, warnings


def _names(paths: list[Path]) -> dict[Path, str]:
    """A job name per run directory: its own name, plus as many parent names as it takes to tell two apart."""
    names = {}
    for path in paths:
        depth = 1
        while depth < len(path.parts) and any(other != path and other.parts[-depth:] == path.parts[-depth:]
                                              for other in paths):
            depth += 1
        names[path] = "/".join(path.parts[-depth:])
    return names


def merge(loaded: list[tuple[Path, list[Record]]]) -> tuple[list[Record], list[str]]:
    """Give each run directory its own job name and number re-gradings.

    A run is its resolved directory, not its name: a run supplied twice is read once, and
    two runs with one name are kept apart. One instance, model and patch graded under
    several runs gets judge_run 1..n in job-name order.
    """
    by_run: dict[Path, list[Record]] = {}
    warnings = []
    for source, records in loaded:
        root = _base(source.resolve())
        here = {run.name: run.resolve() for run in _runs(root)}
        fresh: dict[str, list[Record]] = {}
        for record in records:
            fresh.setdefault(record.job_id, []).append(record)
        for run, group in ((here[job], group) for job, group in fresh.items()):
            if run in by_run:
                warnings.append(f"SWE-bench run {run.name} was supplied more than once; it is read once.")
            else:
                by_run[run] = group
    names = _names(list(by_run))
    renamed = []
    for run, group in by_run.items():
        for record in group:
            # A run id that stands in for a missing patch follows the job name.
            run_id = names[run] if record.run_id == record.job_id else record.run_id
            renamed.append(replace(record, job_id=names[run], run_id=run_id))
    jobs: dict[tuple, set] = {}
    for record in renamed:
        jobs.setdefault(record.attempt_key, set()).add(record.job_id)
    order = {key: {job: number for number, job in enumerate(sorted(found), 1)}
             for key, found in jobs.items() if len(found) > 1}
    return [replace(record, judge_run=order[record.attempt_key][record.job_id])
            if record.attempt_key in order else record for record in renamed], warnings
