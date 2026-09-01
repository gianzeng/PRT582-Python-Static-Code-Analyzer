import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from pyanalyzer.engine import analyze_source
from pyanalyzer.models import AnalysisConfig, InputError


ROOT = Path(__file__).resolve().parents[1]


class QualityEdgeTests(unittest.TestCase):
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

    def test_directory_without_python_files_is_controlled_error(self):
        with tempfile.TemporaryDirectory() as directory:
            Path(directory, "notes.txt").write_text("not Python", encoding="utf-8")

            completed = self.run_cli(directory)

            self.assertEqual(completed.returncode, 2)
            self.assertIn("No Python files", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_non_positive_option_is_rejected_without_traceback(self):
        with tempfile.NamedTemporaryFile(suffix=".py") as source:
            Path(source.name).write_text("value = 1\n", encoding="utf-8")

            completed = self.run_cli(source.name, "--complexity-threshold", "0")

            self.assertEqual(completed.returncode, 2)
            self.assertIn("greater than zero", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_non_positive_duplicate_option_is_rejected_without_traceback(self):
        with tempfile.NamedTemporaryFile(suffix=".py") as source:
            Path(source.name).write_text("value = 1\n", encoding="utf-8")

            completed = self.run_cli(source.name, "--duplicate-min-statements", "0")

            self.assertEqual(completed.returncode, 2)
            self.assertIn("greater than zero", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_non_python_file_is_rejected_without_traceback(self):
        with tempfile.NamedTemporaryFile(suffix=".txt") as source:
            Path(source.name).write_text("not Python", encoding="utf-8")

            completed = self.run_cli(source.name)

            self.assertEqual(completed.returncode, 2)
            self.assertIn("not a Python file", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_invalid_utf8_is_reported_as_controlled_input_error(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.py"
            path.write_bytes(b"value = \xff\n")

            completed = self.run_cli(str(path))

            self.assertEqual(completed.returncode, 2)
            self.assertIn("Unable to read", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_invalid_format_choice_is_controlled_by_cli(self):
        with tempfile.NamedTemporaryFile(suffix=".py") as source:
            Path(source.name).write_text("value = 1\n", encoding="utf-8")

            completed = self.run_cli(source.name, "--format", "yaml")

            self.assertEqual(completed.returncode, 2)
            self.assertIn("invalid choice", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_invalid_fail_level_choice_is_controlled_by_cli(self):
        with tempfile.NamedTemporaryFile(suffix=".py") as source:
            Path(source.name).write_text("value = 1\n", encoding="utf-8")

            completed = self.run_cli(source.name, "--fail-on", "critical")

            self.assertEqual(completed.returncode, 2)
            self.assertIn("invalid choice", completed.stderr)
            self.assertNotIn("Traceback", completed.stderr)

    def test_analyzer_does_not_execute_analyzed_source(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            marker = root / "should_not_exist.txt"
            path = root / "untrusted.py"
            path.write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('executed')\n",
                encoding="utf-8",
            )

            completed = self.run_cli(str(path), "--fail-on", "none")

            self.assertEqual(completed.returncode, 0)
            self.assertFalse(marker.exists())

    def test_analysis_config_rejects_invalid_direct_values(self):
        with self.assertRaises(ValueError):
            AnalysisConfig(complexity_threshold=0)
        with self.assertRaises(ValueError):
            AnalysisConfig(fail_on="verbose")  # type: ignore[arg-type]

    def test_no_final_newline_is_counted_without_losing_last_line(self):
        result = analyze_source("value = 1", "no-newline.py")

        self.assertEqual(result.metrics["physical_lines"], 1)
        self.assertEqual(result.metrics["code_lines"], 1)
