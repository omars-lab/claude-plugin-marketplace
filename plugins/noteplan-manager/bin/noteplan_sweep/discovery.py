"""
discovery.py — Discovery and template cloning commands (Phase F).

Commands:
  list-workstreams    Scan plan directories and print workstream emojis + names
  list-plans          Find plan .md files filtered by age, workstream, status
  list-templates      List @Templates files with type/title from frontmatter
  extract-domains     Extract unique domains from URLs in a file (YAML output)
  clone-template      Copy a template to a target path with variable substitution
  clone-plan          Create a new plan file from the correct template
"""

import re
import sys
from datetime import datetime, timedelta
from pathlib import Path

import noteplan_sweep.utils as utils


# ---------------------------------------------------------------------------
# Patterns
# ---------------------------------------------------------------------------

# Frontmatter block: between --- or -- delimiters
_FM_TRIPLE_RE = re.compile(r'^---\n(.*?)\n---', re.DOTALL)
_FM_DOUBLE_RE = re.compile(r'^--\n(.*?)\n--', re.DOTALL)

# URL extractor
_URL_RE = re.compile(r'https?://[^\s\)\]\'"<>]+')

# Template placeholder styles
_MUSTACHE_RE = re.compile(r'\{\{(\w+)\}\}')
_EJS_RE = re.compile(r'<%-\s*(\w+)\s*%>')


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> dict[str, str]:
    """
    Extract key: value pairs from the first --- or -- frontmatter block.
    Returns an empty dict if no frontmatter is found.
    Values are stripped of surrounding quotes.
    """
    m = _FM_TRIPLE_RE.match(text) or _FM_DOUBLE_RE.match(text)
    if not m:
        return {}
    body = m.group(1)
    result: dict[str, str] = {}
    for line in body.splitlines():
        if ":" in line:
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key:
                result[key] = val
    return result


def _strip_frontmatter(text: str) -> str:
    """
    Return text with the leading frontmatter block (--- or --) removed.
    Also strips leading EJS prompt lines (<% ... -%>).
    """
    # Remove --- frontmatter
    m = _FM_TRIPLE_RE.match(text)
    if m:
        body = text[m.end():]
        return body.lstrip("\n")
    # Remove -- frontmatter
    m = _FM_DOUBLE_RE.match(text)
    if m:
        body = text[m.end():]
        return body.lstrip("\n")
    return text


def _strip_ejs_prompts(text: str) -> str:
    """Remove EJS prompt/logic lines (lines starting with <% ... -%> or <% ... %>)."""
    lines = text.splitlines(keepends=True)
    result = []
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("<%") and (stripped.endswith("%>") or stripped.endswith("-%>")):
            continue
        result.append(line)
    return "".join(result)


def _read_header_lines(path: Path, n: int) -> str:
    """Read up to n lines from a file, returning them as a single string."""
    try:
        with open(path, encoding="utf-8") as f:
            lines = []
            for _ in range(n):
                line = f.readline()
                if not line:
                    break
                lines.append(line)
        return "".join(lines)
    except OSError:
        return ""


def _workstream_dirs(mode: str) -> list[tuple[str, Path]]:
    """
    Return list of (namespace_emoji, plans_dir) pairs filtered by mode.
    mode is one of: work, personal, earlbear, all
    """
    roots = []
    if mode in ("work", "all"):
        roots.append(("🏢", utils.notes_root() / "🏢 ServiceNow" / "📆 Plans"))
    if mode in ("personal", "all"):
        roots.append(("🏡", utils.notes_root() / "🏡 Personal" / "🏡📆 Plans" / "Present"))
    if mode in ("earlbear", "all"):
        roots.append(("👥", utils.notes_root() / "👥 EarlBear" / "📆 Plans"))
    return roots


def _list_immediate_subdirs(path: Path) -> list[str]:
    """Return sorted list of immediate subdirectory names under path, skipping @Backup."""
    if not path.exists():
        return []
    return sorted(
        d.name for d in path.iterdir()
        if d.is_dir() and not d.name.startswith("@")
    )


def _find_template(template_name: str) -> Path | None:
    """
    Locate a template file by name.
    Tries exact stem match first, then substring match.
    Returns None if not found.
    """
    templates_dir = utils.templates_root()
    if not templates_dir.exists():
        return None

    # Exact stem match
    for f in templates_dir.iterdir():
        if f.is_file() and f.suffix == ".md":
            if f.stem == template_name or f.name == template_name:
                return f

    # Contains match (case-insensitive)
    name_lower = template_name.lower()
    for f in templates_dir.iterdir():
        if f.is_file() and f.suffix == ".md":
            if name_lower in f.name.lower():
                return f

    return None


def _substitute_vars(text: str, var_map: dict[str, str]) -> str:
    """
    Replace {{KEY}} and <%- KEY %> placeholders with values from var_map.
    Keys not present in var_map are left unchanged.
    """
    def replace_mustache(m: re.Match) -> str:
        key = m.group(1)
        return var_map.get(key, m.group(0))

    def replace_ejs(m: re.Match) -> str:
        key = m.group(1)
        return var_map.get(key, m.group(0))

    text = _MUSTACHE_RE.sub(replace_mustache, text)
    text = _EJS_RE.sub(replace_ejs, text)
    return text


def _namespace_for_workstream(workstream_emoji: str) -> tuple[str, Path] | None:
    """
    Determine which namespace (🏢/🏡/👥) a workstream emoji belongs to,
    and return (namespace_emoji, plans_dir).
    Returns None if not found in any plans directory.
    """
    candidates = [
        ("🏢", utils.notes_root() / "🏢 ServiceNow" / "📆 Plans"),
        ("🏡", utils.notes_root() / "🏡 Personal" / "🏡📆 Plans" / "Present"),
        ("👥", utils.notes_root() / "👥 EarlBear" / "📆 Plans"),
    ]
    for namespace, plans_dir in candidates:
        if not plans_dir.exists():
            continue
        for subdir in plans_dir.iterdir():
            if subdir.is_dir() and subdir.name.startswith(workstream_emoji):
                return namespace, plans_dir
    return None


def _find_workstream_subdir(plans_dir: Path, workstream_emoji: str) -> Path | None:
    """
    Find the subdirectory under plans_dir whose name starts with workstream_emoji.
    Returns None if not found.
    """
    for subdir in plans_dir.iterdir():
        if subdir.is_dir() and subdir.name.startswith(workstream_emoji):
            return subdir
    return None


def _today_yymmdd() -> str:
    """Return today's date as YYMMDD string."""
    return datetime.now().strftime("%y%m%d")


def _yymmdd_to_iso(yymmdd: str) -> str:
    """Convert YYMMDD to YYYY-MM-DD."""
    try:
        dt = datetime.strptime(yymmdd, "%y%m%d")
        return dt.strftime("%Y-%m-%d")
    except ValueError:
        return yymmdd


# ---------------------------------------------------------------------------
# Status emoji display map
# ---------------------------------------------------------------------------

_STATUS_DISPLAY = {
    "🔮": "🔮 Future",
    "🚦": "🚦 Ready",
    "🟢": "🟢 Started",
    "🟡": "🟡 Paused",
    "🔴": "🔴 Blocked",
    "❎": "❎ Canceled",
    "✅": "✅ Done",
}


# ---------------------------------------------------------------------------
# 1. cmd_list_workstreams
# ---------------------------------------------------------------------------

def cmd_list_workstreams(args):
    """
    Scan actual plan directories for workstream/activity subdirectories.
    Filter by args.mode (work / personal / earlbear / all).
    Print one line per workstream: emoji + name, grouped by namespace.
    Exit 0.
    """
    mode = getattr(args, "mode", "all") or "all"
    namespace_dirs = _workstream_dirs(mode)

    if not namespace_dirs:
        utils.err(f"Unknown mode: {mode!r}. Choose from: work, personal, earlbear, all")
        sys.exit(utils.EXIT_VALIDATION_FAILURE)

    found_any = False
    for namespace, plans_dir in namespace_dirs:
        subdirs = _list_immediate_subdirs(plans_dir)
        if not subdirs:
            utils.verbose(f"No subdirs found under {plans_dir}")
            continue

        label = {
            "🏢": "Work",
            "🏡": "Personal",
            "👥": "EarlBear",
        }.get(namespace, namespace)

        utils.log(f"\n{namespace} {label}:")
        for name in subdirs:
            utils.log(f"  {name}")
        found_any = True

    if not found_any:
        utils.log("No workstreams found.")

    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 2. cmd_list_plans
# ---------------------------------------------------------------------------

def cmd_list_plans(args):
    """
    Find .md plan files modified within args.days days.
    Optionally filter by:
      - args.workstream: emoji prefix to match filename
      - args.status:     status emoji (read first 15 lines of each file for frontmatter)
    Print a table: filename stem | status | description.
    Exit 0.
    """
    days = int(getattr(args, "days", 30))
    workstream_filter = getattr(args, "workstream", None) or ""
    status_filter = getattr(args, "status", None) or ""

    cutoff = datetime.now() - timedelta(days=days)

    # Collect all plan files from all namespace dirs
    plan_roots = [
        utils.notes_root() / "🏢 ServiceNow" / "📆 Plans",
        utils.notes_root() / "🏡 Personal" / "🏡📆 Plans",
        utils.notes_root() / "👥 EarlBear" / "📆 Plans",
    ]

    rows: list[tuple[str, str, str]] = []

    for root in plan_roots:
        if not root.exists():
            continue
        for md_file in root.rglob("*.md"):
            if "@Backup" in str(md_file):
                continue

            # Modified-time filter
            mtime = datetime.fromtimestamp(md_file.stat().st_mtime)
            if mtime < cutoff:
                continue

            stem = md_file.stem

            # Workstream prefix filter
            if workstream_filter and not stem.startswith(workstream_filter):
                continue

            # Read frontmatter for status and description
            header_text = _read_header_lines(md_file, 15)
            fm = _parse_frontmatter(header_text)

            status_raw = fm.get("status", "").strip()
            description = fm.get("description", "").strip()

            # Status filter
            if status_filter:
                if not status_raw.startswith(status_filter):
                    continue

            status_display = _STATUS_DISPLAY.get(status_raw, status_raw or "—")
            rows.append((stem, status_display, description))

    if not rows:
        utils.log("No plans found matching criteria.")
        sys.exit(utils.EXIT_OK)

    # Print table
    col1_w = max(len(r[0]) for r in rows)
    col2_w = max(len(r[1]) for r in rows)
    header_stem = "Plan"
    header_status = "Status"
    header_desc = "Description"
    col1_w = max(col1_w, len(header_stem))
    col2_w = max(col2_w, len(header_status))

    sep = f"{'─' * col1_w}  {'─' * col2_w}  {'─' * len(header_desc)}"
    utils.log(f"{header_stem:<{col1_w}}  {header_status:<{col2_w}}  {header_desc}")
    utils.log(sep)
    for stem, status, desc in sorted(rows, key=lambda r: r[0]):
        utils.log(f"{stem:<{col1_w}}  {status:<{col2_w}}  {desc}")

    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 3. cmd_list_templates
# ---------------------------------------------------------------------------

def cmd_list_templates(args):
    """
    List all .md files in utils.templates_root().
    For each, read first 10 lines and extract title: and type: from YAML frontmatter.
    Print as table: template name | type | title.
    Exit 0.
    """
    templates_dir = utils.templates_root()
    if not templates_dir.exists():
        utils.err(f"Templates directory not found: {templates_dir}")
        sys.exit(utils.EXIT_NOT_FOUND)

    rows: list[tuple[str, str, str]] = []
    for f in sorted(templates_dir.iterdir()):
        if not f.is_file() or f.suffix != ".md":
            continue
        header_text = _read_header_lines(f, 10)
        fm = _parse_frontmatter(header_text)
        title = fm.get("title", "").strip()
        type_ = fm.get("type", "").strip()
        rows.append((f.stem, type_, title))

    if not rows:
        utils.log("No templates found.")
        sys.exit(utils.EXIT_OK)

    col1_w = max(len(r[0]) for r in rows)
    col2_w = max(len(r[1]) for r in rows)
    h1, h2, h3 = "Template", "Type", "Title"
    col1_w = max(col1_w, len(h1))
    col2_w = max(col2_w, len(h2))

    utils.log(f"{h1:<{col1_w}}  {h2:<{col2_w}}  {h3}")
    utils.log(f"{'─' * col1_w}  {'─' * col2_w}  {'─' * len(h3)}")
    for name, type_, title in rows:
        utils.log(f"{name:<{col1_w}}  {type_:<{col2_w}}  {title}")

    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 4. cmd_extract_domains
# ---------------------------------------------------------------------------

def cmd_extract_domains(args):
    """
    Read args.file. Find all URLs with regex https?://...
    Extract hostname (strip www. prefix). Collect unique domains.
    Print as YAML list:
      domains:
        - example.com
    Exit 0.
    """
    path = Path(args.file)
    text = utils.read_file(path)

    domains_seen: list[str] = []
    seen_set: set[str] = set()

    for m in _URL_RE.finditer(text):
        url = m.group(0)
        # Parse hostname from URL (without importing urllib for simplicity)
        # Strip scheme
        rest = url.split("://", 1)[1] if "://" in url else url
        # Get host (up to first / ? # )
        host = re.split(r'[/?#]', rest, maxsplit=1)[0]
        # Strip port
        host = host.split(":")[0]
        # Strip www.
        if host.startswith("www."):
            host = host[4:]
        host = host.lower()
        if host and host not in seen_set:
            seen_set.add(host)
            domains_seen.append(host)

    utils.log("domains:")
    if domains_seen:
        for domain in domains_seen:
            utils.log(f"  - {domain}")
    else:
        utils.log("  []")

    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 5. cmd_clone_template
# ---------------------------------------------------------------------------

def cmd_clone_template(args):
    """
    Clone a template file to args.output_path with variable substitution.

    Template matching (args.template_name):
      - Exact stem/filename match first
      - Falls back to substring match

    Template body (after outer --- frontmatter) may contain:
      - {{KEY}} style placeholders
      - <%- KEY %> style placeholders

    Variable substitution from args.vars list of KEY=VALUE strings.

    Does NOT overwrite an existing output_path — exits 3 with error.
    Writes via utils.write_file. Exit 0 on success.
    """
    template_name = args.template_name
    output_path = Path(args.output_path)
    var_list = getattr(args, "vars", []) or []

    # Parse KEY=VALUE pairs
    var_map: dict[str, str] = {}
    for item in var_list:
        if "=" in item:
            k, _, v = item.partition("=")
            var_map[k.strip()] = v.strip()

    # Prevent overwrite
    if output_path.exists():
        utils.err(f"Output file already exists: {output_path}")
        sys.exit(utils.EXIT_CONFLICT)

    # Locate template
    template_path = _find_template(template_name)
    if template_path is None:
        utils.err(f"Template not found: {template_name!r}")
        templates_dir = utils.templates_root()
        if templates_dir.exists():
            available = [f.stem for f in templates_dir.iterdir() if f.suffix == ".md"]
            utils.err(f"Available templates: {', '.join(sorted(available))}")
        sys.exit(utils.EXIT_NOT_FOUND)

    utils.verbose(f"Using template: {template_path}")

    # Read template
    template_text = utils.read_file(template_path)

    # Extract body: strip outer YAML frontmatter (--- block)
    # Template files have two frontmatter blocks:
    #   1. YAML --- block (title, type) — strip entirely
    #   2. NotePlan -- block in body — keep as-is (user content)
    body = _strip_frontmatter(template_text)

    # Strip EJS prompt/logic lines (they contain dynamic prompts, not content)
    body = _strip_ejs_prompts(body)

    # Substitute placeholders
    body = _substitute_vars(body, var_map)

    # Ensure output parent directory exists
    output_path.parent.mkdir(parents=True, exist_ok=True)

    utils.write_file(output_path, body)
    utils.log(f"Cloned template {template_path.name!r} → {output_path}")

    sys.exit(utils.EXIT_OK)


# ---------------------------------------------------------------------------
# 6. cmd_clone_plan
# ---------------------------------------------------------------------------

def cmd_clone_plan(args):
    """
    Create a new plan file from the correct domain template.

    args.title:       Plan title string
    args.workstream:  Workstream emoji (e.g. 🧑🏻‍💻)
    args.plantype:    Optional personal plantype emoji
    args.date:        Optional YYMMDD string (default: today)

    Steps:
      1. Determine namespace (🏢/🏡/👥) from workstream emoji
      2. Build filename stem: {namespace}{date}{workstream} {title}
      3. Find correct template: work → 🏢📆 Work Plan.md, personal → 🏡📆 Personal Plan.md
      4. Find output directory by matching workstream emoji against plan subdirs
      5. Clone template with vars: title, workstream, date (YYYY-MM-DD)
      6. Write to {plans_dir}/{workstream_subdir}/{filename_stem}.md

    Print full output path. Exit 0 on success.
    """
    title = args.title
    workstream_emoji = args.workstream
    plantype_emoji = getattr(args, "plantype", None) or ""
    date_str = getattr(args, "date", None) or _today_yymmdd()

    # 1. Determine namespace
    result = _namespace_for_workstream(workstream_emoji)
    if result is None:
        utils.err(
            f"Workstream emoji {workstream_emoji!r} not found in any plans directory.\n"
            "Run 'list-workstreams --mode all' to see available workstreams."
        )
        sys.exit(utils.EXIT_NOT_FOUND)

    namespace, plans_dir = result

    # 2. Build filename stem
    filename_stem = f"{namespace}{date_str}{workstream_emoji} {title}"

    # 3. Find correct template
    if namespace == "🏢":
        template_name = "🏢📆 Work Plan"
    elif namespace == "🏡":
        template_name = "🏡📆 Personal Plan"
    elif namespace == "👥":
        # EarlBear reuses work plan template as a fallback
        template_name = "🏢📆 Work Plan"
    else:
        template_name = "🏢📆 Work Plan"

    template_path = _find_template(template_name)
    if template_path is None:
        utils.err(f"Template not found: {template_name!r}")
        sys.exit(utils.EXIT_NOT_FOUND)

    utils.verbose(f"Template: {template_path}")

    # 4. Find output subdirectory
    workstream_subdir = _find_workstream_subdir(plans_dir, workstream_emoji)
    if workstream_subdir is None:
        utils.err(
            f"No subdirectory starting with {workstream_emoji!r} found under {plans_dir}"
        )
        sys.exit(utils.EXIT_NOT_FOUND)

    output_path = workstream_subdir / f"{filename_stem}.md"

    # Check for existing file
    if output_path.exists():
        utils.err(f"Plan file already exists: {output_path}")
        sys.exit(utils.EXIT_CONFLICT)

    # 5. Build var map
    iso_date = _yymmdd_to_iso(date_str)
    var_map: dict[str, str] = {
        "title": filename_stem,
        "workstream": workstream_emoji,
        "date": iso_date,
    }
    if plantype_emoji:
        var_map["plantype"] = plantype_emoji

    # 6. Read template, strip YAML frontmatter + EJS prompts, substitute vars
    template_text = utils.read_file(template_path)
    body = _strip_frontmatter(template_text)
    body = _strip_ejs_prompts(body)
    body = _substitute_vars(body, var_map)

    # Build a minimal NotePlan frontmatter block if body doesn't already have one
    # (after stripping EJS the -- block may remain — that's the NotePlan frontmatter)
    # If not present, prepend one
    if not (body.lstrip().startswith("--\n") or body.lstrip().startswith("---\n")):
        doctype = "📆"
        fm_lines = [
            "---",
            f"doctype: {doctype}",
            f"status: 🔮",
            f"started: {iso_date}",
            f"namespace: {namespace}",
            f"workstream: {workstream_emoji}",
            "---",
            f"# {filename_stem}",
            "",
        ]
        body = "\n".join(fm_lines) + "\n" + body

    utils.write_file(output_path, body)
    utils.log(str(output_path))

    sys.exit(utils.EXIT_OK)
