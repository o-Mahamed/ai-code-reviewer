"""
LLM-based code review layer. Takes source code (optionally alongside
static analysis findings for context) and asks an LLM to find
additional real bugs, returning structured, schema-validated findings
via OpenAI's structured outputs (chat.completions.parse) -- the
response is validated against our Pydantic schema, so there's no
manual JSON parsing or retry-on-malformed-output logic needed.
"""

from __future__ import annotations

import os
from typing import Literal

from dotenv import load_dotenv
from openai import OpenAI
from pydantic import BaseModel

from detectors.base import Finding

load_dotenv()

MODEL = "gpt-5.6-terra"

SYSTEM_PROMPT = """You are a precise code reviewer. You will be shown a \
Python file, optionally with a list of findings a static analyzer already \
flagged. Your job is to find additional real bugs the static analyzer \
would not catch -- logic errors, incorrect assumptions, edge cases, \
security issues, or misuse of APIs.

Rules:
- Only report bugs you are genuinely confident about. If nothing is wrong, \
return an empty findings list -- do not invent issues to seem thorough.
- Do not re-report anything already in the static analyzer's findings list.
- For each bug, give the exact line number, a short bug_class label, a \
severity, a confidence score between 0 and 1, and a one-sentence \
explanation a developer could act on immediately.
"""


class ReviewFinding(BaseModel):
    line: int
    bug_class: str
    severity: Literal["low", "medium", "high"]
    confidence: float
    explanation: str


class ReviewResult(BaseModel):
    findings: list[ReviewFinding]


class LLMReviewer:
    def __init__(self, api_key: str | None = None):
        self.client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))

    def review(self, source: str, static_findings: list[Finding] | None = None) -> list[Finding]:
        static_context = ""
        if static_findings:
            lines = "\n".join(
                f"- L{f.line} [{f.bug_class}] {f.message}" for f in static_findings
            )
            static_context = f"\n\nStatic analyzer already flagged:\n{lines}"

        user_content = f"Review this Python file:\n\n```python\n{source}\n```{static_context}"

        completion = self.client.chat.completions.parse(
            model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_content},
            ],
            response_format=ReviewResult,
        )

        message = completion.choices[0].message
        if message.refusal:
            print(f"Model refused: {message.refusal}")
            return []

        result = message.parsed
        return [
            Finding(
                bug_class=f"llm:{rf.bug_class}",
                line=rf.line,
                message=rf.explanation,
                severity=rf.severity,
                confidence=rf.confidence,
            )
            for rf in result.findings
        ]


if __name__ == "__main__":
    import sys
    reviewer = LLMReviewer()
    source = open(sys.argv[1]).read()
    findings = reviewer.review(source)
    if not findings:
        print("No additional findings from the LLM layer.")
    for f in findings:
        print(f"L{f.line} [{f.severity}] (confidence {f.confidence}) {f.bug_class}: {f.message}")
