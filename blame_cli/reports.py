"""Render the same report data to JSON, Markdown, and escaped static HTML."""

from collections import Counter
import html
import json
from pathlib import Path

from .detectors import triage
from .model import CLASSES


def build_report(records, warnings=(), reasoner=None) -> dict:
    verdicts = triage(records, reasoner)
    classes = []
    for label in CLASSES:
        selected = [v for v in verdicts if v["label"] == label]
        classes.append({"class": label, "lost_items": len(selected),
                        "lost_points": round(sum(1 - v["record"]["score"] for v in selected), 6)})
    models = []
    for model in sorted({r.model for r in records}):
        selected = [v for v in verdicts if v["record"]["model"] == model]
        counts = Counter(v["label"] for v in selected)
        models.append({"model": model, "scored_items": sum(r.model == model for r in records),
                       "lost_items": len(selected),
                       "lost_points": round(sum(1 - v["record"]["score"] for v in selected), 6),
                       **{label: counts[label] for label in CLASSES}})
    return {"schema_version": 1, "scored_items": len(records), "lost_items": len(verdicts),
            "lost_points": round(sum(1 - r.score for r in records), 6),
            "counting": "Each scored observation below 1 is a lost item, including repeated judges.",
            "confidence_note": "Confidence values are fixed heuristic strengths, not calibrated probabilities.",
            "warnings": list(warnings), "by_class": classes, "by_model": models,
            "items": verdicts}


def _md(value) -> str:
    return html.escape(str(value), quote=False).replace("|", "&#124;").replace("\n", "<br>").replace("\r", "")


def _tables(report: dict):
    return [
        ("By class", ["class", "lost_items", "lost_points"], report["by_class"]),
        ("By model", ["model", "scored_items", "lost_items", "lost_points", *CLASSES], report["by_model"]),
    ]


def markdown(report: dict) -> str:
    lines = ["# blame report", "", f"Scored observations: {report['scored_items']}. Lost items: {report['lost_items']}. Lost points: {report['lost_points']:g}.",
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
    lines.extend(["## Lost item drill-down", ""])
    for item in report["items"]:
        record = item["record"]
        lines.extend([f"### {_md(record['task_id'])} / {_md(record['model'])} / {_md(record['rubric_item_id'])}", "",
                      f"Verdict: {item['label']}; confidence: {item['confidence']:.2f}; score: {record['score']:g}; run: {_md(record['run_id'])}; judge_run: {record['judge_run']}.",
                      "", f"Record: {item['record_id']}", ""])
        for field in ("instruction", "rubric_item_text", "output", "judge_reasoning", "error"):
            lines.extend([f"{field}: <q>{_md(record[field])}</q>", ""])
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
             f"<p>Scored observations: {report['scored_items']}. Lost items: {report['lost_items']}. Lost points: {report['lost_points']:g}.</p>",
             f"<p class=muted>{esc(report['counting'])} {esc(report['confidence_note'])}</p>"]
    for title, columns, rows in _tables(report):
        parts.extend([f"<h2>{title}</h2><table><thead><tr>",
                      "".join(f"<th scope=col>{esc(col)}</th>" for col in columns), "</tr></thead><tbody>"])
        for row in rows:
            parts.append("<tr>" + "".join(f"<td>{esc(row[col])}</td>" for col in columns) + "</tr>")
        parts.append("</tbody></table>")
    if report["warnings"]:
        parts.append("<h2>Input warnings</h2><ul>" + "".join(f"<li>{esc(w)}</li>" for w in report["warnings"]) + "</ul>")
    parts.append("<h2>Lost item drill-down</h2>")
    for item in report["items"]:
        record = item["record"]
        title = f"{record['task_id']} / {record['model']} / {record['rubric_item_id']} / judge {record['judge_run']}: {item['label']}"
        parts.append(f"<details id=\"{item['record_id']}\"><summary>{esc(title)}</summary><dl>")
        for name, value in {"confidence": item["confidence"], **record}.items():
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
