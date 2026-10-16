#!/usr/bin/env python3
"""Flag text in technique specs that could identify the person before pages are shared.

It reports and changes nothing. The skill shows the findings and asks what to replace.

Usage:
    python3 scan_privacy.py --spec <root>/pages/specs/<slug>.json
    python3 scan_privacy.py --all [--root <dir>]
    python3 scan_privacy.py --all --post      # what the post view would still show

--post scans each spec after its redactions (and the shared specs/_redactions.json) are
applied, so the findings are exactly what is left to replace. render_page.py refuses to
write a post page while this finds anything.

It also flags passwords, keys and tokens (hide_secrets.py's rules). A secret is reported by
its outline only (letters a/A, digits 9, symbols #), never its value, and is fixed by editing
the spec's text, not by a redaction rule, which would copy the secret into the spec again.

These patterns can't recognize names of people, companies, products or internal tools.
Read the post view for those and add them to the redactions.

Redaction rules: {"find": "...", "replace": "..."}, matched as whole tokens. Put rules for
names that recur across specs in specs/_redactions.json, and one-off ones in the spec's own
"redactions" list. To keep a flagged value that is fine to publish, add a rule whose replace
equals its find.

Output (JSON on stdout):
    {"<spec path>": [{"where": "blocks[3].text", "kind": "cost", "match": "$12.34"}], ...}
"""
import argparse
import json
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import lib  # noqa: E402
from hide_secrets import hide_counted  # noqa: E402

PATTERNS = {
    "cost": r"\$\s?\d[\d,]*(?:\.\d+)?",
    "email": r"[\w.+-]+@[\w-]+\.[\w.-]+",
    "url": r"https?://[^\s)\"']+",
    "hostname": r"\b[\w-]+\.(?:service-now|servicenow|atlassian|slack|sharepoint|okta)\.\w+\b",
    "branch": r"\b(?:feature|feat|fix|bugfix|hotfix|release)/[\w./-]+",
    "repo_path": r"\b(?:workspace|repos?|src|Users)/[\w.-]+(?:/[\w.-]+)*",
    "pr_or_ticket": r"(?:\bPR\s?#\d+|\b[A-Z][A-Z0-9]{1,9}-\d{2,}\b|\b(?:INC|CHG|RITM|PRB|STRY|DEF)\d{5,}\b)",
    "ip": r"\b\d{1,3}(?:\.\d{1,3}){3}\b",
}
COMPILED = {k: re.compile(v) for k, v in PATTERNS.items()}


def walk(node, where=""):
    if isinstance(node, str):
        yield where, node
    elif isinstance(node, dict):
        for k, v in node.items():
            if k in ("slug", "type", "tone", "status", "mode", "view", "image", "file", "session", "redactions"):
                continue
            yield from walk(v, f"{where}.{k}" if where else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from walk(v, f"{where}[{i}]")


def scan(spec: dict, allow: tuple[str, ...] = ()) -> list[dict]:
    """allow: replacement values. A hit inside one is a stand-in, or a value someone reviewed
    and kept (a redaction whose replace equals its find), so it isn't reported."""
    hits, seen = [], set()
    for where, text in walk(spec):
        for kind, rx in COMPILED.items():
            for m in rx.finditer(text):
                if any(m.group(0) in a for a in allow):
                    continue
                key = (where, kind, m.group(0))
                if key not in seen:
                    seen.add(key)
                    hits.append({"where": where, "kind": kind, "match": m.group(0)})
        found: list = []
        hide_counted(text, found)
        for what, outline in found:
            key = (where, "secret", outline)
            if key not in seen:
                seen.add(key)
                hits.append({"where": where, "kind": "secret",
                             "match": f"{what} shaped {outline} (value not shown; edit the spec)"})
    return hits


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--spec", action="append")
    g.add_argument("--all", action="store_true")
    ap.add_argument("--post", action="store_true", help="scan the redacted (post) version")
    args = ap.parse_args()
    root = lib.find_root(args.root)
    paths = lib.spec_paths(root) if args.all else [Path(s).expanduser() for s in args.spec]
    report = {}
    for p in paths:
        spec = json.loads(p.read_text(encoding="utf-8"))
        allow = tuple(r["replace"] for r in lib.redactions_for(spec, root)) if args.post else ()
        report[str(p)] = scan(lib.post_spec(spec, root) if args.post else spec, allow)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
