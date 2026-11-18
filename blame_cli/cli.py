"""The blame CLI entry point."""

import argparse
import json
import sys

from .formats import FORMATS
from .inputs import load_inputs
from .labels import score_labels, write_labels
from .reports import build_report, write_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="blame", description="Did the model fail, or did your eval?")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("report", help="write Markdown, JSON and static HTML")
    report.add_argument("inputs", nargs="+", metavar="IN")
    report.add_argument("--out", required=True, metavar="DIR")
    formats = {"choices": ("auto", *sorted(FORMATS)), "default": "auto",
               "help": "input format of every IN (default: auto, detected per input); "
                       "harbor is unverified against real harness output"}
    report.add_argument("--format", **formats)
    label = commands.add_parser("label", help="write a CSV with blank human labels")
    label.add_argument("inputs", nargs="+", metavar="IN")
    label.add_argument("--out", default="labels.csv", metavar="CSV")
    label.add_argument("--format", **formats)
    score = commands.add_parser("score", help="measure detector precision/recall against filled labels")
    score.add_argument("labels", metavar="labels.csv")
    args = parser.parse_args(argv)
    try:
        if args.command == "score":
            print(json.dumps(score_labels(args.labels), indent=2, allow_nan=False))
        else:
            records, warnings = load_inputs(args.inputs, args.format)
            result = build_report(records, warnings)
            if args.command == "report":
                write_report(result, args.out)
                ungraded = f", {result['ungraded_items']} ungraded" if result["ungraded_items"] else ""
                print(f"Wrote {args.out}/report.md, report.json, report.html ({result['lost_items']} lost items{ungraded})")
            else:
                write_labels(result, args.out)
                print(f"Wrote {args.out} ({len(result['items'])} rows; human_label is blank)")
            for warning in warnings:
                print(f"warning: {warning}", file=sys.stderr)
    except (OSError, ValueError) as exc:
        print(f"blame: {exc}", file=sys.stderr)
        return 2
    return 0
