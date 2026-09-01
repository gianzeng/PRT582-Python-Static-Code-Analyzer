import unittest

from pyanalyzer.engine import analyze_source
from pyanalyzer.models import AnalysisConfig


class RegressionTests(unittest.TestCase):
    def test_regression_module_constant_gets_one_specific_naming_finding(self):
        result = analyze_source("mixedConstant = 1\n", "regression.py")

        naming = [item for item in result.findings if item.category == "naming"]

        self.assertEqual(len(naming), 1)
        self.assertEqual(naming[0].rule_id, "N003")

    def test_regression_three_operand_boolean_expression_counts_two_extra_paths(self):
        source = """def evaluate(first, second, third):
    if first and second and third:
        return True
    return False
"""

        result = analyze_source(source, "regression.py")

        detail = result.metrics["functions_detail"][0]
        self.assertEqual(detail["complexity"], 4)

    def test_regression_for_with_and_except_bindings_are_scope_checked(self):
        source = """def process(items):
    unused_before = 1
    for item in items:
        print(item)
    with open('file.txt') as handle:
        data = handle.read()
    try:
        return data
    except ValueError as unused_error:
        return None
"""

        result = analyze_source(source, "regression.py")
        unused_names = {item.evidence["name"] for item in result.findings if item.category == "unused"}

        self.assertIn("unused_before", unused_names)
        self.assertNotIn("item", unused_names)
        self.assertNotIn("handle", unused_names)
        self.assertNotIn("data", unused_names)
        self.assertIn("unused_error", unused_names)

    def test_regression_findings_are_sorted_across_categories(self):
        source = """def BadName(value):
    unused_value = value
    if value:
        return 1
    return 0
"""

        result = analyze_source(source, "regression.py", AnalysisConfig(complexity_threshold=1))
        keys = [(item.line, item.column, item.rule_id, item.message) for item in result.findings]

        self.assertEqual(keys, sorted(keys))
