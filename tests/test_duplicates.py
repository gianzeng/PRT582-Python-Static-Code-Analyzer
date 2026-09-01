import tempfile
import unittest
from pathlib import Path

from pyanalyzer.engine import analyze_paths, analyze_source
from pyanalyzer.models import AnalysisConfig


class DuplicateCodeTests(unittest.TestCase):
    def test_b08_repeated_structural_block_is_reported(self):
        source = """def first(value):
    one = value + 1
    two = one + 1
    three = two + 1
    return three

def second(value):
    one = value + 1
    two = one + 1
    three = two + 1
    return three
"""

        result = analyze_source(source, "duplicates.py")
        findings = [item for item in result.findings if item.category == "duplicate"]

        self.assertEqual(len(findings), 2)
        self.assertTrue(all(item.evidence["length"] >= 3 for item in findings))
        self.assertEqual({item.evidence["occurrences"] for item in findings}, {2})
        self.assertNotEqual(findings[0].line, findings[1].line)

    def test_b09_block_shorter_than_minimum_is_not_reported(self):
        source = """def first():
    one = 1
    two = 2

def second():
    one = 1
    two = 2
"""

        result = analyze_source(source, "duplicates.py", AnalysisConfig(duplicate_min_statements=3))

        self.assertFalse([item for item in result.findings if item.category == "duplicate"])

    def test_structural_match_ignores_source_locations(self):
        source = """def first():
    first_name = 1
    first_value = first_name + 1
    return first_value

def second():
    second_name = 1
    second_value = second_name + 1
    return second_value
"""

        result = analyze_source(source, "duplicates.py", AnalysisConfig(duplicate_min_statements=3))

        self.assertEqual(len([item for item in result.findings if item.category == "duplicate"]), 2)

    def test_cross_file_duplicate_block_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            block = "value = 1\nresult = value + 1\nprint(result)\n"
            (root / "one.py").write_text(block, encoding="utf-8")
            (root / "two.py").write_text(block, encoding="utf-8")

            report = analyze_paths([directory])
            findings = [item for item in report.findings if item.category == "duplicate"]

            self.assertEqual(len(findings), 2)
            self.assertEqual({Path(item.file).name for item in findings}, {"one.py", "two.py"})

    def test_duplicate_blocks_in_one_module_suite_are_reported(self):
        source = """first = 1
second = first + 1
third = second + 1
first = 1
second = first + 1
third = second + 1
"""

        result = analyze_source(source, "same-suite.py")
        findings = [item for item in result.findings if item.category == "duplicate"]

        self.assertEqual(len(findings), 2)
        self.assertEqual({item.line for item in findings}, {1, 4})
