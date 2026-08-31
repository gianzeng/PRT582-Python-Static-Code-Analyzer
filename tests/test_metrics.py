import unittest

from pyanalyzer.engine import analyze_source


class MetricsTests(unittest.TestCase):
    def test_b12_line_metrics_distinguish_blank_comment_and_code(self):
        source = "# comment\n\nvalue = 1\n\nprint(value)\n"

        result = analyze_source(source, "metrics.py")

        self.assertEqual(result.metrics["physical_lines"], 5)
        self.assertEqual(result.metrics["blank_lines"], 2)
        self.assertEqual(result.metrics["comment_lines"], 1)
        self.assertEqual(result.metrics["code_lines"], 2)

    def test_metrics_count_declarations_and_nested_depth(self):
        source = """class GoodName:\n    def good_name(self):\n        if True:\n            return 1\n        return 0\n"""

        result = analyze_source(source, "metrics.py")

        self.assertEqual(result.metrics["classes"], 1)
        self.assertEqual(result.metrics["functions"], 1)
        self.assertGreaterEqual(result.metrics["ast_nodes"], 10)
        self.assertGreaterEqual(result.metrics["max_nesting_depth"], 2)

    def test_b02_simple_function_has_complexity_one(self):
        result = analyze_source("def simple():\n    return 1\n", "complexity.py")

        function = result.metrics["functions_detail"][0]
        self.assertEqual(function["name"], "simple")
        self.assertEqual(function["complexity"], 1)
