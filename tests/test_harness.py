"""
Tests the eval harness's counting/aggregation logic against a tiny
synthetic package where every expected number was hand-computed BEFORE
running the harness, not derived from its output after the fact.

This exists because every recall/precision number this project claims
comes from harness.py's counting logic -- if that logic has a bug (an
off-by-one, a double-count, a miscategorized bug class), every number
downstream is wrong even if every detector is perfect. This is the
test that catches that class of bug.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "eval"))
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from harness import run_eval

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mini_package"


def test_harness_matches_hand_computed_totals():
    # Hand-computed before ever running the harness against this fixture:
    # file_a.py has 1 resource_leak site (caught), 1 swallowed_exception
    # site catching ValueError with real handling (caught), and 1
    # swallowed_exception site catching ImportError around a real import
    # (missed -- this is the known, proven-undetectable ambiguity).
    # file_b.py has 2 clean mutable_default sites (both caught).
    result = run_eval(str(FIXTURE_DIR))

    assert result.total_mutants == 5
    assert result.caught == 4
    assert result.missed == 1
    assert result.recall == 0.8
    assert result.baseline_false_positives == 0


def test_harness_per_bug_class_breakdown():
    result = run_eval(str(FIXTURE_DIR))

    assert result.per_bug_class["resource_leak"]["total"] == 1
    assert result.per_bug_class["resource_leak"]["caught"] == 1

    assert result.per_bug_class["swallowed_exception"]["total"] == 2
    assert result.per_bug_class["swallowed_exception"]["caught"] == 1

    assert result.per_bug_class["mutable_default"]["total"] == 2
    assert result.per_bug_class["mutable_default"]["caught"] == 2


def test_harness_identifies_the_correct_missed_mutant():
    result = run_eval(str(FIXTURE_DIR))

    assert len(result.missed_details) == 1
    missed = result.missed_details[0]
    assert missed["file"] == "file_a.py"
    assert missed["bug_class"] == "swallowed_exception"
