"""The blame CLI entry point."""

import argparse
import json
import sys

from .inputs import load_inputs
from .labels import score_labels, write_labels
from .reports import build_report, write_report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="blame", description="Did the model fail, or did your eval?")
    commands = parser.add_subparsers(dest="command", required=True)
    report = commands.add_parser("report", help="write Markdown, JSON and static HTML")
    report.add_argument("inputs", nargs="+", metavar="IN")
    report.add_argument("--out", required=True, metavar="DIR")
    label = commands.add_parser("label", help="write a CSV with blank human labels")
    label.add_argument("inputs", nargs="+", metavar="IN")
    label.add_argument("--out", default="labels.csv", metavar="CSV")
    score = commands.add_parser("score", help="measure detector precision/recall against filled labels")
    score.add_argument("labels", metavar="labels.csv")
    args = parser.parse_args(argv)
    try:
        if args.command == "score":
            print(json.dumps(score_labels(args.labels), indent=2, allow_nan=False))
        else:
            records, warnings = load_inputs(args.inputs)
            result = build_report(records, warnings)
            if args.command == "report":
                write_report(result, args.out)
                print(f"Wrote {args.out}/report.md, report.json, report.html ({result['lost_items']} lost items)")
            else:
                write_labels(result, args.out)
                print(f"Wrote {args.out} ({result['lost_items']} rows; human_label is blank)")
            for warning in warnings:
                print(f"warning: {warning}", file=sys.stderr)
    except (OSError, ValueError) as exc:
        print(f"blame: {exc}", file=sys.stderr)
        return 2
    return 0
