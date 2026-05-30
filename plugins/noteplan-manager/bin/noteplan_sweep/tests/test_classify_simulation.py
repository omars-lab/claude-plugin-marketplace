"""
test_classify_simulation.py — Pure-Python equivalents of the JS classification engine.

Mirrors the logic in sweep_review.py's JS template so edge cases can be tested
without Playwright/Chromium. When a JS bug is found, add a simulation test here
first to confirm the expected behavior, then add the Playwright regression in
test_sweep_review_js.py.

Functions ported:
  norm_line         ← normLine
  body_text         ← bodyText
  is_noise_line     ← isNoiseLine
  classify_dest_lines ← classifyDestLines
  filter_valid_pairs  ← filterValidPairs
  countable_removed   ← removedLines.filter(l => normLine(l).length > 2 && !isNoiseLine(l))
"""

import re
import pytest


# ---------------------------------------------------------------------------
# Python equivalents of JS classification primitives
# ---------------------------------------------------------------------------

def norm_line(s: str) -> str:
    """normLine: strip due dates, hashtag-tags, collapse whitespace, lowercase."""
    s = re.sub(r'>\d{4}-\d{2}-\d{2}', '', s)
    s = re.sub(r'#\w+', '', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip().lower()


def body_text(s: str) -> str:
    """bodyText: strip task checkbox prefix from a (already-normed) line."""
    return re.sub(r'^[-*]\s*\[[x ]\]\s*', '', s, flags=re.IGNORECASE).strip()


def is_noise_line(line: str) -> bool:
    """isNoiseLine: headings, code fences, horizontal rules, bare empty checkboxes."""
    stripped = line.strip()
    if re.match(r'^#+\s', stripped):
        return True
    n = norm_line(line)
    if len(n) <= 3:
        return True
    if re.match(r'^`+(\w*)$', n):
        return True
    if re.match(r'^-{2,}$', n) or re.match(r'^—{1,}$', n):
        return True
    if re.match(r'^[-*]\s*\[\s*\]\s*$', n):
        return True
    return False


def token_jaccard(a: str, b: str) -> float:
    """Token Jaccard similarity between two strings (already normed/body-text)."""
    ta = set(w for w in a.split() if len(w) >= 3)
    tb = set(w for w in b.split() if len(w) >= 3)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def classify_dest_lines(removed_lines: list[str], added_lines: list[str]) -> dict:
    """
    classifyDestLines: match added lines against removed lines.

    Returns:
        {
          "moved":      [destLine, ...],        # added lines that matched a removed line
          "new_content":[destLine, ...],         # added lines with no source match
          "moved_pairs": {destLine: srcLine},    # dest→src mapping
        }
    """
    # Build entries with origIdx so matchIdx maps back correctly (fixes index-skew bug)
    removed_entries = []
    for orig_idx, line in enumerate(removed_lines):
        n = norm_line(line)
        b = body_text(n)
        if len(n) > 3 and not is_noise_line(line):
            removed_entries.append({"line": line, "n": n, "b": b, "orig_idx": orig_idx})

    moved = []
    new_content = []
    moved_pairs = {}

    for dest_line in added_lines:
        n = norm_line(dest_line)
        if not n or len(n) <= 2:
            continue
        nb = body_text(n)

        match_idx = None
        for i, entry in enumerate(removed_entries):
            en, eb = entry["n"], entry["b"]
            # Exact norm match
            if n == en:
                match_idx = i
                break
            # Prefix match on norm (up to 50 chars, min 10)
            p_len = min(50, min(len(n), len(en)))
            if p_len >= 10 and (n.startswith(en[:p_len]) or en.startswith(n[:p_len])):
                match_idx = i
                break
            # Body-text prefix match (strips checkbox, min 8 chars)
            if not eb or len(eb) < 8 or len(nb) < 8:
                pass
            else:
                b_len = min(40, min(len(nb), len(eb)))
                if b_len >= 8 and (nb.startswith(eb[:b_len]) or eb.startswith(nb[:b_len])):
                    match_idx = i
                    break
            # 4th tier: Token Jaccard (handles reworded lines with shared key terms)
            # Gate: both sides ≥ 3 meaningful tokens; score ≥ 0.5
            if token_jaccard(nb, eb) >= 0.5 and len([w for w in nb.split() if len(w) >= 3]) >= 3:
                match_idx = i
                break

        if match_idx is not None:
            moved.append(dest_line)
            moved_pairs[dest_line] = removed_entries[match_idx]["line"]
            # One-to-one: consume so same source can't double-match
            removed_entries.pop(match_idx)
        else:
            new_content.append(dest_line)

    return {"moved": moved, "new_content": new_content, "moved_pairs": moved_pairs}


def filter_valid_pairs(moved: list[str], moved_pairs: dict, removed_lines: list[str]) -> list[str]:
    """
    filterValidPairs: reject pairs where srcLine isn't in removedLines or norm-match fails.
    Mirrors the JS validation pass that prevents phantom moved counts.
    """
    removed_set = set(removed_lines)
    valid = []
    for dest_line in moved:
        src_line = moved_pairs.get(dest_line)
        if not src_line or src_line not in removed_set:
            continue
        if is_noise_line(src_line) or is_noise_line(dest_line):
            continue
        dn, sn = norm_line(dest_line), norm_line(src_line)
        if len(dn) <= 2 or len(sn) <= 2:
            continue
        db, sb = body_text(dn), body_text(sn)
        p_len = min(50, min(len(dn), len(sn)))
        b_len = min(40, min(len(db), len(sb)))
        jaccard_ok = (
            token_jaccard(db, sb) >= 0.5 and
            len([w for w in db.split() if len(w) >= 3]) >= 3
        )
        if (dn == sn or
                (p_len >= 10 and (dn.startswith(sn[:p_len]) or sn.startswith(dn[:p_len]))) or
                (len(sb) >= 8 and len(db) >= 8 and b_len >= 8 and
                 (db.startswith(sb[:b_len]) or sb.startswith(db[:b_len]))) or
                jaccard_ok):
            valid.append(dest_line)
    return valid


def countable_removed(removed_lines: list[str]) -> list[str]:
    """Lines that count toward lostCount: non-noise, norm length > 2."""
    return [l for l in removed_lines if len(norm_line(l)) > 2 and not is_noise_line(l)]


# ---------------------------------------------------------------------------
# Helper to compute the final counts the same way classifyRow does
# ---------------------------------------------------------------------------

def classify_row(removed_lines: list[str], added_lines: list[str]) -> dict:
    """
    Runs the full pipeline: classify → filterValidPairs → compute counts.
    Returns {type, moved_count, lost_count, new_count}.
    """
    result = classify_dest_lines(removed_lines, added_lines)
    moved = result["moved"]
    moved_pairs = result["moved_pairs"]
    new_content = result["new_content"]

    valid_moved = filter_valid_pairs(moved, moved_pairs, removed_lines)
    countable = countable_removed(removed_lines)
    moved_count = len(valid_moved)
    total = len(countable)
    lost_count = max(0, total - moved_count)
    true_new = [l for l in new_content if len(norm_line(l)) > 2 and not is_noise_line(l)]
    new_count = len(true_new)

    if total == 0 and new_count == 0:
        row_type = "empty"
    elif moved_count > 0 and lost_count == 0:
        row_type = "move"
    elif moved_count == 0 and total > 0:
        row_type = "lost"
    elif moved_count > 0 and lost_count > 0:
        row_type = "lost"  # compound: blocks carry the move+lost split
    elif new_count > 0 and moved_count == 0 and total == 0:
        row_type = "anomaly"
    else:
        row_type = "partial"

    blocks = []
    if moved_count > 0: blocks.append({"type": "move", "count": moved_count})
    if lost_count > 0:  blocks.append({"type": "lost",  "count": lost_count})

    return {
        "type": row_type,
        "blocks": blocks,
        "moved_count": moved_count,
        "lost_count": lost_count,
        "new_count": new_count,
    }


# ---------------------------------------------------------------------------
# norm_line tests
# ---------------------------------------------------------------------------

def test_norm_strips_due_date():
    assert norm_line("- [ ] Do the thing >2026-04-21") == "- [ ] do the thing"

def test_norm_strips_hashtag():
    assert norm_line("- [ ] Do the thing #work") == "- [ ] do the thing"

def test_norm_collapses_whitespace():
    assert norm_line("  a    b  ") == "a b"

def test_norm_lowercases():
    assert norm_line("HELLO WORLD") == "hello world"


# ---------------------------------------------------------------------------
# is_noise_line tests
# ---------------------------------------------------------------------------

def test_noise_heading():
    assert is_noise_line("## Some heading")
    assert is_noise_line("# Top")

def test_noise_code_fence():
    assert is_noise_line("```python")
    assert is_noise_line("```")

def test_noise_horizontal_rule():
    assert is_noise_line("---")
    assert is_noise_line("----")

def test_noise_bare_empty_checkbox():
    assert is_noise_line("- [ ]")
    assert is_noise_line("* [ ]")

def test_noise_short_norm():
    assert is_noise_line("ok")   # len("ok") == 2 ≤ 3

def test_not_noise_task():
    assert not is_noise_line("- [ ] Do the thing")

def test_not_noise_plain_text():
    assert not is_noise_line("This is a real content line")


# ---------------------------------------------------------------------------
# classify_dest_lines — core cases
# ---------------------------------------------------------------------------

def test_exact_match():
    removed = ["- [ ] Do the thing"]
    added   = ["- [ ] Do the thing"]
    r = classify_dest_lines(removed, added)
    assert r["moved"] == ["- [ ] Do the thing"]
    assert r["new_content"] == []


def test_due_date_stripped_match():
    """Line moved to plan with a due date appended — normLine strips it so it still matches."""
    removed = ["- [ ] Make a coffee cup animation"]
    added   = ["- [ ] Make a coffee cup animation  >2026-04-26"]
    r = classify_dest_lines(removed, added)
    assert len(r["moved"]) == 1
    assert r["moved_pairs"][added[0]] == removed[0]


def test_body_text_match_strips_checkbox():
    """Source has unchecked box, dest has checked — body text matches."""
    removed = ["- [ ] Review the docs carefully"]
    added   = ["- [x] Review the docs carefully"]
    r = classify_dest_lines(removed, added)
    assert len(r["moved"]) == 1


def test_prefix_match_truncated_line():
    """Dest line is a prefix of source (longer content trimmed at plan level)."""
    src = "- [ ] Set up CI/CD pipeline with GitHub Actions and run tests"
    dst = "- [ ] Set up CI/CD pipeline with GitHub Actions"
    r = classify_dest_lines([src], [dst])
    assert len(r["moved"]) == 1


def test_unrelated_line_is_new():
    removed = ["- [ ] Fix the login bug"]
    added   = ["- [ ] Deploy to staging"]
    r = classify_dest_lines(removed, added)
    assert r["moved"] == []
    assert r["new_content"] == ["- [ ] Deploy to staging"]


def test_noise_lines_not_matched():
    """Section headers in removedLines are excluded from matching pool."""
    removed = ["## Config Agent ARB", "- [ ] Real task here"]
    added   = ["## Config Agent ARB", "- [ ] Real task here"]
    r = classify_dest_lines(removed, added)
    # Header should not be in moved (it's noise)
    assert "## Config Agent ARB" not in r["moved"]
    assert "- [ ] Real task here" in r["moved"]


def test_empty_added_lines_skipped():
    """Blank/empty added lines are not counted as new content."""
    removed = ["- [ ] Task A"]
    added   = ["", "   ", "- [ ] Task A"]
    r = classify_dest_lines(removed, added)
    assert len(r["moved"]) == 1
    assert r["new_content"] == []


# ---------------------------------------------------------------------------
# One-to-one matching (double-match prevention)
# ---------------------------------------------------------------------------

def test_one_to_one_prevents_double_count():
    """
    Two similar dest lines should not both match the same single source line.
    The second dest line must go to new_content after the source is consumed.
    This is the bug that caused negative lostCount (movedCount > countableRemoved).
    """
    src = "- [ ] Do goals for Jeff"
    dst1 = "- [ ] Do goals for Jeff"       # exact match → moved, source consumed
    dst2 = "- [ ] Do goals for Jef"        # typo variant — same prefix, but source gone
    r = classify_dest_lines([src], [dst1, dst2])
    assert dst1 in r["moved"]
    assert dst2 in r["new_content"], "Typo variant must not double-match consumed source"
    assert len(r["moved"]) == 1


def test_two_sources_two_dests_one_to_one():
    """Two source lines, two distinct dest lines — each should match its own source."""
    src1 = "- [ ] Task Alpha with detail"
    src2 = "- [ ] Task Beta with detail"
    dst1 = "- [ ] Task Alpha with detail >2026-04-30"
    dst2 = "- [ ] Task Beta with detail >2026-04-30"
    r = classify_dest_lines([src1, src2], [dst1, dst2])
    assert len(r["moved"]) == 2
    assert r["moved_pairs"][dst1] == src1
    assert r["moved_pairs"][dst2] == src2


# ---------------------------------------------------------------------------
# classify_row — end-to-end type classification
# ---------------------------------------------------------------------------

def test_classify_row_move():
    removed = ["- [ ] Task A is a long enough line", "- [ ] Task B is a long enough line"]
    added   = [l + " >2026-04-30" for l in removed]
    result = classify_row(removed, added)
    assert result["type"] == "move"
    assert result["lost_count"] == 0
    assert result["moved_count"] == 2


def test_classify_row_lost():
    removed = ["- [ ] Task that never arrived in destination"]
    added   = []
    result = classify_row(removed, added)
    assert result["type"] == "lost"
    assert result["lost_count"] == 1
    assert result["moved_count"] == 0


def test_classify_row_mixed():
    src1 = "- [ ] Task that moved successfully to destination"
    src2 = "- [ ] Task that got lost in the sweep"
    removed = [src1, src2]
    added   = [src1 + " >2026-04-30"]   # only src1 moved
    result = classify_row(removed, added)
    assert result["type"] == "lost"   # compound: blocks carry move+lost detail
    assert result["moved_count"] == 1
    assert result["lost_count"] == 1
    assert any(b["type"] == "move" for b in result["blocks"])
    assert any(b["type"] == "lost" for b in result["blocks"])


def test_classify_row_anomaly():
    """No source removed, but additions exist — pure anomaly."""
    removed = []
    added   = ["- [ ] Mystery line appeared in destination"]
    result = classify_row(removed, added)
    assert result["type"] == "anomaly"
    assert result["new_count"] == 1


def test_classify_row_empty():
    """No removed lines, no meaningful additions."""
    removed = ["## Just a heading"]  # noise only
    added   = []
    result = classify_row(removed, added)
    assert result["type"] == "empty"


def test_classify_row_noise_lines_not_lost():
    """Noise lines (headings, separators) don't count toward lostCount."""
    removed = ["## Section Header", "---", "- [ ] Real task here long enough"]
    added   = ["- [ ] Real task here long enough >2026-04-30"]
    result = classify_row(removed, added)
    assert result["type"] == "move"
    assert result["lost_count"] == 0


# ---------------------------------------------------------------------------
# filter_valid_pairs
# ---------------------------------------------------------------------------

def test_filter_rejects_phantom_src():
    """srcLine not in removedLines → rejected as phantom."""
    dest_line = "- [ ] Real destination line here"
    fake_src  = "- [ ] Phantom line not in source"
    moved = [dest_line]
    pairs = {dest_line: fake_src}
    removed = ["- [ ] Different line"]
    valid = filter_valid_pairs(moved, pairs, removed)
    assert valid == []


def test_filter_rejects_noise_src():
    """Pairs where srcLine is noise are rejected."""
    dest_line = "- [ ] Some task line here"
    noise_src = "## Section heading"
    moved = [dest_line]
    pairs = {dest_line: noise_src}
    removed = [noise_src]
    valid = filter_valid_pairs(moved, pairs, removed)
    assert valid == []


def test_filter_accepts_valid_pair():
    src = "- [ ] Deploy the agent to production environment"
    dst = "- [ ] Deploy the agent to production environment >2026-05-01"
    moved = [dst]
    pairs = {dst: src}
    removed = [src]
    valid = filter_valid_pairs(moved, pairs, removed)
    assert valid == [dst]


# ---------------------------------------------------------------------------
# countable_removed
# ---------------------------------------------------------------------------

def test_countable_excludes_noise():
    lines = ["## Heading", "- [ ] Real task line here", "---", "- [ ]", "Short"]
    countable = countable_removed(lines)
    assert "## Heading" not in countable
    assert "---" not in countable
    assert "- [ ]" not in countable
    assert "- [ ] Real task line here" in countable


def test_countable_excludes_short_norms():
    lines = ["ok", "hi", "- [ ] Substantial content line here"]
    countable = countable_removed(lines)
    assert len(countable) == 1


# ---------------------------------------------------------------------------
# Token Jaccard similarity (#83)
# ---------------------------------------------------------------------------

def test_token_jaccard_reword_matches():
    """A meaningfully reworded line scores as moved via Jaccard 4th tier."""
    src  = "- [ ] Set up monitoring alerts for production services"
    dest = "- [ ] Configure production monitoring alerts and services"
    result = classify_dest_lines([src], [dest])
    assert dest in result["moved"], "reworded line should be matched by Jaccard tier"
    assert result["moved_pairs"][dest] == src


def test_token_jaccard_unrelated_no_match():
    """Completely unrelated lines do not cross-match via Jaccard."""
    src  = "- [ ] Fix the login timeout bug in the auth service"
    dest = "- [ ] Update the dependency versions in package.json"
    result = classify_dest_lines([src], [dest])
    assert dest not in result["moved"], "unrelated line should NOT match via Jaccard"
    assert dest in result["new_content"]


def test_token_jaccard_gate_min_tokens():
    """Jaccard does not match when either side has fewer than 3 meaningful tokens."""
    src  = "- [ ] CI pipeline"   # only 2 tokens ≥ 3 chars: "pipeline", no wait...
    # "CI" is 2 chars (excluded), "pipeline" is 8 chars → only 1 token ≥ 3 chars
    dest = "- [ ] Set up CI pipeline"
    result = classify_dest_lines([src], [dest])
    # "pipeline" alone doesn't hit ≥ 3 token gate → should fall through to new_content
    assert dest not in result["moved"]


def test_token_jaccard_filter_valid_pairs_accepts():
    """filterValidPairs accepts a Jaccard-matched pair."""
    src  = "- [ ] Set up monitoring alerts for production services"
    dest = "- [ ] Configure production monitoring alerts and services"
    moved = [dest]
    pairs = {dest: src}
    valid = filter_valid_pairs(moved, pairs, [src])
    assert dest in valid, "Jaccard pair should pass filterValidPairs"


def test_token_jaccard_does_not_run_before_prefix():
    """Prefix match takes priority — Jaccard runs only as a 4th tier fallback."""
    src  = "- [ ] Deploy the application to staging environment now"
    dest = "- [ ] Deploy the application to staging environment today"
    # These share a 10-char prefix match — should match via tier 2, not Jaccard
    result = classify_dest_lines([src], [dest])
    assert dest in result["moved"]
    assert result["moved_pairs"][dest] == src
