"""
Runs the full set of static detectors over a Python source file and
prints or returns the findings. This is the entry point both for
manual use and for the eval harness we'll build next.
"""

from __future__ import annotations

import argparse
import ast
from pathlib import Path

from detectors.base import Finding
from detectors.resource_leak import ResourceLeakDetector
from detectors.swallowed_exception import SwallowedExceptionDetector
from detectors.mutable_default import MutableDefaultDetector

ALL_DETECTORS = [
    ResourceLeakDetector(),
    SwallowedExceptionDetector(),
    MutableDefaultDetector(),
]


def analyze_source(source: str) -> list[Finding]:
    try:
        tree = ast.parse(source)
    except SyntaxError as e:
        # A syntax error means we can't analyze it -- surface it as a
        # finding rather than crashing, since the eval harness will run
        # this over hundreds of generated mutants unattended.
        return [
            Finding(
                bug_class="syntax_error",
                line=e.lineno or 1,
                message=f"Could not parse file: {e.msg}",
                severity="high",
            )
        ]

    lines = source.splitlines()
    findings: list[Finding] = []
    for detector in ALL_DETECTORS:
        findings.extend(detector.check(tree, lines))
    return sorted(findings, key=lambda f: f.line)


def analyze_file(path: str) -> list[Finding]:
    source = Path(path).read_text()
    return analyze_source(source)


def main():
    parser = argparse.ArgumentParser(description="Static bug detector")
    parser.add_argument("path", help="Python file to analyze")
    args = parser.parse_args()

    findings = analyze_file(args.path)
    if not findings:
        print(f"No issues found in {args.path}")
        return

    print(f"Found {len(findings)} issue(s) in {args.path}:\n")
    for f in findings:
        print(f"  L{f.line:<4} [{f.severity:<6}] {f.bug_class}: {f.message}")


if __name__ == "__main__":
    main()
