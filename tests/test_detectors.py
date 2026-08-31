import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from analyzer import analyze_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_buggy_file_catches_all_three_bug_classes():
    findings = analyze_file(str(FIXTURES / "buggy.py"))
    bug_classes = {f.bug_class for f in findings}
    assert bug_classes == {"resource_leak", "swallowed_exception", "mutable_default"}


def test_buggy_file_flags_exact_lines():
    findings = analyze_file(str(FIXTURES / "buggy.py"))
    flagged_lines = {f.line for f in findings}
    # line 5: leaky open(), line 25: swallowed except, line 37: mutable default
    assert {5, 25, 37}.issubset(flagged_lines)


def test_clean_file_has_zero_findings():
    findings = analyze_file(str(FIXTURES / "clean.py"))
    assert findings == []


def test_safe_patterns_in_buggy_file_are_not_flagged():
    # buggy.py also contains safe versions of each pattern right next to
    # the buggy ones -- this specifically guards against a detector that's
    # too aggressive and flags everything.
    findings = analyze_file(str(FIXTURES / "buggy.py"))
    flagged_lines = {f.line for f in findings}
    # load_config_safe (line 11) and load_config_manual_close (line 16)
    # should never appear
    assert 11 not in flagged_lines
    assert 16 not in flagged_lines
