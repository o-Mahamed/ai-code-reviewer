# AI Code Reviewer

A code review tool that combines deterministic static analysis with an
LLM review layer, validated with a mutation testing methodology instead
of shipped as an unvalidated demo.

## Quick start

```bash
pip install -r requirements.txt
echo 'OPENAI_API_KEY=your-key-here' > .env

python3 src/review.py path/to/file.py
```

This runs both the static analyzer and the LLM reviewer against a
single file and prints a merged, line-sorted report tagged by source:

```
Found 2 issue(s) in path/to/file.py:

  L5    [medium] [static] resource_leak: open() call is not inside a 'with' block...
  L20   [high]   [llm]    logic_error: off-by-one in pagination offset calculation...
```

Use `--static-only` to skip the LLM call entirely. Useful for fast,
free iteration, or in CI where you don't want per-run API cost.

## Why mutation testing

Most "AI code review" projects stop at "it runs on a demo file." This
one doesn't trust itself by default. Instead of hand-picking a few
examples, `eval/harness.py` programmatically injects known bugs into
real code and measures what percentage actually gets caught, and
whether the tool stays quiet on code it shouldn't flag.

## Results (against the real requests library)

Running `eval/harness.py` against [psf/requests](https://github.com/psf/requests):

| Bug class | Caught | Recall |
|---|---|---|
| `mutable_default` | 33/33 | 100% |
| `swallowed_exception` | 53/60 | 88.3% |
| **Overall** | **86/93** | **92.5%** |

Baseline false positives on real, un-mutated code: **4**, down from 6
before a targeted fix. See [LIMITATIONS.md](LIMITATIONS.md) for details.

### A real, tested limitation

The 7 missed mutants all share one shape: `except ImportError: pass`
wrapping a real import, mutated from code that used to do something
useful. This is structurally identical to the standard, legitimate
"optional dependency" idiom, identical enough that it's undecidable
from a single file snapshot, not just hard.

This wasn't left as a guess. The LLM layer was tested directly against
these exact 7 cases, with no static findings given as a hint, and it
caught 0 of them. That confirms this isn't a static analysis weakness
an LLM happens to patch over. It's a missing information problem
neither approach can solve without seeing a diff. Full writeup in
[LIMITATIONS.md](LIMITATIONS.md), test in `eval/test_llm_on_missed.py`.

## Architecture

```
src/
  detectors/          # 3 AST-based static detectors
    resource_leak.py       # open() without a 'with' block or .close()
    swallowed_exception.py # except body that's just pass/...
    mutable_default.py     # def f(x=[]) shared-state gotcha
  analyzer.py          # runs all static detectors over a file
  mutate.py            # mutation generator, ground truth for eval
  llm_reviewer.py       # LLM review layer (OpenAI, structured outputs)
  review.py             # combined entry point: static + LLM merged

eval/
  harness.py                 # mutation testing eval harness
  test_llm_on_missed.py       # targeted test: does the LLM catch what static analysis misses?
  results/                    # saved eval run outputs (JSON)

tests/
  test_detectors.py     # unit tests for each static detector
  test_harness.py        # regression test for the harness's own counting logic
  fixtures/               # hand-crafted known-bug and known-safe test files
```

## Known limitations

See [LIMITATIONS.md](LIMITATIONS.md) for the full list, including:
- The fundamental single-snapshot-vs-diff issue above
- `swallowed_exception`'s narrow scope. It only recognizes the literal
  `import` idiom, not `importlib.import_module` or non-import fallback
  patterns like `except StopIteration: pass`
- `resource_leak`'s per-function scoping, which won't catch a resource
  opened in one method and closed in another

## Future work

The single-snapshot limitation points directly at the next real
extension: reviewing a diff instead of a whole file. A diff would show
exactly the missing signal, that an except body used to do something
and now does nothing, which would likely close the 7-mutant gap for
both the static and LLM layers. Not yet built. Documented here as the
known next step rather than left unstated.
