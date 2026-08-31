import unittest

from pyanalyzer.engine import analyze_source
from pyanalyzer.models import AnalysisConfig


def _function(result, name):
    return next(item for item in result.metrics["functions_detail"] if item["name"] == name)


class ComplexityTests(unittest.TestCase):
    def test_b03_decisions_and_boolean_short_circuit_increase_complexity(self):
        source = """def branch(value):
    if value and value > 0:
        return 1
    return 0
"""

        result = analyze_source(source, "complexity.py")

        self.assertEqual(_function(result, "branch")["complexity"], 3)
        self.assertEqual(result.metrics["module_complexity"], 1)

    def test_b04_equal_threshold_does_not_warn_but_lower_threshold_does(self):
        source = """def branch(value):
    if value:
        return 1
    return 0
"""

        equal = analyze_source(source, "complexity.py", AnalysisConfig(complexity_threshold=2))
        lower = analyze_source(source, "complexity.py", AnalysisConfig(complexity_threshold=1))

        self.assertEqual(_function(equal, "branch")["complexity"], 2)
        self.assertFalse([item for item in equal.findings if item.rule_id == "C001"])
        self.assertEqual(len([item for item in lower.findings if item.rule_id == "C001"]), 1)

    def test_nested_function_complexity_is_not_counted_in_outer_function(self):
        source = """def outer(value):
    def inner(other):
        if other:
            return 1
        return 0
    return inner(value)
"""

        result = analyze_source(source, "nested.py")

        self.assertEqual(_function(result, "outer")["complexity"], 1)
        self.assertEqual(_function(result, "inner")["complexity"], 2)
