"""Scope-aware unused binding and import diagnostics."""

import ast
from dataclasses import dataclass, field

from ..models import Finding


@dataclass
class _Binding:
    name: str
    node: ast.AST
    kind: str


@dataclass
class _Scope:
    parent: "_Scope | None"
    bindings: dict[str, _Binding] = field(default_factory=dict)
    loads: set[str] = field(default_factory=set)
    children: list["_Scope"] = field(default_factory=list)
    global_names: set[str] = field(default_factory=set)
    nonlocal_names: set[str] = field(default_factory=set)
    global_loads: set[str] = field(default_factory=set)

    def bind(self, name: str, node: ast.AST, kind: str = "variable") -> None:
        if name in self.global_names or name in self.nonlocal_names:
            return
        self.bindings[name] = _Binding(name, node, kind)


class _DeclarationCollector(ast.NodeVisitor):
    """Collect declarations belonging to one lexical function body."""

    def __init__(self) -> None:
        self.global_names: set[str] = set()
        self.nonlocal_names: set[str] = set()

    def visit_Global(self, node: ast.Global) -> None:
        self.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.nonlocal_names.update(node.names)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        return

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        return

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        return


def _is_exempt(name: str) -> bool:
    return name in {"_", "self", "cls"} or (name.startswith("__") and name.endswith("__"))


class _ScopeCollector(ast.NodeVisitor):
    def __init__(self) -> None:
        self.root = _Scope(parent=None)
        self.current = self.root

    def _child_scope(self) -> _Scope:
        child = _Scope(parent=self.current)
        self.current.children.append(child)
        return child

    def _bind_arguments(self, node: ast.arguments, scope: _Scope) -> None:
        arguments = [*node.posonlyargs, *node.args, *node.kwonlyargs]
        if node.vararg:
            arguments.append(node.vararg)
        if node.kwarg:
            arguments.append(node.kwarg)
        for argument in arguments:
            scope.bind(argument.arg, argument, "parameter")

    @staticmethod
    def _prepare_declarations(nodes: list[ast.stmt], scope: _Scope) -> None:
        collector = _DeclarationCollector()
        for statement in nodes:
            collector.visit(statement)
        scope.global_names.update(collector.global_names)
        scope.nonlocal_names.update(collector.nonlocal_names)

    @staticmethod
    def _visit_annotations(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.AST]:
        annotations: list[ast.AST] = []
        for argument in (
            *node.args.posonlyargs,
            *node.args.args,
            *node.args.kwonlyargs,
        ):
            if argument.annotation is not None:
                annotations.append(argument.annotation)
        if node.args.vararg and node.args.vararg.annotation is not None:
            annotations.append(node.args.vararg.annotation)
        if node.args.kwarg and node.args.kwarg.annotation is not None:
            annotations.append(node.args.kwarg.annotation)
        if node.returns is not None:
            annotations.append(node.returns)
        return annotations

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.current.bind(node.name, node, "definition")
        # Decorators/default values execute in the surrounding scope.
        for decorator in node.decorator_list:
            self.visit(decorator)
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        for annotation in self._visit_annotations(node):
            self.visit(annotation)
        child = self._child_scope()
        previous = self.current
        self.current = child
        self._prepare_declarations(node.body, child)
        self._bind_arguments(node.args, child)
        for statement in node.body:
            self.visit(statement)
        self.current = previous

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Lambda(self, node: ast.Lambda) -> None:
        for default in [*node.args.defaults, *node.args.kw_defaults]:
            if default is not None:
                self.visit(default)
        child = self._child_scope()
        previous = self.current
        self.current = child
        self._bind_arguments(node.args, child)
        self.visit(node.body)
        self.current = previous

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.current.bind(node.name, node, "definition")
        for base in node.bases:
            self.visit(base)
        for keyword in node.keywords:
            self.visit(keyword.value)
        for decorator in node.decorator_list:
            self.visit(decorator)
        child = self._child_scope()
        previous = self.current
        self.current = child
        for statement in node.body:
            self.visit(statement)
        self.current = previous

    def visit_Name(self, node: ast.Name) -> None:
        if isinstance(node.ctx, ast.Load):
            if node.id in self.current.global_names:
                self.current.global_loads.add(node.id)
            else:
                self.current.loads.add(node.id)
        elif isinstance(node.ctx, (ast.Store, ast.Del)):
            self.current.bind(node.id, node, "variable")

    def visit_Global(self, node: ast.Global) -> None:
        self.current.global_names.update(node.names)

    def visit_Nonlocal(self, node: ast.Nonlocal) -> None:
        self.current.nonlocal_names.update(node.names)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            name = alias.asname or alias.name.split(".")[0]
            self.current.bind(name, node, "import")

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        for alias in node.names:
            if alias.name != "*":
                self.current.bind(alias.asname or alias.name, node, "import")

    def visit_ExceptHandler(self, node: ast.ExceptHandler) -> None:
        if node.name:
            self.current.bind(node.name, node, "variable")
        if node.type:
            self.visit(node.type)
        for statement in node.body:
            self.visit(statement)

    def _visit_comprehension(
        self,
        generators: list[ast.comprehension],
        result_nodes: list[ast.AST],
    ) -> None:
        # Python evaluates the first iterator in the surrounding scope, then
        # evaluates the target, later iterators, filters and result in the
        # comprehension's implicit scope.
        if not generators:
            return
        self.visit(generators[0].iter)
        child = self._child_scope()
        previous = self.current
        self.current = child
        for generator in generators:
            if generator is not generators[0]:
                self.visit(generator.iter)
            self.visit(generator.target)
            for condition in generator.ifs:
                self.visit(condition)
        for node in result_nodes:
            self.visit(node)
        self.current = previous

    def visit_ListComp(self, node: ast.ListComp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_SetComp(self, node: ast.SetComp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_GeneratorExp(self, node: ast.GeneratorExp) -> None:
        self._visit_comprehension(node.generators, [node.elt])

    def visit_DictComp(self, node: ast.DictComp) -> None:
        self._visit_comprehension(node.generators, [node.key, node.value])


def _free_loads(scope: _Scope) -> set[str]:
    child_free: set[str] = set()
    for child in scope.children:
        child_free.update(_free_loads(child))
    return (scope.loads - set(scope.bindings)) | (child_free - set(scope.bindings))


def _descendant_free_loads(scope: _Scope) -> set[str]:
    return {name for child in scope.children for name in _free_loads(child)}


def _all_global_loads(scope: _Scope) -> set[str]:
    loads = set(scope.global_loads)
    for child in scope.children:
        loads.update(_all_global_loads(child))
    return loads


def _finding(binding: _Binding, filename: str) -> Finding:
    line = getattr(binding.node, "lineno", 1)
    column = getattr(binding.node, "col_offset", 0)
    rule = "U002" if binding.kind == "import" else "U003" if binding.kind == "parameter" else "U001"
    label = "parameter" if binding.kind == "parameter" else "import" if binding.kind == "import" else "variable"
    return Finding(
        rule_id=rule,
        category="unused",
        severity="warning",
        file=filename,
        line=line,
        column=column,
        message=f"Unused {label} '{binding.name}'",
        evidence={"name": binding.name, "kind": binding.kind},
    )


def analyze_unused(tree: ast.AST, filename: str) -> list[Finding]:
    """Find bindings with no read in their lexical scope or closures."""

    collector = _ScopeCollector()
    collector.visit(tree)
    findings: list[Finding] = []
    root_global_loads = _all_global_loads(collector.root)
    scopes = [collector.root]
    while scopes:
        scope = scopes.pop()
        descendant_loads = _descendant_free_loads(scope)
        used = scope.loads | descendant_loads
        if scope is collector.root:
            used.update(root_global_loads)
        for binding in scope.bindings.values():
            if binding.kind in {"variable", "import", "parameter"} and binding.name not in used and not _is_exempt(binding.name):
                findings.append(_finding(binding, filename))
        scopes.extend(scope.children)
    return sorted(findings, key=lambda item: (item.line, item.column, item.rule_id, item.message))
