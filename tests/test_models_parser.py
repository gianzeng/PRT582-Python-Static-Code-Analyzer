import json
import unittest

from pyanalyzer.engine import analyze_source
from pyanalyzer.models import Finding


class ModelAndParserTests(unittest.TestCase):
    def test_finding_serializes_to_stable_json_contract(self):
        finding = Finding(
            rule_id="N001",
            category="naming",
            severity="warning",
            file="example.py",
            line=3,
            column=0,
            message="Use snake_case",
            evidence={"name": "badName"},
        )

        payload = finding.to_dict()

        self.assertEqual(payload["rule_id"], "N001")
        self.assertEqual(payload["evidence"], {"name": "badName"})
        self.assertIsInstance(json.dumps(payload, sort_keys=True), str)

    def test_b01_empty_file_has_baseline_metrics(self):
        result = analyze_source("", "empty.py")

        self.assertEqual(result.path, "empty.py")
        self.assertEqual(result.metrics["physical_lines"], 0)
        self.assertEqual(result.metrics["code_lines"], 0)
        self.assertEqual(result.findings, [])

    def test_b16_syntax_error_is_a_finding(self):
        result = analyze_source("def broken(:\n", "broken.py")

        self.assertEqual(len(result.findings), 1)
        self.assertEqual(result.findings[0].rule_id, "P001")
        self.assertEqual(result.findings[0].file, "broken.py")
        self.assertGreaterEqual(result.findings[0].line, 1)
        self.assertNotIn("Traceback", result.findings[0].message)
