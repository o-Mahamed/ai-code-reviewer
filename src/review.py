"""
Combined entry point: runs the static analyzer and, unless disabled,
the LLM reviewer against a single file, merges their findings into one
line-sorted report tagged by source. This is the tool as it's meant to
actually be used, rather than running two separate scripts by hand.
"""

from __future__ import annotations

import argparse

from analyzer import analyze_file
from llm_reviewer import LLMReviewer


def review_file(path: str, static_only: bool = False):
    static_findings = analyze_file(path)

    # A syntax error means the file didn't parse at all -- there's
    # nothing meaningful for the LLM layer to add on top of that, and
    # no point spending an API call on it.
    if any(f.bug_class == "syntax_error" for f in static_findings):
        return static_findings, []

    llm_findings = []
    if not static_only:
        source = open(path, encoding="utf-8").read()
        reviewer = LLMReviewer()
        llm_findings = reviewer.review(source, static_findings=static_findings)

    return static_findings, llm_findings


def main():
    parser = argparse.ArgumentParser(description="Combined static + LLM code review")
    parser.add_argument("path", help="Python file to review")
    parser.add_argument(
        "--static-only", action="store_true",
        help="Skip the LLM review layer (faster, free, no API key needed)",
    )
    args = parser.parse_args()

    static_findings, llm_findings = review_file(args.path, static_only=args.static_only)

    tagged = [("static", f) for f in static_findings] + [("llm", f) for f in llm_findings]
    tagged.sort(key=lambda pair: pair[1].line)

    if not tagged:
        print(f"No issues found in {args.path}")
        return

    print(f"Found {len(tagged)} issue(s) in {args.path}:\n")
    for source, f in tagged:
        print(f"  L{f.line:<4} [{f.severity:<6}] [{source:<6}] {f.bug_class}: {f.message}")


if __name__ == "__main__":
    main()
