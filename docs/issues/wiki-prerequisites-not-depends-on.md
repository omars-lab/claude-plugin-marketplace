# `depends_on` was named for the wrong question

**Date:** 2026-09-16 · **Shipped in:** wiki-manager 0.10.0

## The contradiction

`references/article.md` said, of `kind:`:

```
kind — base | derived. base = grounded directly in raw notes: fill `sources`, drop `depends_on`.
        derived = built from other answers: fill `depends_on`, drop `sources`.
```

42 pages ignored the "drop" half and carried both keys. Nothing enforced the rule, so nothing
had ever failed — the pages were simply outside a rule no tool checked.

An audit could read that two ways: 42 broken pages, or a broken rule. Looking at one:

```
kind: base                                     <- the facts were read off a raw note
sources:
  - "[[LLM Model consumption]]"
depends_on:                                    <- and you still need this one first
  - "[[How is model availability and resilience handled on Bedrock?]]"
```

Both lines are true. The Guardrails facts *did* come off a raw note, and a newcomer *does* need
the model-availability answer first. Enforcing the rule would have deleted ~30 real reading-order
edges to protect a definition.

## What was actually wrong

The key's **name**. `depends_on` reads as a claim about where a page's content comes from — the
same question `kind:` answers — so the two looked like they had to agree. They don't. They answer
different questions and are independent:

| Key | Question it answers |
|---|---|
| `kind:` + `sources:` | Where did these facts come from? |
| `prerequisites:` | What must a reader already understand? |

Omar's framing, which is what the key is now named for: *"i dont want depends on … i want
'prerequisite' — to understand the answer to this question you must first understand these"*.

## The change

`bin/migrate_prereq_key.py` (`--wiki`, `--check` / `--apply` / `--selftest`) renames the key in
the frontmatter block and nothing else. 42 files, 42 keys, one per page.

It is deliberately the narrowest possible transform — a key line at column 0 inside the **first**
`---` block. Values, ordering, indentation, every other key and the whole body are untouched, so
the migration is edge-neutral by construction, not by luck. A `depends_on:` in body prose (a page
*explaining* the schema) is left alone, because there it is being quoted, not declared.

`leads_to:` keeps its name. It is still the mirror — "these questions name this one as a
prerequisite" — and it already reads as prose rather than as schema.

## Proof nothing moved

- `check_evidence.py --strict` before and after: identical. 23 ungrounded literals; **0** on every
  hard gate (unresolved links, cross-space leaks, space mismatch, legacy body sections, asymmetric
  cross-links).
- Concept map regenerated: **73 articles, 61 edges** — the same 61 as before the rename. If the
  tools had stopped seeing the key the edge count would have gone to zero, so this is the check
  that actually distinguishes "renamed" from "lost".
- Asymmetry staying at 0 is a weaker signal on its own (losing *both* directions also reads as 0),
  which is why the edge count is the one quoted.

## Also changed

The rule that caused this is gone from `references/article.md` and `review-as-newcomer/rubric.md`.
The rubric now states the positive form: `kind` and `prerequisites` are independent, a `base` page
with prerequisites is correct and common, and the reviewer must never "fix" one to match the
other. What remains a real violation is a `base` page listing a wiki **article** in `sources:` —
that is a prerequisite wearing the wrong key.

One existing verdict (`📦 Past Work/Golden Path/What is context engineering…`) had raised this exact
contradiction under **Raised, not fixed**. It was right, and this is the answer.
