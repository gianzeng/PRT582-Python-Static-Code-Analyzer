"""Human-readable and machine-readable report formatters."""

import json
from typing import Any

from .models import AnalysisReport, FileAnalysis


def _file_dict(result: FileAnalysis) -> dict[str, Any]:
    return {
        "path": result.path,
        "metrics": result.metrics,
        "findings": [finding.to_dict() for finding in sorted(result.findings, key=lambda item: (item.line, item.column, item.rule_id, item.message))],
    }


def format_json(report: AnalysisReport) -> str:
    """Serialize a report with stable ordering and indentation."""

    payload = {
        "config": {
            "complexity_threshold": report.config.complexity_threshold,
            "duplicate_min_statements": report.config.duplicate_min_statements,
            "fail_on": report.config.fail_on,
            "exclude": list(report.config.exclude),
        },
        "files": [_file_dict(result) for result in sorted(report.files, key=lambda item: item.path)],
        "findings": [finding.to_dict() for finding in report.findings],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def format_text(report: AnalysisReport) -> str:
    """Serialize a report for terminal users."""

    lines: list[str] = []
    for result in sorted(report.files, key=lambda item: item.path):
        lines.append(result.path)
        lines.append("  metrics:")
        for key in (
            "physical_lines",
            "code_lines",
            "comment_lines",
            "blank_lines",
            "ast_nodes",
            "functions",
            "classes",
            "imports",
            "max_nesting_depth",
            "module_complexity",
        ):
            if key in result.metrics:
                lines.append(f"    {key}: {result.metrics[key]}")
        details = result.metrics.get("functions_detail", [])
        if details:
            lines.append("    functions_detail:")
            for detail in details:
                lines.append(
                    f"      {detail['name']}:{detail['line']} complexity={detail['complexity']}"
                )
        for finding in sorted(result.findings, key=lambda item: (item.line, item.column, item.rule_id, item.message)):
            lines.append(
                f"  {finding.line}:{finding.column} {finding.rule_id} "
                f"[{finding.severity}] {finding.message}"
            )
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
