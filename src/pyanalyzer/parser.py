"""Read and parse Python source without executing it."""

import ast
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ParsedSource:
    """The source text and AST, or a syntax error if parsing failed."""

    source: str
    tree: ast.AST | None
    syntax_error: SyntaxError | None = None


def parse_source(source: str, filename: str = "<string>") -> ParsedSource:
    """Parse source into an AST and preserve syntax diagnostics."""

    try:
        tree = ast.parse(source, filename=filename, type_comments=True)
    except SyntaxError as exc:
        return ParsedSource(source=source, tree=None, syntax_error=exc)
    return ParsedSource(source=source, tree=tree)


def read_source(path: Path) -> str:
    """Read UTF-8 source text from *path* without running it."""

    return path.read_text(encoding="utf-8")
