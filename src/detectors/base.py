"""
Base interface for all static analysis detectors.

Every detector takes a parsed AST + source lines, and yields Finding
objects. Keeping this interface uniform means the analyzer, the eval
harness, and (later) the LLM layer can all consume detector output the
same way, regardless of which bug class produced it.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass, field
from typing import Iterator


@dataclass
class Finding:
    bug_class: str          # e.g. "resource_leak"
    line: int                # 1-indexed line number
    message: str             # human-readable explanation
    severity: str = "medium" # "low" | "medium" | "high"
    confidence: float = 1.0  # 1.0 for deterministic static checks

    def to_dict(self) -> dict:
        return {
            "bug_class": self.bug_class,
            "line": self.line,
            "message": self.message,
            "severity": self.severity,
            "confidence": self.confidence,
        }


class Detector:
    """Subclass this and implement `check`."""

    bug_class: str = "base"

    def check(self, tree: ast.AST, source_lines: list[str]) -> Iterator[Finding]:
        raise NotImplementedError

    def run(self, source: str) -> list[Finding]:
        tree = ast.parse(source)
        lines = source.splitlines()
        return list(self.check(tree, lines))
