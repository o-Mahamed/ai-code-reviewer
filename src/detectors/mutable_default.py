"""
Flags function definitions using a mutable literal (list/dict/set) as a
default argument value -- the classic Python gotcha where the default
is created once at function-definition time and shared across every
call that doesn't override it, causing state to leak between calls.
"""

from __future__ import annotations

import ast
from typing import Iterator

from .base import Detector, Finding

MUTABLE_NODE_TYPES = (ast.List, ast.Dict, ast.Set)


class MutableDefaultDetector(Detector):
    bug_class = "mutable_default"

    def check(self, tree: ast.AST, source_lines: list[str]) -> Iterator[Finding]:
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue

            all_defaults = list(node.args.defaults) + list(node.args.kw_defaults)
            for default in all_defaults:
                if isinstance(default, MUTABLE_NODE_TYPES):
                    kind = type(default).__name__.lower()
                    yield Finding(
                        bug_class=self.bug_class,
                        line=node.lineno,
                        message=(
                            f"function '{node.name}' uses a mutable {kind} "
                            "literal as a default argument -- it's created "
                            "once and shared across calls, which can leak "
                            "state between unrelated invocations."
                        ),
                        severity="high",
                    )
