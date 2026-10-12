# Verdict freshness: content hash, not mtime

**Status:** resolved — shipped in wiki-manager 0.6.0
**Affects:** `plugins/wiki-manager/bin/check_verdicts.py`, `hooks/wiki-verdict-hook.py`

## What the plan called for

The approved plan said the verdict Stop hook should "reuse today's mtime-guard lesson from
`wiki-concept-hook.py` (compare page mtime vs verdict mtime) + content-hash dedup TTL so it never
re-fires in a loop."

## Why that was the wrong mechanism

The mtime guard in `wiki-concept-hook.py` exists to work around a *missing* fact. The concept map
has no record of what it was generated from, so the only available question is "was the map
touched after the article was?" That question has well-known failure modes, and we had just spent a
session fixing them: the map is regenerated and the nudge fires anyway because the filesystem
recorded the two writes in an unhelpful order; NotePlan's own sync rewrites a file and resets its
mtime; a `git checkout` sets every mtime to now. Hence the TTL, the dedup file, and the earlier bug
where the hook fired on every Stop.

A verdict is not in that position. It *does* record what it was written from. So the question can
be the direct one — "is this verdict about the bytes that are in the article right now?" — instead
of a proxy for it.

## What we did instead

Each verdict stores `page_hash`: the first 12 hex of the sha256 of the whole article file, with
CRLF normalized to LF. The whole file, frontmatter included, because a changed `depends_on`, space
or title changes what a newcomer reads as much as a rewritten paragraph does. Newlines are
normalized so an editor rewriting line endings is not mistaken for a content change.

The consequences are structural rather than tuned:

- Editing a page makes its verdict stale **by construction**. Nothing has to notice the edit.
- Rewriting the verdict makes it fresh **by construction**. The nudge stops because the condition
  it tests is now false, not because a TTL expired or a dedup key matched.
- There is no clock, no touch-ordering dependency, and nothing to re-fire. `git checkout`,
  NotePlan sync and out-of-order writes are all invisible to it.

`check_verdicts.py --hash <file>` is the *single definition* of the hash. The skill calls it to
write the value, the validator calls it to compare, and the Stop hook imports `page_hash` from the
same module. Three consumers, one definition — they cannot drift into disagreeing about whether a
page changed.

The hook's selftest asserts the mtime-proofing directly: it touches an article to a future mtime
with unchanged content and asserts silence.

## Takeaway

An mtime comparison is what you reach for when the derived artifact does not know its own input.
When you are designing the artifact, give it that knowledge instead — the freshness check then
falls out for free and cannot be defeated by the filesystem.
