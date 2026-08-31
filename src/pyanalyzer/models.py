"""Stable public data contracts used by the analyzer and its formatters."""

from dataclasses import dataclass, field
from typing import Any, Literal


Severity = Literal["info", "warning", "error"]


@dataclass(frozen=True)
class Finding:
    """A single source-level diagnostic."""

    rule_id: str
    category: str
    severity: Severity
    file: str
    line: int
    column: int
    message: str
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-compatible representation with stable field names."""

        return {
            "rule_id": self.rule_id,
            "category": self.category,
            "severity": self.severity,
            "file": self.file,
            "line": self.line,
            "column": self.column,
            "message": self.message,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class AnalysisConfig:
    """Options that affect analysis and output status."""

    complexity_threshold: int = 10
    duplicate_min_statements: int = 3
    fail_on: Literal["none", "info", "warning", "error"] = "error"
    exclude: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.complexity_threshold < 1:
            raise ValueError("complexity_threshold must be greater than zero")
        if self.duplicate_min_statements < 1:
            raise ValueError("duplicate_min_statements must be greater than zero")
        if self.fail_on not in {"none", "info", "warning", "error"}:
            raise ValueError(f"unsupported fail_on level: {self.fail_on}")


@dataclass
class FileAnalysis:
    """Analysis results for one input source file."""

    path: str
    metrics: dict[str, Any]
    findings: list[Finding] = field(default_factory=list)


@dataclass
class AnalysisReport:
    """Analysis results for all requested files."""

    files: list[FileAnalysis]
    config: AnalysisConfig

    @property
    def findings(self) -> list[Finding]:
        """Return all findings in deterministic order."""

        return sorted(
            (finding for file_result in self.files for finding in file_result.findings),
            key=lambda item: (item.file, item.line, item.column, item.rule_id, item.message),
        )


class InputError(ValueError):
    """Raised when a requested input or CLI option cannot be processed."""
