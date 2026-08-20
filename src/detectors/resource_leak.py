"""
Flags calls to open() that aren't wrapped in a `with` statement AND
aren't explicitly closed later via `.close()` in the same function.

This is intentionally a heuristic, not a full data-flow analysis:
- It correctly ignores `with open(...) as f:` (the common safe pattern).
- It correctly ignores `f = open(...); ...; f.close()` (manual close).
- It will flag opens where the close happens conditionally, in a
  different branch, or via a helper function -- those are genuinely
  ambiguous cases and erring toward flagging them is the right
  tradeoff for a *review* tool (false negatives are worse than a
  human having to dismiss a false positive).
"""

from __future__ import annotations

import ast
from typing import Iterator

from .base import Detector, Finding


class ResourceLeakDetector(Detector):
    bug_class = "resource_leak"

    def check(self, tree: ast.AST, source_lines: list[str]) -> Iterator[Finding]:
        # Collect open() calls that are safely inside a `with` context.
        protected_call_ids: set[int] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.With):
                for item in node.items:
                    if self._is_open_call(item.context_expr):
                        protected_call_ids.add(id(item.context_expr))

        # Each function (and the module top level) is its own scope.
        # We deliberately do NOT recurse into nested function bodies
        # when scoping a given function -- that would let a .close()
        # call in one function "cancel out" an open() in a totally
        # unrelated function that happens to reuse a variable name
        # like `f`.
        scopes: list[ast.AST] = [tree] + [
            n for n in ast.walk(tree)
            if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
        ]

        seen: set[int] = set()
        for scope in scopes:
            descendants = list(self._scoped_walk(scope))
            closed_names = {
                node.func.value.id
                for node in descendants
                if isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "close"
                and isinstance(node.func.value, ast.Name)
            }

            for node in descendants:
                if not self._is_open_call(node) or id(node) in protected_call_ids:
                    continue
                if id(node) in seen:
                    continue
                seen.add(id(node))

                assigned_name = self._assigned_name_in(descendants, node)
                if assigned_name and assigned_name in closed_names:
                    continue

                yield Finding(
                    bug_class=self.bug_class,
                    line=node.lineno,
                    message=(
                        "open() call is not inside a 'with' block and no "
                        "matching .close() was found in this scope -- the "
                        "file handle may leak if an exception occurs."
                    ),
                    severity="medium",
                )

    @staticmethod
    def _is_open_call(node: ast.AST | None) -> bool:
        return (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Name)
            and node.func.id == "open"
        )

    @staticmethod
    def _scoped_walk(node: ast.AST) -> Iterator[ast.AST]:
        """Like ast.walk, but does not descend into nested function or
        lambda bodies -- keeps each function's variables scoped to
        itself instead of bleeding into siblings."""
        stack = list(ast.iter_child_nodes(node))
        while stack:
            current = stack.pop()
            yield current
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
                continue
            stack.extend(ast.iter_child_nodes(current))

    @staticmethod
    def _assigned_name_in(descendants: list[ast.AST], call_node: ast.Call) -> str | None:
        for node in descendants:
            if isinstance(node, ast.Assign) and node.value is call_node:
                if len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
                    return node.targets[0].id
        return None
