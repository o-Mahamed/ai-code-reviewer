"""
Flags `except` blocks whose entire body is a no-op (pass / ... / a bare
comment), meaning an exception is caught and silently discarded with no
logging, re-raise, or handling of any kind.

This is deliberately narrow and unambiguous -- it will not flag except
blocks that log, re-raise, or take any real action, even a single line.
That precision matters: it's exactly what our mutation generator will
target (mutate a real `except: log/raise` into `except: pass`), which
gives us a clean, well-defined ground truth for the eval harness later.
"""

from __future__ import annotations

import ast
from typing import Iterator

from .base import Detector, Finding


class SwallowedExceptionDetector(Detector):
    bug_class = "swallowed_exception"

    def check(self, tree: ast.AST, source_lines: list[str]) -> Iterator[Finding]:
        for node in ast.walk(tree):
            if not isinstance(node, ast.ExceptHandler):
                continue

            if self._is_noop_body(node.body):
                exc_desc = self._describe_exception_type(node)
                yield Finding(
                    bug_class=self.bug_class,
                    line=node.lineno,
                    message=(
                        f"except block for {exc_desc} silently discards the "
                        "exception (body is only pass/... ) with no logging "
                        "or re-raise -- failures here will be invisible."
                    ),
                    severity="high",
                )

    @staticmethod
    def _is_noop_body(body: list[ast.stmt]) -> bool:
        if not body:
            return True
        return all(
            isinstance(stmt, ast.Pass)
            or (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
                and stmt.value.value is Ellipsis)
            for stmt in body
        )

    @staticmethod
    def _describe_exception_type(node: ast.ExceptHandler) -> str:
        if node.type is None:
            return "bare except"
        if isinstance(node.type, ast.Name):
            return node.type.id
        if isinstance(node.type, ast.Tuple):
            names = [n.id for n in node.type.elts if isinstance(n, ast.Name)]
            return " / ".join(names) if names else "exception"
        return "exception"
