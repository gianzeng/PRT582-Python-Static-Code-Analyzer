"""Cyclomatic complexity analysis for Python ASTs."""

import ast
from dataclasses import dataclass
from typing import Any

from ..models import Finding


@dataclass(frozen=True)
class ComplexitySummary:
    module: int
    functions: dict[tuple[int, int], int]


class _ComplexityVisitor(ast.NodeVisitor):
    """Count decisions in one lexical code body."""

    def __init__(self) -> None:
        self.value = 1

    def visit_If(self, node: ast.If) -> None:
        self.value += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:
        self.value += 1
        self.generic_visit(node)

    visit_AsyncFor = visit_For

    def visit_While(self, node: ast.While) -> None:
        self.value += 1
        self.generic_visit(node)

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        self.value += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:
        self.value += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:
        self.value += max(0, len(node.values) - 1)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:
        self.value += len(node.ifs)
        self.generic_visit(node)

    def visit_Match(self, node: ast.Match) -> None:
        # A match with N cases contributes N-1 alternatives beyond the base.
        self.value += max(0, len(node.cases) - 1)
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        # Nested functions have their own complexity and are handled separately.
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        # Class bodies are not part of their containing function's complexity.
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        # A lambda is another executable scope for this rule's purposes.
        return


def _complexity_for_nodes(nodes: list[ast.AST]) -> int:
    visitor = _ComplexityVisitor()
    for node in nodes:
        visitor.visit(node)
    return visitor.value


def calculate_complexity(tree: ast.AST) -> ComplexitySummary:
    """Calculate module and function complexity without double counting scopes."""

    module_nodes = list(getattr(tree, "body", []))
    module_value = _complexity_for_nodes(module_nodes)
    functions: dict[tuple[int, int], int] = {}

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions[(node.lineno, node.col_offset)] = _complexity_for_nodes(node.body)

    return ComplexitySummary(module=module_value, functions=functions)


def analyze_complexity(tree: ast.AST, filename: str, threshold: int) -> list[Finding]:
    """Return findings for functions whose complexity exceeds *threshold*."""

    summary = calculate_complexity(tree)
    findings: list[Finding] = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        value = summary.functions[(node.lineno, node.col_offset)]
        if value > threshold:
            findings.append(
                Finding(
                    rule_id="C001",
                    category="complexity",
                    severity="warning",
                    file=filename,
                    line=node.lineno,
                    column=node.col_offset,
                    message=(
                        f"Function '{node.name}' has complexity {value} "
                        f"(threshold {threshold})"
                    ),
                    evidence={"name": node.name, "value": value, "threshold": threshold},
                )
            )
    return sorted(findings, key=lambda item: (item.line, item.column, item.message))
