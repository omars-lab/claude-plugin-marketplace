# Wiki spaces — domain partitions bound to PII/confidentiality tolerances

The wiki is **not one graph**. It is split into **spaces**: each space is a self-contained FAQ
dependency graph for one **domain**, bound to one **confidentiality/PII tolerance**. A space is a
compartment — content of one sensitivity never leaks into another through the dependency crawl.

This file is the **rubric** the `manage-wiki` skill reads at run time to route a note to a space
and to gate what may enter it. Sharpen it here; the skill reads it, it does not hard-code the list.

> **No regex for intent** (repo tenet): *Claude* reads a note and decides its space and whether it
> is safe to ingest. The space is a semantic judgment about what the note is *about* and how
> sensitive it is — never a pattern match on a filename or a folder. Scripts only check the
> mechanical compartment boundary (`bin/check_evidence.py`) after Claude has filed things.

## The spaces

Spaces mirror the vault's domain emojis (see the repo `CLAUDE.md`). Each lives at
`Notes/📚 Wiki/<space>/` and is a full FAQ graph (its own `index.md`, its own base/derived
articles). The rows below are examples: the vault's own `@References/spaces.md` lists its real spaces.

| Space (folder) | Domain | Tolerance — what may enter |
|---|---|---|
| `🌐 General` | cross-cutting, non-sensitive | **Public floor.** No PII, no confidential detail. Shareable as-is. This is the *only* space others may build on. |
| `🏢 Work` | current employer | Employer-confidential + colleague PII (names, 1-1s, perf, internal systems). |
| `📦 Past Work` | former employer | Former-employer-confidential + colleague PII. |
| `🏡 Personal` | self + family | Personal/family PII — health, home, finances, minors. The most sensitive personal compartment. |
| `☕️ NaqshCoffee` | coffee business + Islamic design | Business-confidential (strategy, pricing, brand, supplier). |
| `👥 EarlBear` | venture | Venture-confidential. |

The **public floor** is `🌐 General`: the space identified by its name ending in "General". It is the shared base every private space is allowed to build on. Everything else is a **private compartment**.

If a note does not fit any domain, it is *cross-cutting* and, only if it carries no PII/confidential
detail, belongs in `🌐 General`. If it is sensitive but domain-less, keep it in its most specific
private compartment rather than promoting it to General.

## Invariant 1 — no secrets, ever (hard gate, orthogonal to spaces)

A live credential, API key, token, or password **never enters any space**, not even a private one.
Spaces partition *confidentiality of content*, not *secrets*. This is the pre-existing safety gate:
on spotting a secret, stop on that note, name the file and line (never the value), and offer to
redact or quarantine. A private space is not a vault for secrets.

## Invariant 2 — the compartment rule (no cross-space dependency)

An answer may only name prerequisites in:

1. **its own space**, or
2. the **public floor** (`🌐 General`).

A derived answer may **never** build on an answer in a *different private compartment*. This is what
keeps the dependency crawl safe: following any answer's `prerequisites` links down to the base facts can
only ever pass through the answer's own space and General — never through another domain's
confidential content. (Bell–LaPadula-style: read down to the public floor, never sideways into
another compartment.)

Consequences:

- A fact needed by two private spaces, and safe to state publicly, becomes a **base answer in `🌐 General`**; each private space then builds on the General answer. Promote the shared, non-sensitive fact up to the floor rather than linking sideways.
- If a fact is *not* safe for General (it carries the other compartment's confidential detail),
  it may **not** be shared — re-derive it independently within the space that needs it, from that
  space's own raw sources.
- `leads_to:` back-links are the exception in direction only: a `🌐 General` answer may list a
  private answer in its `leads_to:` (the private answer builds up on the floor). That is the same
  allowed edge seen from the base side, not a new one — General still depends on nothing private.
  It is also why the compartment check reads `prerequisites` and not `leads_to`: `prerequisites` is the
  authoritative direction and `leads_to` is its mirror.

`bin/check_evidence.py` enforces the mechanical side of this: it derives each article's space from
its folder, and flags any `prerequisites` edge that points into a different private space.

## `space:` frontmatter

Every wiki article carries `space: <folder name>` in its frontmatter, matching the folder it lives
in. The folder is the real compartment boundary (what the linter trusts); the frontmatter is the
declared value, kept in sync so a reader knows a moved file's intended home. The linter flags a
mismatch.

## Raw notes are not partitioned

The raw inbox (`Notes/🗑️ Unorganized/` and the vault's domain folders) is *not* split into spaces —
it is the immutable source layer. A single raw note may feed base answers in more than one space
(e.g. a meeting note with both a shareable definition and a confidential decision). What is
partitioned is the **compiled wiki**: which space each *answer* is written into, and what it may
depend on. When one raw note feeds two spaces, write two base answers (one per space) grounded in
the same source — do not write one answer that straddles compartments.
