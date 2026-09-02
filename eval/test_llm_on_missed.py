"""
Targeted test: does the LLM review layer catch the exact mutants the
static analyzer missed? Reads the missed_details from a saved eval
harness JSON result, regenerates those exact mutants, and runs the LLM
reviewer against each one -- with NO static findings passed as
context, since the point is testing whether the LLM alone closes the
gap static analysis structurally cannot.

Usage:
    python3 eval/test_llm_on_missed.py eval/results/requests_baseline.json /tmp/requests-src/src/requests
"""

from __future__ import annotations

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from mutate import MutationGenerator
from llm_reviewer import LLMReviewer


def main():
    results_path = sys.argv[1]
    package_dir = sys.argv[2]

    with open(results_path) as f:
        results = json.load(f)

    missed = results["missed_details"]
    if not missed:
        print("No missed mutants in this results file -- nothing to test.")
        return

    generator = MutationGenerator()
    reviewer = LLMReviewer()

    caught_by_llm = 0
    for m in missed:
        fname, lineno, bug_class = m["file"], m["original_line"], m["bug_class"]
        source = open(os.path.join(package_dir, fname), encoding="utf-8").read()
        mutants = generator.generate(source)
        match = [x for x in mutants if x.bug_class == bug_class and x.target_line == lineno]

        if not match:
            print(f"{fname} L{lineno}: could not regenerate mutant, skipping")
            continue

        mutant = match[0]
        # No static_findings passed -- we already know static analysis
        # missed this one. We want to know if the LLM alone catches it.
        llm_findings = reviewer.review(mutant.source)

        # The LLM won't use our exact bug_class label, so we just check
        # whether it flagged *anything* near the mutated line.
        nearby = [f for f in llm_findings if abs(f.line - lineno) <= 2]

        if nearby:
            caught_by_llm += 1
            print(f"{fname} L{lineno}: CAUGHT by LLM")
            for f in nearby:
                print(f"    -> {f.bug_class} (confidence {f.confidence}): {f.message}")
        else:
            print(f"{fname} L{lineno}: still MISSED by LLM too")

    print(f"\n{caught_by_llm}/{len(missed)} static-analysis misses caught by the LLM layer")


if __name__ == "__main__":
    main()
