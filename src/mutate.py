"""
Mutation generator: takes clean Python source and produces "mutants" -
copies of the source with a single, deliberate, well-defined bug
injected at one location. This is the ground truth for the eval
harness: we know exactly which bug was injected and where, so we can
measure precisely whether a detector (or later, the LLM reviewer)
actually catches it -- and, just as importantly, whether it stays
quiet on everything we *didn't* touch.
"""

from __future__ import annotations

import ast
import copy
from dataclasses import dataclass


@dataclass
class Mutant:
    bug_class: str
    source: str
    target_line: int  # line in the ORIGINAL source where the bug was injected
    description: str


def _is_open_call(node) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == "open"
    )


class _WithToAssignTransformer(ast.NodeTransformer):
    """Rewrites one target `with open(...) as name:` block into
    `name = open(...)` + its inlined body -- removing the safety net
    that guarantees the file gets closed."""

    def __init__(self, target_lineno: int):
        self.target_lineno = target_lineno
        self.applied = False

    def visit_With(self, node):
        self.generic_visit(node)
        if (
            not self.applied
            and node.lineno == self.target_lineno
            and len(node.items) == 1
            and _is_open_call(node.items[0].context_expr)
            and isinstance(node.items[0].optional_vars, ast.Name)
        ):
            self.applied = True
            name = node.items[0].optional_vars.id
            assign = ast.Assign(
                targets=[ast.Name(id=name, ctx=ast.Store())],
                value=node.items[0].context_expr,
            )
            ast.copy_location(assign, node)
            return [assign, *node.body]
        return node


class _ExceptToPassTransformer(ast.NodeTransformer):
    """Replaces a real except-block body with a bare `pass`."""

    def __init__(self, target_lineno: int):
        self.target_lineno = target_lineno
        self.applied = False

    def visit_ExceptHandler(self, node):
        self.generic_visit(node)
        if not self.applied and node.lineno == self.target_lineno:
            self.applied = True
            pass_stmt = ast.Pass()
            ast.copy_location(pass_stmt, node)
            node.body = [pass_stmt]
        return node


class _NoneDefaultToMutableTransformer(ast.NodeTransformer):
    """Changes a `None` default to a mutable literal. Any existing
    `if x is None: x = []` guard becomes dead code, and the function
    silently starts sharing state across calls."""

    def __init__(self, target_lineno: int):
        self.target_lineno = target_lineno
        self.applied = False

    def _try_mutate(self, node):
        if self.applied or node.lineno != self.target_lineno:
            return
        for i, d in enumerate(node.args.defaults):
            if isinstance(d, ast.Constant) and d.value is None:
                new_default = ast.List(elts=[], ctx=ast.Load())
                ast.copy_location(new_default, d)
                node.args.defaults[i] = new_default
                self.applied = True
                break

    def visit_FunctionDef(self, node):
        self.generic_visit(node)
        self._try_mutate(node)
        return node

    def visit_AsyncFunctionDef(self, node):
        self.generic_visit(node)
        self._try_mutate(node)
        return node


class MutationGenerator:
    """Finds every eligible injection site for each bug class in a
    piece of source code, and yields one Mutant per site."""

    def generate(self, source: str) -> list[Mutant]:
        mutants: list[Mutant] = []
        mutants.extend(self._resource_leak_mutants(source))
        mutants.extend(self._swallowed_exception_mutants(source))
        mutants.extend(self._mutable_default_mutants(source))
        return mutants

    def _resource_leak_mutants(self, source: str) -> list[Mutant]:
        original = ast.parse(source)
        target_lines = [
            node.lineno for node in ast.walk(original)
            if isinstance(node, ast.With)
            and len(node.items) == 1
            and _is_open_call(node.items[0].context_expr)
            and isinstance(node.items[0].optional_vars, ast.Name)
        ]
        results = []
        for lineno in target_lines:
            tree_copy = copy.deepcopy(original)
            transformer = _WithToAssignTransformer(lineno)
            mutated = transformer.visit(tree_copy)
            if transformer.applied:
                ast.fix_missing_locations(mutated)
                results.append(Mutant(
                    bug_class="resource_leak",
                    source=ast.unparse(mutated),
                    target_line=lineno,
                    description=f"Removed 'with' context manager around open() at original line {lineno}",
                ))
        return results

    def _swallowed_exception_mutants(self, source: str) -> list[Mutant]:
        original = ast.parse(source)
        target_lines = [
            node.lineno for node in ast.walk(original)
            if isinstance(node, ast.ExceptHandler)
            and not self._is_already_noop(node.body)
        ]
        results = []
        for lineno in target_lines:
            tree_copy = copy.deepcopy(original)
            transformer = _ExceptToPassTransformer(lineno)
            mutated = transformer.visit(tree_copy)
            if transformer.applied:
                ast.fix_missing_locations(mutated)
                results.append(Mutant(
                    bug_class="swallowed_exception",
                    source=ast.unparse(mutated),
                    target_line=lineno,
                    description=f"Replaced except body with 'pass' at original line {lineno}",
                ))
        return results

    def _mutable_default_mutants(self, source: str) -> list[Mutant]:
        original = ast.parse(source)
        target_lines = [
            node.lineno for node in ast.walk(original)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(isinstance(d, ast.Constant) and d.value is None for d in node.args.defaults)
        ]
        results = []
        for lineno in target_lines:
            tree_copy = copy.deepcopy(original)
            transformer = _NoneDefaultToMutableTransformer(lineno)
            mutated = transformer.visit(tree_copy)
            if transformer.applied:
                ast.fix_missing_locations(mutated)
                results.append(Mutant(
                    bug_class="mutable_default",
                    source=ast.unparse(mutated),
                    target_line=lineno,
                    description=f"Changed None default to mutable [] at original line {lineno}",
                ))
        return results

    @staticmethod
    def _is_already_noop(body: list[ast.stmt]) -> bool:
        if not body:
            return True
        return all(
            isinstance(stmt, ast.Pass)
            or (isinstance(stmt, ast.Expr) and isinstance(stmt.value, ast.Constant)
                and stmt.value.value is Ellipsis)
            for stmt in body
        )
