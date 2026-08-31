import unittest

from pyanalyzer.engine import analyze_source


class UnusedNameTests(unittest.TestCase):
    def test_b05_used_local_and_import_are_not_reported(self):
        source = """import math

def calculate(value):
    result = math.floor(value)
    return result
"""

        result = analyze_source(source, "unused.py")

        self.assertEqual([item for item in result.findings if item.category == "unused"], [])

    def test_b06_unused_local_is_reported_but_placeholder_is_exempt(self):
        source = """def calculate(value):
    unused_value = value
    _ = value
    return value
"""

        result = analyze_source(source, "unused.py")
        unused = [item for item in result.findings if item.category == "unused"]

        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].rule_id, "U001")
        self.assertEqual(unused[0].evidence["name"], "unused_value")
        self.assertEqual(unused[0].line, 2)

    def test_b07_unused_import_is_reported(self):
        source = """import os
from pathlib import Path

value = Path('file.txt')
print(value)
"""

        result = analyze_source(source, "unused.py")
        unused = [item for item in result.findings if item.category == "unused"]

        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].rule_id, "U002")
        self.assertEqual(unused[0].evidence["name"], "os")

    def test_b17_nested_function_does_not_merge_same_name_scopes(self):
        source = """def outer():
    value = 1
    def inner():
        value = 2
        return value
    return inner()
"""

        result = analyze_source(source, "scopes.py")
        unused = [item for item in result.findings if item.category == "unused"]

        self.assertEqual(len(unused), 1)
        self.assertEqual(unused[0].evidence["name"], "value")
        self.assertEqual(unused[0].line, 2)

    def test_closure_read_counts_as_use_of_outer_binding(self):
        source = """def outer():
    value = 1
    def inner():
        return value
    return inner
"""

        result = analyze_source(source, "closure.py")
        unused = [item for item in result.findings if item.category == "unused"]

        self.assertFalse(any(item.evidence["name"] == "value" for item in unused))

    def test_annotation_names_count_as_uses_of_imports(self):
        source = """from typing import Iterable

def transform(items: Iterable[int]) -> Iterable[int]:
    return items
"""

        result = analyze_source(source, "annotations.py")
        unused = [item for item in result.findings if item.category == "unused"]

        self.assertEqual(unused, [])

    def test_comprehension_target_has_its_own_scope(self):
        source = """def build(items):
    item = "outer"
    values = [item for item in items]
    return values
"""

        result = analyze_source(source, "comprehension.py")
        unused = [item for item in result.findings if item.category == "unused"]

        self.assertEqual(
            [(item.evidence["name"], item.line) for item in unused],
            [("item", 2)],
        )

    def test_global_assignment_is_not_reported_as_a_local_binding(self):
        source = """value = 0

def update():
    global value
    value = 1
"""

        result = analyze_source(source, "global.py")
        unused = [item for item in result.findings if item.category == "unused"]

        self.assertFalse(any(item.evidence["name"] == "value" and item.line == 5 for item in unused))

    def test_global_read_does_not_use_same_named_enclosing_binding(self):
        source = """def outer():
    value = 0
    def inner():
        global value
        return value
    return inner
"""

        result = analyze_source(source, "global-shadow.py")
        unused = [item for item in result.findings if item.category == "unused"]

        self.assertEqual(
            [(item.evidence["name"], item.line) for item in unused],
            [("value", 2)],
        )

    def test_nonlocal_assignment_is_not_reported_as_a_local_binding(self):
        source = """def outer():
    value = 0
    def update():
        nonlocal value
        value = 1
    return update
"""

        result = analyze_source(source, "nonlocal.py")
        unused = [item for item in result.findings if item.category == "unused"]

        self.assertEqual(
            [(item.evidence["name"], item.line) for item in unused],
            [("value", 2)],
        )
