import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class CliIntegrationTests(unittest.TestCase):
    def run_cli(self, *arguments):
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(ROOT / "src")
        return subprocess.run(
            [sys.executable, "-m", "pyanalyzer", *arguments],
            cwd=ROOT,
            env=environment,
            capture_output=True,
            text=True,
        )

    def test_b13_text_output_has_sorted_findings_and_metrics(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "example.py"
            path.write_text("def BadName(value):\n    unused_value = value\n    if value:\n        return 1\n    return 0\n", encoding="utf-8")

            completed = self.run_cli(str(path), "--format", "text", "--fail-on", "warning")

            self.assertEqual(completed.returncode, 1)
            self.assertIn("example.py", completed.stdout)
            self.assertIn("complexity", completed.stdout)
            self.assertIn("metrics", completed.stdout)
            self.assertEqual(completed.stderr, "")

    def test_b14_json_output_has_schema(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "clean.py"
            path.write_text("def clean_name(value):\n    return value\n", encoding="utf-8")

            completed = self.run_cli(str(path), "--format", "json")

            self.assertEqual(completed.returncode, 0)
            self.assertEqual(completed.stderr, "")
            payload = json.loads(completed.stdout)
            self.assertEqual(set(payload), {"config", "files", "findings"})
            self.assertEqual(payload["findings"], [])
            self.assertIn("metrics", payload["files"][0])

    def test_b18_repeating_analysis_produces_byte_for_byte_equivalent_json(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "repeatable.py"
            path.write_text("def repeatable(value):\n    if value:\n        return value\n    return 0\n", encoding="utf-8")

            first = self.run_cli(
                str(path),
                "--format",
                "json",
                "--complexity-threshold",
                "1",
                "--fail-on",
                "none",
            )
            second = self.run_cli(
                str(path),
                "--format",
                "json",
                "--complexity-threshold",
                "1",
                "--fail-on",
                "none",
            )

            self.assertEqual(first.returncode, 0)
            self.assertEqual(second.returncode, 0)
            self.assertEqual(first.stderr, "")
            self.assertEqual(first.stdout, second.stdout)

    def test_b15_missing_path_returns_controlled_error(self):
        completed = self.run_cli("/definitely/missing.py")

        self.assertEqual(completed.returncode, 2)
        self.assertEqual(completed.stdout, "")
        self.assertIn("does not exist", completed.stderr)
        self.assertNotIn("Traceback", completed.stderr)

    def test_b16_syntax_error_is_visible_without_traceback(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "broken.py"
            path.write_text("def broken(:\n", encoding="utf-8")

            completed = self.run_cli(str(path), "--format", "json", "--fail-on", "none")

            self.assertEqual(completed.returncode, 0)
            payload = json.loads(completed.stdout)
            self.assertEqual(payload["findings"][0]["rule_id"], "P001")
            self.assertNotIn("Traceback", completed.stdout)
