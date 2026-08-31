"""Source and AST metrics."""

import ast
from typing import Any


def _line_metrics(source: str) -> dict[str, int]:
    lines = source.splitlines()
    blank = sum(not line.strip() for line in lines)
    comments = sum(bool(line.strip()) and line.lstrip().startswith("#") for line in lines)
    return {
        "physical_lines": len(lines),
        "blank_lines": blank,
        "comment_lines": comments,
        "code_lines": len(lines) - blank - comments,
    }


class _NestingVisitor(ast.NodeVisitor):
    _NESTING_NODES = (
        ast.AsyncFor,
        ast.AsyncFunctionDef,
        ast.AsyncWith,
        ast.ClassDef,
        ast.For,
        ast.FunctionDef,
        ast.If,
        ast.Match,
        ast.Try,
        ast.While,
        ast.With,
    )

    def __init__(self) -> None:
        self.depth = 0
        self.maximum = 0

    def generic_visit(self, node: ast.AST) -> None:
        enters = isinstance(node, self._NESTING_NODES)
        if enters:
            self.depth += 1
            self.maximum = max(self.maximum, self.depth)
        super().generic_visit(node)
        if enters:
            self.depth -= 1


def _function_details(
    tree: ast.AST,
    complexities: dict[tuple[int, int], int] | None = None,
) -> list[dict[str, Any]]:
    details: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            details.append(
                {
                    "name": node.name,
                    "line": node.lineno,
                    "column": node.col_offset,
                    "end_line": getattr(node, "end_lineno", node.lineno),
                    "complexity": (complexities or {}).get((node.lineno, node.col_offset), 1),
                }
            )
    return sorted(details, key=lambda item: (item["line"], item["name"]))


def calculate_metrics(
    tree: ast.AST,
    source: str,
    complexities: dict[tuple[int, int], int] | None = None,
) -> dict[str, Any]:
    """Calculate deterministic source and AST metrics."""

    line_metrics = _line_metrics(source)
    nodes = list(ast.walk(tree))
    nesting = _NestingVisitor()
    nesting.visit(tree)
    return {
        **line_metrics,
        "ast_nodes": len(nodes),
        "functions": sum(isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) for node in nodes),
        "classes": sum(isinstance(node, ast.ClassDef) for node in nodes),
        "imports": sum(isinstance(node, (ast.Import, ast.ImportFrom)) for node in nodes),
        "max_nesting_depth": nesting.maximum,
        "functions_detail": _function_details(tree, complexities),
    }


def empty_metrics(source: str) -> dict[str, Any]:
    """Return line metrics when a source file has no valid AST."""

    return {
        **_line_metrics(source),
        "ast_nodes": 0,
        "functions": 0,
        "classes": 0,
        "imports": 0,
        "max_nesting_depth": 0,
        "functions_detail": [],
    }
