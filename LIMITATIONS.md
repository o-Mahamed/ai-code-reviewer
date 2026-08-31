# Known limitations

Documented on purpose. An interviewer probing this project will ask
"what does it get wrong?" and a specific, understood limitation is a
much stronger answer than pretending the tool is perfect.

## swallowed_exception: only recognizes the literal import idiom

Running against the real `requests` library surfaced 6 flagged
"swallowed exceptions" that were all actually intentional. One
targeted fix -- recognizing `except ImportError: pass` (or a tuple
containing it) wrapping a try body that contains an actual import
statement, searched recursively since real code nests this inside
`if`/`try` blocks -- brought that down to 4.

The remaining 4 are legitimate patterns outside this rule's scope:
- `importlib.import_module(...)` used instead of a literal `import`
  statement (same idiom, different spelling)
- `except StopIteration: pass` used as a control-flow signal
- `except AttributeError: pass` used for feature detection

Deliberately not chasing these with more special-case rules -- each
one is a different idiom, and an ever-growing pile of exemptions
makes the detector fragile instead of trustworthy. This is exactly
the kind of contextual judgment call ("is this pass intentional given
the surrounding code and comments?") that the planned LLM review
layer is suited for, and pure AST pattern-matching isn't.
