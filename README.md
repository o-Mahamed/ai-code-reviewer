# AI Code Reviewer

A code review tool that combines deterministic static analysis with an
LLM review layer, validated against a mutation-testing eval harness —
not just a demo, a tool with measured precision/recall.

## Why mutation testing

Instead of hand-picking a few examples to show off, this project
programmatically injects known bugs into real code, runs the reviewer
against them, and measures exactly what percentage it catches.

## Status

Work in progress. See commit history for build order.
