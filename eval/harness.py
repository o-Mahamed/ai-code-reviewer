"""
Mutation-testing eval harness. Points the mutation generator and the
analyzer at every .py file in a target package directory and reports
real precision/recall numbers -- not on a hand-written fixture, but on
whatever real codebase you point it at.

Usage:
    python3 eval/harness.py /path/to/package_dir
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections import defaultdict
from dataclasses import asdict, dataclass

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from analyzer import analyze_source
from mutate import MutationGenerator


@dataclass
class EvalResult:
    total_mutants: int
    caught: int
    missed: int
    recall: float
    baseline_false_positives: int
    per_bug_class: dict
    missed_details: list
    false_positive_details: list


def run_eval(package_dir: str) -> EvalResult:
    generator = MutationGenerator()

    per_class_total = defaultdict(int)
    per_class_caught = defaultdict(int)
    missed_details = []
    false_positive_details = []
    baseline_fp_count = 0
    total_mutants = 0
    total_caught = 0

    py_files = [
        f for f in sorted(os.listdir(package_dir))
        if f.endswith(".py")
    ]

    for fname in py_files:
        path = os.path.join(package_dir, fname)
        try:
            source = open(path, encoding="utf-8").read()
        except (UnicodeDecodeError, OSError) as e:
            print(f"  skipping {fname}: {e}", file=sys.stderr)
            continue

        # --- Precision side: does the analyzer flag real, un-mutated code? ---
        try:
            baseline_findings = [
                f for f in analyze_source(source) if f.bug_class != "syntax_error"
            ]
        except Exception as e:
            print(f"  analyzer crashed on {fname}: {e}", file=sys.stderr)
            continue

        for f in baseline_findings:
            baseline_fp_count += 1
            false_positive_details.append({
                "file": fname, "line": f.line, "bug_class": f.bug_class,
            })

        # --- Recall side: does the analyzer catch mutants we inject? ---
        try:
            mutants = generator.generate(source)
        except Exception as e:
            print(f"  mutation generator crashed on {fname}: {e}", file=sys.stderr)
            continue

        for m in mutants:
            total_mutants += 1
            per_class_total[m.bug_class] += 1
            try:
                mutant_findings = analyze_source(m.source)
            except Exception as e:
                print(f"  analyzer crashed on a mutant of {fname}: {e}", file=sys.stderr)
                continue

            matched = [f for f in mutant_findings if f.bug_class == m.bug_class]
            if matched:
                total_caught += 1
                per_class_caught[m.bug_class] += 1
            else:
                missed_details.append({
                    "file": fname, "bug_class": m.bug_class,
                    "original_line": m.target_line, "description": m.description,
                })

    per_bug_class = {
        bug_class: {
            "total": per_class_total[bug_class],
            "caught": per_class_caught[bug_class],
            "recall": round(per_class_caught[bug_class] / per_class_total[bug_class], 3)
            if per_class_total[bug_class] else None,
        }
        for bug_class in per_class_total
    }

    return EvalResult(
        total_mutants=total_mutants,
        caught=total_caught,
        missed=total_mutants - total_caught,
        recall=round(total_caught / total_mutants, 3) if total_mutants else 0.0,
        baseline_false_positives=baseline_fp_count,
        per_bug_class=per_bug_class,
        missed_details=missed_details,
        false_positive_details=false_positive_details,
    )


def main():
    parser = argparse.ArgumentParser(description="Mutation-testing eval harness")
    parser.add_argument("package_dir", help="Directory of .py files to evaluate against")
    parser.add_argument("--out", default=None, help="Optional path to write JSON results")
    args = parser.parse_args()

    result = run_eval(args.package_dir)

    print(f"\n{'='*60}")
    print(f"Mutants generated: {result.total_mutants}")
    print(f"Caught:            {result.caught}")
    print(f"Missed:            {result.missed}")
    print(f"Overall recall:    {result.recall:.1%}")
    print(f"Baseline false positives (on real, un-mutated code): {result.baseline_false_positives}")
    print(f"{'='*60}\n")

    print("By bug class:")
    for bug_class, stats in result.per_bug_class.items():
        recall_str = f"{stats['recall']:.1%}" if stats["recall"] is not None else "n/a"
        print(f"  {bug_class:20s} {stats['caught']}/{stats['total']} caught ({recall_str})")

    if result.missed_details:
        print("\nMissed mutants:")
        for m in result.missed_details:
            print(f"  {m['file']} L{m['original_line']} [{m['bug_class']}] {m['description']}")

    if args.out:
        with open(args.out, "w") as f:
            json.dump(asdict(result), f, indent=2)
        print(f"\nFull results written to {args.out}")


if __name__ == "__main__":
    main()
