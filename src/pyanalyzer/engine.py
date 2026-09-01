"""Coordinate parsing and individual analysis rules."""

import ast
from pathlib import Path
from typing import Iterable

from .models import AnalysisConfig, AnalysisReport, FileAnalysis, Finding, InputError
from .parser import parse_source, read_source
from .rules.complexity import analyze_complexity, calculate_complexity
from .rules.duplicates import analyze_duplicate_trees, analyze_duplicates
from .rules.metrics import calculate_metrics, empty_metrics
from .rules.naming import analyze_naming
from .rules.unused import analyze_unused


def _syntax_finding(filename: str, error: SyntaxError) -> Finding:
    line = error.lineno or 1
    column = error.offset - 1 if error.offset else 0
    return Finding(
        rule_id="P001",
        category="parsing",
        severity="error",
        file=filename,
        line=max(1, line),
        column=max(0, column),
        message=f"Syntax error: {error.msg}",
        evidence={"exception": type(error).__name__},
    )


def analyze_source(
    source: str,
    filename: str = "<string>",
    config: AnalysisConfig | None = None,
) -> FileAnalysis:
    """Analyze one source string through the public analysis seam."""

    config = config or AnalysisConfig()
    parsed = parse_source(source, filename)
    if parsed.tree is None:
        assert parsed.syntax_error is not None
        return FileAnalysis(
            path=filename,
            metrics=empty_metrics(source),
            findings=[_syntax_finding(filename, parsed.syntax_error)],
        )

    complexity = calculate_complexity(parsed.tree)
    metrics = calculate_metrics(parsed.tree, source, complexity.functions)
    metrics["module_complexity"] = complexity.module
    findings = analyze_complexity(parsed.tree, filename, config.complexity_threshold)
    findings.extend(analyze_naming(parsed.tree, filename))
    findings.extend(analyze_unused(parsed.tree, filename))
    findings.extend(analyze_duplicates(parsed.tree, filename, config.duplicate_min_statements))
    findings.sort(key=lambda item: (item.line, item.column, item.rule_id, item.message))
    return FileAnalysis(
        path=filename,
        metrics=metrics,
        findings=findings,
    )


def _collect_paths(inputs: Iterable[str]) -> list[Path]:
    paths: list[Path] = []
    for raw in inputs:
        path = Path(raw)
        if not path.exists():
            raise InputError(f"Input path does not exist: {raw}")
        if path.is_file():
            if path.suffix != ".py":
                raise InputError(f"Input file is not a Python file: {raw}")
            paths.append(path)
        elif path.is_dir():
            paths.extend(sorted(candidate for candidate in path.rglob("*.py") if candidate.is_file()))
    if not paths:
        raise InputError("No Python files were found in the requested inputs")
    return sorted(set(paths), key=lambda item: item.as_posix())


def analyze_paths(
    inputs: Iterable[str],
    config: AnalysisConfig | None = None,
) -> AnalysisReport:
    """Analyze Python files from file or directory paths."""

    config = config or AnalysisConfig()
    file_results: list[FileAnalysis] = []
    parsed_trees: list[tuple[ast.AST, str]] = []
    for path in _collect_paths(inputs):
        try:
            source = read_source(path)
        except (OSError, UnicodeError) as exc:
            raise InputError(f"Unable to read {path}: {exc}") from exc
        filename = path.as_posix()
        file_results.append(analyze_source(source, filename, config))
        parsed = parse_source(source, filename)
        if parsed.tree is not None:
            parsed_trees.append((parsed.tree, filename))
    duplicate_map = analyze_duplicate_trees(parsed_trees, config.duplicate_min_statements)
    for file_result in file_results:
        file_result.findings = [item for item in file_result.findings if item.category != "duplicate"]
        file_result.findings.extend(duplicate_map.get(file_result.path, []))
    return AnalysisReport(file_results, config)
