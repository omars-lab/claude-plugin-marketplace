#!/usr/bin/env python3
"""PreToolUse hook (config-driven, shipped by task-management-manager): block
TaskUpdate `status: deleted` unless the task has first been recorded in the
repo's task files (DONE_FILE / BACKLOG_FILE from task-management.conf).

Rationale: tasks must be persisted to the markdown task files BEFORE they are
destroyed from the live task list, so nothing is silently dropped.

No-op unless the repo's .claude/hooks/task-management.conf exists and
ENABLE_GUARD_DELETION is truthy.

Contract (unchanged from the original loose hook):
  - stdin: JSON with tool_name + tool_input (Claude Code PreToolUse payload)
  - exit 0  -> allow (not a deletion, or the task is recorded)
  - exit 2  -> BLOCK; stderr is shown back to Claude so it can self-correct

How "recorded" is decided (v1.2.0 — id first, fuzzy second):
  1. ID match. A task-file line is a task bullet (`- [x] …` / `- [ ] …`) whose
     first bold token is the task's id: `**#N**` or `**gtm-N**` (or any
     `**<slug>**`). Candidate ids come from the TaskUpdate payload — a leading
     `#N` / `gtm-N` / `**…**` token in `subject`, and the numeric `taskId` as
     `#<taskId>`. One exact bullet match = recorded. This is the authoritative
     path: it cannot false-pass on generic wording in a dense corpus.
  2. Fuzzy fallback (the original behaviour): >=60% of the subject's >3-char
     tokens present anywhere in the corpus. Kept only for tasks whose lines
     carry no id (legacy/free-form ledgers).
  Caveat: live Task-tool ids restart when the list is cleared, so `taskId` can
  collide with an OLD ledger id. A repo whose ledger ids are assigned by the
  ledger (not the tool) should put the ledger id at the front of the live
  task's subject — that candidate is checked first and wins.
"""
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _taskconf  # noqa: E402


def norm(s: str, done_marker: str) -> str:
    """Lowercase + collapse whitespace + drop a leading bracket tag/status noise
    so '[USER] Connect shop...' matches 'connect shop...' in the md files."""
    s = s.lower()
    s = re.sub(r"\[[^\]]*\]", " ", s)                    # strip [MANUAL]/[USER]/[x]/[ ] tags
    s = re.sub(re.escape(done_marker) + r"\([^)]*\)", " ", s)  # strip @done(...) timestamps
    s = re.sub(r"[`*_#>-]", " ", s)                      # strip md punctuation
    s = re.sub(r"\s+", " ", s).strip()
    return s


ID_TOKEN_RE = re.compile(r"^\s*(?:\*\*)?(#\d+|gtm-\d+|[A-Za-z][A-Za-z0-9._-]*)(?:\*\*)?[\s:—-]")


def candidate_ids(ti: dict) -> tuple[str | None, list[str]]:
    """Ids this deletion could be recorded under, most specific first.
    Returns (subject_id, ids): `subject_id` is an explicit id at the front of the
    subject (`#N` / `gtm-N` / `**slug**`) or None; `ids` is that plus the numeric
    taskId as `#<taskId>` (deduplicated)."""
    subject_id: str | None = None
    subject = str(ti.get("subject", "") or "")
    m = ID_TOKEN_RE.match(subject + " ")
    if m:
        tok = m.group(1)
        # a bare word at the start of a free-form subject ("Trip the …") is not an id;
        # only accept slugs that look like ids (contain a digit, '-', '.' or '_')
        if tok.startswith("#") or tok.startswith("gtm-") or re.search(r"[\d._-]", tok):
            subject_id = tok
    ids: list[str] = [subject_id] if subject_id else []
    task_id = str(ti.get("taskId", "") or "").strip()
    if task_id.isdigit() and f"#{task_id}" not in ids:
        ids.append(f"#{task_id}")
    return subject_id, ids


def id_recorded(raw_corpus: str, ids: list[str]) -> str | None:
    """Return the first id that heads a task bullet in the RAW (un-normalised)
    task files: `- [x] **#89** …` / `- [ ] **gtm-7** …` / `- [ ] **slug** …`."""
    for tid in ids:
        pat = re.compile(r"^\s*-\s*\[(?:\s|[xX])\]\s+\*\*" + re.escape(tid) + r"\*\*", re.M)
        if pat.search(raw_corpus):
            return tid
    return None


def significant_tokens(s: str, done_marker: str) -> list[str]:
    """Keep tokens >3 chars that carry meaning, for a fuzzy containment check."""
    return [t for t in norm(s, done_marker).split() if len(t) > 3]


def main() -> int:
    root = _taskconf.project_root()
    conf = _taskconf.load_conf(root)
    if not _taskconf.enabled(conf, "ENABLE_GUARD_DELETION"):
        try:
            sys.stdin.read()
        except Exception:
            pass
        return 0

    try:
        payload = json.load(sys.stdin)
    except Exception:
        return 0  # never break the tool on a parse error of our own

    if payload.get("tool_name") != "TaskUpdate":
        return 0

    ti = payload.get("tool_input", {}) or {}
    if str(ti.get("status", "")).lower() != "deleted":
        return 0  # only guard actual deletions

    delete_reason = str((ti.get("metadata") or {}).get("deleteReason", "")).strip().lower()
    if delete_reason and delete_reason in _taskconf.allow_unrecorded_delete_reasons(conf):
        return 0  # explicit, opted-in exception — not a silent bypass

    done_marker = _taskconf.done_marker(conf)
    task_files = [_taskconf.done_file(conf), _taskconf.backlog_file(conf)]

    root_p = Path.cwd() if root is None else root
    corpus_parts = []
    for rel in task_files:
        p = root_p / rel
        if p.exists():
            corpus_parts.append(p.read_text(encoding="utf-8", errors="ignore"))
    raw_corpus = "\n".join(corpus_parts)
    corpus = norm(raw_corpus, done_marker)

    if not corpus.strip():
        print(
            "BLOCKED: TaskUpdate status=deleted, but no task files found at "
            f"{task_files}. Record the task there (done file if closed as "
            f"'- [x] … {done_marker}(<isoTimestamp>)', backlog file if open as "
            "'- [ ] …') before deleting.",
            file=sys.stderr,
        )
        return 2

    # 1. Id-based match — authoritative, immune to generic wording.
    subject_id, ids = candidate_ids(ti)
    if ids and id_recorded(raw_corpus, ids):
        return 0
    if subject_id:
        # The subject names an explicit id that is NOT in the ledger. Do not let the
        # fuzzy fallback rescue it — that is exactly the false-pass this ordering exists
        # to prevent. (Only the bare taskId candidate may fall through to fuzzy, since
        # free-form subjects in legacy ledgers carry no id at all.)
        print(
            "BLOCKED: task %s is not recorded — no `- [x]/- [ ] **%s** …` bullet in %s. "
            "Add that line (done file if closed, backlog file if open), then delete."
            % (subject_id, subject_id, task_files),
            file=sys.stderr,
        )
        return 2

    # 2. Fuzzy fallback. We only get taskId, not subject text — so require the
    # caller to include a `subject` (or description) so we can verify it's recorded.
    text = " ".join(
        str(ti.get(k, "")) for k in ("subject", "description") if ti.get(k)
    ).strip()

    if not text:
        print(
            "BLOCKED: cannot verify task #%s is recorded before deletion — no task "
            "bullet `- [x]/- [ ] **%s** …` in %s, and TaskUpdate carried no "
            "`subject`/`description` to fuzzy-match against. First ensure the task "
            "line exists (done file if closed, backlog file if open), then re-issue "
            "the delete WITH the task's `subject`." % (ti.get("taskId", "?"), ids[0] if ids else "#?", task_files),
            file=sys.stderr,
        )
        return 2

    toks = significant_tokens(text, done_marker)
    # Consider it recorded if a strong majority of significant tokens are present.
    if toks:
        hits = sum(1 for t in toks if t in corpus)
        if hits >= max(2, int(len(toks) * 0.6)):
            return 0

    print(
        "BLOCKED: task \"%s\" does not appear to be recorded in %s yet "
        "(no id bullet for %s; fuzzy match below threshold). "
        "Add it first — done file as '- [x] **%s** %s %s(<isoTimestamp>)' if closed, "
        "or backlog file as '- [ ] **%s** %s' if still open — then delete."
        % (text, task_files, ", ".join(ids) or "no id", ids[0] if ids else "#N", text, done_marker, ids[0] if ids else "#N", text),
        file=sys.stderr,
    )
    return 2


if __name__ == "__main__":
    sys.exit(main())
