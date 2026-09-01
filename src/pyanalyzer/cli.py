"""Command-line interface for pyanalyzer."""

import argparse
import sys

from .engine import analyze_paths
from .formatters import format_json, format_text
from .models import AnalysisConfig, InputError


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be an integer") from exc
    if parsed < 1:
        raise argparse.ArgumentTypeError("must be greater than zero")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Analyze Python source without executing it.")
    parser.add_argument("inputs", nargs="+", help="Python files or directories")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    parser.add_argument("--complexity-threshold", type=_positive_int, default=10)
    parser.add_argument("--duplicate-min-statements", type=_positive_int, default=3)
    parser.add_argument("--fail-on", choices=("none", "info", "warning", "error"), default="error")
    return parser


def _exit_status(report: object, fail_on: str) -> int:
    if fail_on == "none":
        return 0
    rank = {"info": 1, "warning": 2, "error": 3}
    threshold = rank[fail_on]
    return 1 if any(rank[finding.severity] >= threshold for finding in report.findings) else 0


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = AnalysisConfig(
        complexity_threshold=args.complexity_threshold,
        duplicate_min_statements=args.duplicate_min_statements,
        fail_on=args.fail_on,
    )
    try:
        report = analyze_paths(args.inputs, config)
    except InputError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    output = format_json(report) if args.format == "json" else format_text(report)
    print(output, end="")
    return _exit_status(report, args.fail_on)
