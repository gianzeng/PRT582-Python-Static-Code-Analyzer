"""Structural duplicate-code detection using normalized AST statement sequences."""

import ast
import copy
import hashlib
from dataclasses import dataclass

from ..models import Finding


@dataclass(frozen=True)
class _Suite:
    filename: str
    nodes: tuple[ast.stmt, ...]


class _NameNormalizer(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.Name:
        node.id = "<name>"
        return node


def _signature(node: ast.stmt) -> str:
    normalized = _NameNormalizer().visit(copy.deepcopy(node))
    return ast.dump(normalized, annotate_fields=True, include_attributes=False)


def _suites(tree: ast.AST, filename: str) -> list[_Suite]:
    suites: list[_Suite] = []
    if isinstance(tree, ast.Module):
        suites.append(_Suite(filename, tuple(tree.body)))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            suites.append(_Suite(filename, tuple(node.body)))
    return [suite for suite in suites if suite.nodes]


def analyze_duplicate_trees(
    trees: list[tuple[ast.AST, str]],
    minimum: int,
) -> dict[str, list[Finding]]:
    """Find longest repeated contiguous statement blocks across source trees."""

    suites = [suite for tree, filename in trees for suite in _suites(tree, filename)]
    sequences = [[_signature(node) for node in suite.nodes] for suite in suites]
    groups: dict[tuple[str, ...], dict[tuple[str, int, int], tuple[str, int, int]]] = {}

    for left_index, left in enumerate(sequences):
        for right_index in range(left_index, len(sequences)):
            right = sequences[right_index]
            for left_start in range(0, len(left) - minimum + 1):
                right_start_min = left_start + 1 if left_index == right_index else 0
                for right_start in range(right_start_min, len(right) - minimum + 1):
                    length = 0
                    while (
                        left_start + length < len(left)
                        and right_start + length < len(right)
                        and left[left_start + length] == right[right_start + length]
                    ):
                        length += 1
                    if length < minimum:
                        continue
                    key = tuple(left[left_start : left_start + length])
                    locations = groups.setdefault(key, {})
                    left_node = suites[left_index].nodes[left_start]
                    right_node = suites[right_index].nodes[right_start]
                    locations[(suites[left_index].filename, left_node.lineno, left_node.col_offset)] = (
                        suites[left_index].filename,
                        left_node.lineno,
                        left_node.col_offset,
                    )
                    locations[(suites[right_index].filename, right_node.lineno, right_node.col_offset)] = (
                        suites[right_index].filename,
                        right_node.lineno,
                        right_node.col_offset,
                    )

    result: dict[str, list[Finding]] = {filename: [] for _, filename in trees}
    ordered_groups = sorted(groups.items(), key=lambda item: len(item[0]), reverse=True)
    for key, location_map in ordered_groups:
        locations = sorted(location_map.values())
        covered_locations = []
        for location in locations:
            filename, line, column = location
            covered = False
            for larger_key, larger_locations in ordered_groups:
                if len(larger_key) <= len(key) or not _contains_sequence(larger_key, key):
                    continue
                for larger_filename, larger_line, larger_column in larger_locations.values():
                    if (
                        larger_filename == filename
                        and larger_line <= line <= larger_line + len(larger_key) - len(key)
                        and larger_column == column
                    ):
                        covered = True
                        break
                if covered:
                    break
            if not covered:
                covered_locations.append(location)
        locations = covered_locations
        if len(locations) < 2:
            continue
        group_id = "D001-" + hashlib.sha1("\n".join(key).encode("utf-8")).hexdigest()[:10]
        for filename, line, column in locations:
            result.setdefault(filename, []).append(
                Finding(
                    rule_id="D001",
                    category="duplicate",
                    severity="warning",
                    file=filename,
                    line=line,
                    column=column,
                    message=(
                        f"Duplicate code block of {len(key)} statements "
                        f"(group {group_id}, {len(locations)} occurrences)"
                    ),
                    evidence={
                        "group_id": group_id,
                        "length": len(key),
                        "occurrences": len(locations),
                    },
                )
            )

    for filename in result:
        result[filename].sort(key=lambda item: (item.line, item.column, item.message))
    return result


def _contains_sequence(container: tuple[str, ...], candidate: tuple[str, ...]) -> bool:
    width = len(candidate)
    return any(container[index : index + width] == candidate for index in range(len(container) - width + 1))


def analyze_duplicates(tree: ast.AST, filename: str, minimum: int) -> list[Finding]:
    """Find duplicates within one source file."""

    return analyze_duplicate_trees([(tree, filename)], minimum).get(filename, [])
