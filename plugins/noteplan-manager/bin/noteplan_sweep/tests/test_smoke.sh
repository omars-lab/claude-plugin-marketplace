#!/usr/bin/env bash
# test_smoke.sh — Smoke tests for noteplan-sweep CLI
#
# Run from the bin/ directory:
#   bash noteplan_sweep/tests/test_smoke.sh
#
# Each test runs in isolation; outer script continues on failure to report all
# results. set -e is used only inside sub-shells where early exit is wanted.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# tests/ is inside noteplan_sweep/, which is inside bin/ — go up two levels for the entrypoint
NOTEPLAN_SWEEP="python3 $(dirname "$(dirname "$SCRIPT_DIR")")/noteplan-sweep"
FIXTURES="$SCRIPT_DIR/fixtures"

PASS=0
FAIL=0
FAILURES=()

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

pass() {
    local name="$1"
    echo "  PASS  $name"
    PASS=$((PASS + 1))
}

fail() {
    local name="$1"
    local reason="$2"
    echo "  FAIL  $name — $reason"
    FAIL=$((FAIL + 1))
    FAILURES+=("$name: $reason")
}

assert_exit() {
    local name="$1"
    local expected="$2"
    local actual="$3"
    if [ "$actual" -eq "$expected" ]; then
        pass "$name"
    else
        fail "$name" "expected exit $expected, got $actual"
    fi
}

assert_contains() {
    local name="$1"
    local needle="$2"
    local haystack="$3"
    if echo "$haystack" | grep -qF -- "$needle"; then
        pass "$name"
    else
        fail "$name" "output did not contain: $needle"
        echo "    --- actual output ---"
        echo "$haystack" | head -20 | sed 's/^/    /'
        echo "    ---"
    fi
}

# ---------------------------------------------------------------------------
# 1. fix-date-tags — >20260410 becomes >2026-04-10
# ---------------------------------------------------------------------------
run_fix_date_tags() {
    local tmp
    tmp=$(mktemp /tmp/daily_note_XXXXXX.md)
    cp "$FIXTURES/daily_note.md" "$tmp"

    output=$($NOTEPLAN_SWEEP fix-date-tags "$tmp" 2>&1)
    local exit_code=$?
    local content
    content=$(cat "$tmp")
    rm -f "$tmp"

    assert_exit  "fix-date-tags: exit 0"                  0 "$exit_code"
    assert_contains "fix-date-tags: >20260410 replaced"   ">2026-04-10" "$content"

    # Verify the bare tag is gone
    if echo "$content" | grep -qF ">20260410"; then
        fail "fix-date-tags: bare tag still present" "'>20260410' still in output"
    else
        pass "fix-date-tags: bare tag removed"
    fi
}

# ---------------------------------------------------------------------------
# 2. check-source-clean — daily_note has open tasks → exit 1
# ---------------------------------------------------------------------------
run_check_source_clean() {
    output=$($NOTEPLAN_SWEEP check-source-clean "$FIXTURES/daily_note.md" 2>&1)
    local exit_code=$?

    assert_exit "check-source-clean: exit 1 (has open tasks)" 1 "$exit_code"
    assert_contains "check-source-clean: reports open tasks" "Open tasks found" "$output"
}

# ---------------------------------------------------------------------------
# 3. check-section-exists — section present → exit 0
# ---------------------------------------------------------------------------
run_check_section_exists() {
    output=$($NOTEPLAN_SWEEP check-section-exists \
        "$FIXTURES/target_note.md" \
        "# [[🏢260410🤖 Finishing Config Agent HLD]]" 2>&1)
    local exit_code=$?

    assert_exit     "check-section-exists: exit 0 (found)"  0  "$exit_code"
    assert_contains "check-section-exists: confirms found"  "section found" "$output"
}

# ---------------------------------------------------------------------------
# 4. check-section-exists — section absent → exit 2
# ---------------------------------------------------------------------------
run_check_section_missing() {
    output=$($NOTEPLAN_SWEEP check-section-exists \
        "$FIXTURES/target_note.md" \
        "# [[NonExistentSection]]" 2>&1)
    local exit_code=$?

    assert_exit     "check-section-exists (missing): exit 2"         2  "$exit_code"
    assert_contains "check-section-exists (missing): reports absent" "not found" "$output"
}

# ---------------------------------------------------------------------------
# 5. check-frontmatter — broken delimiters → non-zero exit
# ---------------------------------------------------------------------------
run_check_frontmatter_broken() {
    output=$($NOTEPLAN_SWEEP check-frontmatter "$FIXTURES/plan_broken_frontmatter.md" 2>&1)
    local exit_code=$?

    if [ "$exit_code" -ne 0 ]; then
        pass "check-frontmatter: non-zero exit on broken delimiters"
    else
        fail "check-frontmatter: expected non-zero exit" "got exit 0"
    fi
}

# ---------------------------------------------------------------------------
# 6. fix-frontmatter-delimiters — -- becomes ---
# ---------------------------------------------------------------------------
run_fix_frontmatter_delimiters() {
    local tmp
    tmp=$(mktemp /tmp/plan_broken_XXXXXX.md)
    cp "$FIXTURES/plan_broken_frontmatter.md" "$tmp"

    output=$($NOTEPLAN_SWEEP fix-frontmatter-delimiters "$tmp" 2>&1)
    local exit_code=$?
    local content
    content=$(cat "$tmp")
    rm -f "$tmp"

    assert_exit     "fix-frontmatter-delimiters: exit 0"        0   "$exit_code"
    assert_contains "fix-frontmatter-delimiters: --- present"   "---" "$content"

    # Verify no bare -- opener remains (the file should start with ---)
    if head -1 "$FIXTURES/plan_broken_frontmatter.md" | grep -q '^---'; then
        fail "fix-frontmatter-delimiters: fixture already has --- (test invalid)" \
             "fixture should start with -- not ---"
    else
        # Check that the fixed file starts with ---
        if echo "$content" | head -1 | grep -q '^---'; then
            pass "fix-frontmatter-delimiters: file now starts with ---"
        else
            fail "fix-frontmatter-delimiters: file does not start with ---" \
                 "first line: $(echo "$content" | head -1)"
        fi
    fi
}

# ---------------------------------------------------------------------------
# 7. append-section — append content under existing section with --date
# ---------------------------------------------------------------------------
run_append_section() {
    local tmp
    tmp=$(mktemp /tmp/target_note_XXXXXX.md)
    cp "$FIXTURES/target_note.md" "$tmp"

    local content_tmp
    content_tmp=$(mktemp /tmp/content_XXXXXX.txt)
    echo "- [ ] Test task appended by smoke test" > "$content_tmp"

    output=$($NOTEPLAN_SWEEP append-section \
        "$tmp" \
        "# [[🏢260410🤖 Finishing Config Agent HLD]]" \
        "$content_tmp" \
        --date "2026-04-10" 2>&1)
    local exit_code=$?
    local content
    content=$(cat "$tmp")
    rm -f "$tmp" "$content_tmp"

    assert_exit     "append-section: exit 0"                    0   "$exit_code"
    assert_contains "append-section: date subheader present"    "## From 2026-04-10" "$content"
    assert_contains "append-section: appended content present"  "Test task appended by smoke test" "$content"
}

# ---------------------------------------------------------------------------
# 8. add-breadcrumb — breadcrumb table row appears in output
# ---------------------------------------------------------------------------
run_add_breadcrumb() {
    local tmp
    tmp=$(mktemp /tmp/daily_note_bc_XXXXXX.md)
    cp "$FIXTURES/daily_note.md" "$tmp"

    output=$($NOTEPLAN_SWEEP add-breadcrumb \
        "$tmp" \
        "2026-04-10" \
        "Work" \
        "Moved work tasks to config agent plan" \
        "[[🏢260410🤖 Finishing Config Agent HLD]]" 2>&1)
    local exit_code=$?
    local content
    content=$(cat "$tmp")
    rm -f "$tmp"

    assert_exit     "add-breadcrumb: exit 0"                0   "$exit_code"
    assert_contains "add-breadcrumb: table header present"  "| Swept | Section | Summary | Destination |" "$content"
    assert_contains "add-breadcrumb: row with date present" "| 2026-04-10 |" "$content"
    assert_contains "add-breadcrumb: section in row"        "Work" "$content"
}

# ---------------------------------------------------------------------------
# 9. check-date-tags — reports the broken >20260410 tag
# ---------------------------------------------------------------------------
run_check_date_tags() {
    output=$($NOTEPLAN_SWEEP check-date-tags "$FIXTURES/daily_note.md" 2>&1)
    local exit_code=$?

    assert_exit     "check-date-tags: exit 1 (has bare tags)"  1   "$exit_code"
    assert_contains "check-date-tags: reports the tag"         ">20260410" "$output"
}

# ---------------------------------------------------------------------------
# 10. fix-links — explicit stem rename in dry-run mode
# ---------------------------------------------------------------------------
run_fix_links_explicit() {
    local tmp_dir
    tmp_dir=$(mktemp -d /tmp/noteplan_fixlinks_XXXXXX)

    # File containing a wikilink to OldStem
    cat > "$tmp_dir/Note With Link.md" <<'MDEOF'
# Note With Link

See [[OldStem]] for details.
Also [[OldStem#Some Heading|alias]] should match.
MDEOF

    # File that is the renamed target
    cat > "$tmp_dir/NewStem.md" <<'MDEOF'
# OldStem

This file was renamed.
MDEOF

    output=$($NOTEPLAN_SWEEP --dry-run fix-links OldStem NewStem "$tmp_dir" 2>&1)
    local exit_code=$?
    rm -rf "$tmp_dir"

    assert_exit     "fix-links: exit 0 (explicit rename, dry-run)"    0  "$exit_code"
    assert_contains "fix-links: reports files that would change"       "file(s)" "$output"
}

# ---------------------------------------------------------------------------
# 11. fix-links — no notes_root provided, no renames, exits 0 cleanly
# ---------------------------------------------------------------------------
run_fix_links_no_op() {
    local tmp_dir
    tmp_dir=$(mktemp -d /tmp/noteplan_fixlinks_noop_XXXXXX)
    cat > "$tmp_dir/Clean.md" <<'MDEOF'
# Clean

No wikilinks here.
MDEOF

    output=$($NOTEPLAN_SWEEP --dry-run fix-links NoSuchOld NoSuchNew "$tmp_dir" 2>&1)
    local exit_code=$?
    rm -rf "$tmp_dir"

    assert_exit "fix-links (no-op): exit 0"  0  "$exit_code"
}

# ---------------------------------------------------------------------------
# 12. enrich-links — file with no bare URLs exits 0 without modifications
# ---------------------------------------------------------------------------
run_enrich_links_no_bare_urls() {
    local tmp
    tmp=$(mktemp /tmp/enrich_links_XXXXXX.md)
    cat > "$tmp" <<'MDEOF'
# Already Enriched

All links are already formatted: [Google](https://google.com)
No bare URLs here.
MDEOF

    output=$($NOTEPLAN_SWEEP enrich-links "$tmp" --dry-run-preview 2>&1)
    local exit_code=$?
    rm -f "$tmp"

    assert_exit     "enrich-links (no bare URLs): exit 0"    0  "$exit_code"
    assert_contains "enrich-links (no bare URLs): 0 enriched" "0 URL" "$output"
}

# ---------------------------------------------------------------------------
# 13. enrich-links --use-chrome without Playwright exits 1 with install hint
#     (only meaningful when Playwright is NOT installed; skip if venv present)
# ---------------------------------------------------------------------------
run_enrich_links_no_playwright() {
    VENV_DIR="$(dirname "$(dirname "$SCRIPT_DIR")")/.venv"
    if [ -d "$VENV_DIR" ]; then
        echo "  SKIP  enrich-links (no-playwright): venv exists, Playwright may be installed"
        return
    fi

    local tmp
    tmp=$(mktemp /tmp/enrich_links_np_XXXXXX.md)
    echo "https://example.com" > "$tmp"

    output=$($NOTEPLAN_SWEEP enrich-links "$tmp" --use-chrome 2>&1)
    local exit_code=$?
    rm -f "$tmp"

    assert_exit     "enrich-links (no playwright): exit 1"          1  "$exit_code"
    assert_contains "enrich-links (no playwright): install hint"    "playwright" "$output"
}

# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------
echo ""
echo "noteplan-sweep smoke tests"
echo "=================================="
echo "Binary: $NOTEPLAN_SWEEP"
echo "Fixtures: $FIXTURES"
echo ""

run_fix_date_tags
run_check_source_clean
run_check_section_exists
run_check_section_missing
run_check_frontmatter_broken
run_fix_frontmatter_delimiters
run_append_section
run_add_breadcrumb
run_check_date_tags
run_fix_links_explicit
run_fix_links_no_op
run_enrich_links_no_bare_urls
run_enrich_links_no_playwright

echo ""
echo "=================================="
echo "Results: $PASS passed, $FAIL failed"

if [ ${#FAILURES[@]} -gt 0 ]; then
    echo ""
    echo "Failures:"
    for f in "${FAILURES[@]}"; do
        echo "  - $f"
    done
fi

echo ""
if [ "$FAIL" -eq 0 ]; then
    echo "All tests passed."
    exit 0
else
    echo "Some tests FAILED."
    exit 1
fi
