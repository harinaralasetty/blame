"""Render the same report data to JSON, Markdown, and escaped static HTML."""

from collections import Counter, defaultdict
import html
import json
from pathlib import Path

from .detectors import build_index, reference_attempts, triage
from .model import CLASSES, LABELS, system_name


MISSING = "not available in this format"


def _system(record: dict) -> str:
    return system_name(record.get("agent"), record["model"])


def _lost(items) -> dict:
    scored = [v for v in items if v["record"]["score"] is not None]
    return {"lost_items": len(scored), "lost_points": round(sum(1 - v["record"]["score"] for v in scored), 6),
            "ungraded_items": len(items) - len(scored)}


def _reference_text(passed: int, used: int, supplied: int) -> str:
    """The reference attempts the reference detectors used, and how many they left out."""
    if not supplied:
        return "no reference run supplied"
    left = f"; {supplied - used} left out (harness error, not graded or another task version)" if supplied > used else ""
    return (f"passed {passed} of {used} attempts" if used else "no usable reference attempt") + left


def _by_task(records, verdicts) -> list[dict]:
    index = build_index(records)
    by_task = defaultdict(list)
    for record in records:
        by_task[record.task_id].append(record)
    failed = defaultdict(list)
    for verdict in verdicts:
        failed[verdict["record"]["task_id"]].append(verdict)
    rows = []
    for task, items in failed.items():
        candidates = [r for r in by_task[task] if r.role == "candidate"]
        headlines = Counter(v["label"] for v in items)
        # The most frequent headline; ties go to the higher precedence.
        primary = max(CLASSES, key=lambda label: (headlines[label], -CLASSES.index(label)))
        findings = Counter(f["label"] for v in items for f in (v["matches"] or [v]))
        info = LABELS[CLASSES.index(primary)]
        rows.append({
            "task_id": task,
            "systems_attempted": len({r.system for r in candidates}),
            "systems_failed": len({r.system for r in candidates if r.score is not None and r.score < 1}),
            "reference": _reference_text(*reference_attempts(by_task[task], index)),
            "labels": {label: findings[label] for label in CLASSES if findings[label]},
            "primary_label": primary, "category": info.category,
            "max_confidence": max(v["confidence"] for v in items if v["label"] == primary),
            "next_step": info.next_step,
        })
    return rows


def build_report(records, warnings=(), reasoner=None) -> dict:
    """Count candidate records only; reference records appear in by_task and in evidence."""
    verdicts = triage(records, reasoner)
    candidates = [r for r in records if r.role == "candidate"]
    scored = [r for r in candidates if r.score is not None]
    classes = [{"class": info.name, "category": info.category,
                **_lost([v for v in verdicts if v["label"] == info.name])} for info in LABELS]
    models = []
    for system in sorted({r.system for r in candidates}):
        selected = [v for v in verdicts if _system(v["record"]) == system]
        counts = Counter(v["label"] for v in selected)
        models.append({"model": system, "scored_items": sum(r.system == system for r in scored),
                       **_lost(selected), **{label: counts[label] for label in CLASSES}})
    ungraded = len(candidates) - len(scored)
    counting = "Each scored observation below 1 is a lost item, including repeated judges."
    if ungraded:
        counting += f" {ungraded} attempts were never graded and are listed as ungraded."
    return {"schema_version": 2, "scored_items": len(scored),
            "lost_items": sum(v["record"]["score"] is not None for v in verdicts),
            "lost_points": round(sum(1 - r.score for r in scored), 6),
            "ungraded_items": ungraded, "reference_items": len(records) - len(candidates),
            "counting": counting,
            "confidence_note": "Confidence values are fixed heuristic strengths, not calibrated probabilities.",
            "warnings": list(warnings), "by_class": classes, "by_model": models,
            "by_task": _by_task(records, verdicts), "items": verdicts}


def _md(value) -> str:
    return html.escape(str(value), quote=False).replace("|", "&#124;").replace("\n", "<br>").replace("\r", "")


def _score(value) -> str:
    return "not graded" if value is None else f"{value:g}"


def _field(record: dict, name: str):
    """A record field for display; None in a field the format may not carry gets a plain note."""
    value = record.get(name)
    return MISSING if value is None and name in ("instruction", "rubric_item_text", "output") else value


def _summary(report: dict) -> str:
    text = f"Scored observations: {report['scored_items']}. Lost items: {report['lost_items']}. Lost points: {report['lost_points']:g}."
    if report["ungraded_items"]:
        text += f" Ungraded attempts: {report['ungraded_items']}."
    if report["reference_items"]:
        text += f" Reference results (not counted): {report['reference_items']}."
    return text


def _tables(report: dict):
    ungraded = ["ungraded_items"] if report["ungraded_items"] else []
    return [
        ("By class", ["class", "category", "lost_items", "lost_points", *ungraded], report["by_class"]),
        ("By model", ["model", "scored_items", "lost_items", "lost_points", *ungraded, *CLASSES], report["by_model"]),
    ]


TASK_COLUMNS = ("task_id", "systems_attempted", "systems_failed", "reference", "primary_label",
                "category", "rule strength", "labels", "next_step")


def _task_cells(row: dict) -> dict:
    return {**row, "rule strength": f"{row['max_confidence']:.2f}",
            "labels": ", ".join(f"{label} {count}" for label, count in row["labels"].items())}


def markdown(report: dict) -> str:
    lines = ["# blame report", "", _summary(report),
             "", report["counting"], "", report["confidence_note"], ""]
    for title, columns, rows in _tables(report):
        lines.extend([f"## {title}", "", "| " + " | ".join(columns) + " |",
                      "| " + " | ".join("---" for _ in columns) + " |"])
        lines.extend("| " + " | ".join(_md(row[col]) for col in columns) + " |" for row in rows)
        lines.append("")
    if report["warnings"]:
        lines.extend(["## Input warnings", ""])
        lines.extend("- " + _md(w) for w in report["warnings"])
        lines.append("")
    if report["by_task"]:
        lines.extend(["## Failed tasks", "", "One row per task with a lost or ungraded attempt. "
                      "The label is the most frequent verdict on the task; `labels` counts every detector match.",
                      "", "| " + " | ".join(TASK_COLUMNS) + " |", "| " + " | ".join("---" for _ in TASK_COLUMNS) + " |"])
        lines.extend("| " + " | ".join(_md(cells[col]) for col in TASK_COLUMNS) + " |"
                     for cells in map(_task_cells, report["by_task"]))
        lines.append("")
    lines.extend(["## Lost item drill-down", ""])
    for item in report["items"]:
        record = item["record"]
        lines.extend([f"### {_md(record['task_id'])} / {_md(_system(record))} / {_md(record['rubric_item_id'])}", "",
                      f"Verdict: {item['label']}; rule strength: {item['confidence']:.2f}; score: {_score(record['score'])}; run: {_md(record['run_id'])}; judge_run: {record['judge_run']}.",
                      "", f"Record: {item['record_id']}", ""])
        for field in ("instruction", "rubric_item_text", "output", "judge_reasoning", "error"):
            lines.extend([f"{field}: <q>{_md(_field(record, field))}</q>", ""])
        for name, value in item["evidence"].items():
            lines.extend([f"- {_md(name)}: <q>{_md(json.dumps(value, ensure_ascii=False))}</q>"])
        lines.extend(["", "Detector matches: " + ", ".join(f["label"] for f in item["matches"]), ""])
    return "\n".join(lines)


def static_html(report: dict) -> str:
    esc = lambda x: html.escape(str(x), quote=True)
    parts = ['<!doctype html><html lang="en"><meta charset="utf-8">',
             '<meta name="viewport" content="width=device-width, initial-scale=1">',
             '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; style-src \'unsafe-inline\'">',
             '<title>blame report</title><style>body{font:16px system-ui;max-width:1200px;margin:2rem auto;padding:0 1rem;color:#182233;background:#fafaf8}table{border-collapse:collapse;display:block;overflow:auto}td,th{border:1px solid #bbb;padding:.5rem;text-align:left}th{background:#e8ece8}details{margin:1rem 0;border:1px solid #bbb;padding:1rem}summary{cursor:pointer;font-weight:600}pre{white-space:pre-wrap;overflow-wrap:anywhere}dt{font-weight:600;margin-top:.6rem}dd{margin-left:1rem;white-space:pre-wrap;overflow-wrap:anywhere}.muted{color:#53615a}</style><body><h1>blame report</h1>',
             f"<p>{esc(_summary(report))}</p>",
             f"<p class=muted>{esc(report['counting'])} {esc(report['confidence_note'])}</p>"]
    for title, columns, rows in _tables(report):
        parts.extend([f"<h2>{title}</h2><table><thead><tr>",
                      "".join(f"<th scope=col>{esc(col)}</th>" for col in columns), "</tr></thead><tbody>"])
        for row in rows:
            parts.append("<tr>" + "".join(f"<td>{esc(row[col])}</td>" for col in columns) + "</tr>")
        parts.append("</tbody></table>")
    if report["warnings"]:
        parts.append("<h2>Input warnings</h2><ul>" + "".join(f"<li>{esc(w)}</li>" for w in report["warnings"]) + "</ul>")
    if report["by_task"]:
        parts.append("<h2>Failed tasks</h2><p class=muted>One entry per task with a lost or ungraded attempt. "
                     "The label is the most frequent verdict on the task.</p><ul>")
        for cells in map(_task_cells, report["by_task"]):
            parts.append(f"<li><strong>{esc(cells['task_id'])}</strong>: {esc(cells['primary_label'])} "
                         f"({esc(cells['category'])}), rule strength {cells['rule strength']}. "
                         f"Systems with a failed check: {cells['systems_failed']} of {cells['systems_attempted']}. "
                         f"Reference: {esc(cells['reference'])}. All matches: {esc(cells['labels'])}. "
                         f"Next step: {esc(cells['next_step'])}</li>")
        parts.append("</ul>")
    parts.append("<h2>Lost item drill-down</h2>")
    for item in report["items"]:
        record = item["record"]
        title = f"{record['task_id']} / {_system(record)} / {record['rubric_item_id']} / judge {record['judge_run']}: {item['label']}"
        parts.append(f"<details id=\"{item['record_id']}\"><summary>{esc(title)}</summary><dl>")
        for name, value in {"rule strength": item["confidence"], **{key: _field(record, key) for key in record}}.items():
            parts.append(f"<dt>{esc(name)}</dt><dd>{esc(value)}</dd>")
        parts.append("</dl><h3>Evidence</h3><pre>" + esc(json.dumps(item["evidence"], indent=2, ensure_ascii=False)) + "</pre>")
        parts.append("<h3>All detector matches</h3><pre>" + esc(json.dumps(item["matches"], indent=2, ensure_ascii=False)) + "</pre></details>")
    parts.append("</body></html>\n")
    return "\n".join(parts)


def write_report(report: dict, directory: str) -> None:
    out = Path(directory)
    out.mkdir(parents=True, exist_ok=True)
    for filename, content in (
        ("report.json", json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False) + "\n"),
        ("report.md", markdown(report)), ("report.html", static_html(report)),
    ):
        (out / filename).write_text(content, encoding="utf-8")
