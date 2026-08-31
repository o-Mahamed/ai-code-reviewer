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
        # Iterate Try nodes (not ExceptHandler nodes directly) so we can
        # see the try-body alongside each handler -- that's what lets us
        # recognize the "optional dependency" idiom below.
        for try_node in ast.walk(tree):
            if not isinstance(try_node, ast.Try):
                continue

            for handler in try_node.handlers:
                if not self._is_noop_body(handler.body):
                    continue
                if self._is_optional_import_fallback(try_node, handler):
                    continue

                exc_desc = self._describe_exception_type(handler)
                yield Finding(
                    bug_class=self.bug_class,
                    line=handler.lineno,
                    message=(
                        f"except block for {exc_desc} silently discards the "
                        "exception (body is only pass/... ) with no logging "
                        "or re-raise -- failures here will be invisible."
                    ),
                    severity="high",
                )

    @staticmethod
    def _is_optional_import_fallback(try_node: ast.Try, handler: ast.ExceptHandler) -> bool:
        """Recognizes the extremely common
            try:
                import optional_thing
            except ImportError:
                pass
        idiom -- catching ImportError (alone or alongside others, e.g.
        `except (ImportError, AttributeError):`) around a try body that
        actually contains an import. This is a deliberate, well-known
        pattern for optional dependencies, not a swallowed bug.
        """
        catches_import_error = False
        if isinstance(handler.type, ast.Name) and handler.type.id == "ImportError":
            catches_import_error = True
        elif isinstance(handler.type, ast.Tuple):
            catches_import_error = any(
                isinstance(elt, ast.Name) and elt.id == "ImportError"
                for elt in handler.type.elts
            )
        if not catches_import_error:
            return False

        # Search recursively, not just top-level statements -- real code
        # often nests the actual import inside an `if` or another `try`
        # within the outer try body (e.g. requests/__init__.py does
        # exactly this: try -> if -> from x import y).
        for stmt in try_node.body:
            for sub_node in ast.walk(stmt):
                if isinstance(sub_node, (ast.Import, ast.ImportFrom)):
                    return True
        return False

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
