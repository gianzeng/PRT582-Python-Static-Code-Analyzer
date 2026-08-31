"""Naming-convention diagnostics."""

import ast
import re

from ..models import Finding


_SNAKE_CASE = re.compile(r"^[a-z_][a-z0-9_]*$")
_PASCAL_CASE = re.compile(r"^[A-Z][A-Za-z0-9]*$")
_UPPER_SNAKE_CASE = re.compile(r"^[A-Z][A-Z0-9_]*$")


def _is_exempt(name: str) -> bool:
    return name == "_" or (name.startswith("__") and name.endswith("__"))


def _finding(rule_id: str, name: str, node: ast.AST, filename: str, expected: str) -> Finding:
    return Finding(
        rule_id=rule_id,
        category="naming",
        severity="warning",
        file=filename,
        line=getattr(node, "lineno", 1),
        column=getattr(node, "col_offset", 0),
        message=f"Name '{name}' should use {expected}",
        evidence={"name": name, "expected": expected},
    )


def _check_binding(name: str, node: ast.AST, filename: str, module_level: bool) -> list[Finding]:
    if _is_exempt(name):
        return []
    if module_level and _UPPER_SNAKE_CASE.fullmatch(name):
        return []
    if not _SNAKE_CASE.fullmatch(name):
        return [_finding("N001", name, node, filename, "snake_case")]
    return []


class _ModuleAssignmentCollector(ast.NodeVisitor):
    """Collect names assigned by module-level assignment statements."""

    def __init__(self) -> None:
        self.assignments: list[tuple[str, ast.AST]] = []

    def _record_targets(self, node: ast.AST, targets: list[ast.AST]) -> None:
        for target in targets:
            for descendant in ast.walk(target):
                if isinstance(descendant, ast.Name) and isinstance(descendant.ctx, ast.Store):
                    self.assignments.append((descendant.id, node))

    def visit_Assign(self, node: ast.Assign) -> None:
        self._record_targets(node, list(node.targets))
        self.generic_visit(node)

    def visit_AnnAssign(self, node: ast.AnnAssign) -> None:
        self._record_targets(node, [node.target])
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return


class _NamingVisitor(ast.NodeVisitor):
    def __init__(self, filename: str, module_constant_store_nodes: set[int]) -> None:
        self.filename = filename
        self.module_constant_store_nodes = module_constant_store_nodes
        self.findings: list[Finding] = []
        self.scope_depth = 0

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if not _is_exempt(node.name) and not _SNAKE_CASE.fullmatch(node.name):
            self.findings.append(_finding("N001", node.name, node, self.filename, "snake_case"))
        self.scope_depth += 1
        for argument in (*node.args.posonlyargs, *node.args.args, *node.args.kwonlyargs):
            self.findings.extend(_check_binding(argument.arg, argument, self.filename, False))
        if node.args.vararg:
            self.findings.extend(_check_binding(node.args.vararg.arg, node.args.vararg, self.filename, False))
        if node.args.kwarg:
            self.findings.extend(_check_binding(node.args.kwarg.arg, node.args.kwarg, self.filename, False))
        self.generic_visit(node)
        self.scope_depth -= 1

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if not _is_exempt(node.name) and not _PASCAL_CASE.fullmatch(node.name):
            self.findings.append(_finding("N002", node.name, node, self.filename, "PascalCase"))
        self.scope_depth += 1
        self.generic_visit(node)
        self.scope_depth -= 1

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.findings.extend(_check_binding(node.name, node, self.filename, self.scope_depth == 0))
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Store):
            # A module-level mixed-case assignment is classified as a constant
            # violation (N003), not duplicated as a generic snake-case finding.
            is_mixed_case_module_binding = (
                self.scope_depth == 0
                and id(node) in self.module_constant_store_nodes
                and any(character.isupper() for character in node.id)
                and not _UPPER_SNAKE_CASE.fullmatch(node.id)
            )
            if not is_mixed_case_module_binding:
                self.findings.extend(_check_binding(node.id, node, self.filename, self.scope_depth == 0))
        self.generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            # An unaliased import keeps the external symbol's spelling. An
            # explicit alias is a local binding and follows local naming.
            if alias.asname:
                self.findings.extend(_check_binding(alias.asname, node, self.filename, self.scope_depth == 0))

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name == "*" or not alias.asname:
                continue
            self.findings.extend(_check_binding(alias.asname, node, self.filename, self.scope_depth == 0))


def analyze_naming(tree: ast.AST, filename: str) -> list[Finding]:
    """Return naming findings in source order."""

    module_assignments = _ModuleAssignmentCollector()
    module_assignments.visit(tree)
    module_constant_store_nodes = {
        id(target)
        for name, node in module_assignments.assignments
        for target in ast.walk(node)
        if (
            isinstance(target, ast.Name)
            and isinstance(target.ctx, ast.Store)
            and any(character.isupper() for character in target.id)
            and not _UPPER_SNAKE_CASE.fullmatch(target.id)
            and target.id == name
        )
    }
    visitor = _NamingVisitor(filename, module_constant_store_nodes)
    visitor.visit(tree)
    # Constants are identified separately so module-level lower camel case is N003.
    for name, node in module_assignments.assignments:
        if any(
            isinstance(target, ast.Name)
            and isinstance(target.ctx, ast.Store)
            and target.id == name
            and id(target) in module_constant_store_nodes
            for target in ast.walk(node)
        ):
            visitor.findings.append(_finding("N003", name, node, filename, "UPPER_SNAKE_CASE"))
    return sorted(visitor.findings, key=lambda item: (item.line, item.column, item.rule_id, item.message))
