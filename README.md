# Python Static Code Analyzer

`pyanalyzer` is a standard-library-first static analyzer for Python source code. It parses source with `ast` and reports:

- cyclomatic complexity;
- unused variables and imports;
- structurally duplicated statement blocks;
- naming convention violations; and
- source-code metrics.

The tool never executes the analyzed source.

Python 3.10 or newer is required. The examples below use `python3`; use the
path to any Python 3.10+ interpreter available on your system.

## Run from a checkout

The project can be run without installing third-party runtime packages:

```bash
PYTHONPATH=src python3 -m pyanalyzer samples/example.py
PYTHONPATH=src python3 -m pyanalyzer samples/ --format json
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

The command returns `0` when no finding meets `--fail-on`, `1` when a finding meets it, and `2` for invalid command-line input or unreadable paths. A syntax error is reported as a finding and does not produce an unhandled traceback.

## CLI examples

```bash
PYTHONPATH=src python3 -m pyanalyzer samples/example.py
PYTHONPATH=src python3 -m pyanalyzer src/ --complexity-threshold 10 --fail-on warning
PYTHONPATH=src python3 -m pyanalyzer samples/ --format json > analysis.json
```

The final submission report contains the requirements analysis, selected AI-TDD prompt record, evaluation, test evidence and reflection. This code repository intentionally contains the executable project and tests; supplementary report evidence is kept with the submission artifact.
