#!/usr/bin/env python3
"""Match Desktop screenshots and Desktop folders to the projects from scan_projects.py.

Two modes:

    # Screenshots: score each one's OCR text against every project's words
    python3 match_projects.py shots --projects "<projects root>/.projects.json" \
        --ocr desktop_ocr.json [--aliases "<projects root>/.aliases.json"] [--json]

    # Folders: map Desktop folders (and the ones inside Debugging/ and Developing/) to a
    # project by name
    python3 match_projects.py folders --projects "<projects root>/.projects.json" \
        [--desktop ~/Desktop] [--aliases ...] [--json]

Each screenshot gets one of:
    matched  - one project's name, repo name or alias shows in the text, more often than
               any other project's (or an org's name shows and no project's does)
    unclear  - only words from a project's recent commits show; they are listed as
               "candidates" for the look at the image (Vision), never trusted alone
    none     - no project words at all; most likely not project work (shopping, school ...)

Why names only: commit-message words ("following", "career", "pattern") show on every
kind of screen, so a word score picks a project for a recipe or a school form. See
docs/issues/organize-by-project-word-matching.md.

Screenshots taken within --burst seconds of each other are judged together: an unclear
or none shot takes the label of a matched neighbour in the same burst.

The aliases file is hand-written and optional: {"<project name>": ["other", "words"]}.
Use it for names a screen shows that the repo name does not (a product name, an Arabic
title, an old folder name). Aliases count as strongly as the project's own name.
"""
import argparse
import difflib
import json
import math
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# Names too common on a screen to prove anything on their own. A project with one of
# these as its name is matched by its words and aliases only.
GENERIC = {"blog", "plan", "content", "knowledge", "sites", "scripts", "prompts", "books",
           "hubs", "questions", "planner", "chips", "artifacts", "packages", "comments",
           "apps", "landing", "gallery", "environment", "workspace", "portfolio", "youtube",
           "instagram", "adventures", "cdk", "cdn", "hats", "clis", "agent", "design-system",
           "claude-code", "homebrew-tap", "plugins", "marketplace", "mcps", "content"}
# Words every screen of this Mac shows; never evidence for a project.
NOISE = {"claude", "code", "file", "edit", "view", "window", "help", "chrome", "terminal",
         "skill", "skills", "plugin", "plugins", "readme", "page", "pages", "commit",
         "session", "tool", "tools", "script", "json", "html", "test", "tests", "run",
         "step", "list", "show", "keep", "read", "write", "only", "each", "first", "next",
         "back", "open", "data", "user", "users", "what", "they", "them", "their", "after",
         "before", "into", "over", "more", "less", "same", "other", "every", "all", "any"}
IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".heic", ".gif", ".mov", ".mp4"}
SECRET = re.compile(r"client_secret|\.pem$|\.p12$|\.key$|credentials|service.account|\.env$", re.I)
FOLDER_PREFIX = re.compile(r"^(debugging|developing|project|meetings)[- _]+", re.I)
SHOT_TIME = re.compile(r"(\d{4}-\d{2}-\d{2}) at (\d{1,2})\.(\d{2})\.(\d{2})\W*([AP]M)")


def norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower()


def load_projects(path: Path, aliases_path: Path | None) -> tuple[list[dict], dict[str, list[str]]]:
    """Projects with their strong names, and the org umbrellas: org -> words naming it."""
    projects = json.loads(path.read_text())["projects"]
    aliases = json.loads(aliases_path.read_text()) if aliases_path and aliases_path.is_file() else {}
    orgs = {o: [norm(w) for w in ws] for o, ws in aliases.pop("_orgs", {}).items()}
    aliases.pop("_folders", None)
    for p in projects:
        names = {p["name"].lower(), p["repo"].lower()}
        # acme-blog -> also "acme blog"; tea-shop-sites -> "tea shop sites"
        names |= {n.replace("-", " ") for n in names if "-" in n}
        p["strong"] = sorted(n for n in names if n not in GENERIC and len(n) >= 4
                             and n not in {w for ws in orgs.values() for w in ws})
        p["strong"] += [norm(a) for a in aliases.get(p["name"], [])]
        # homework-cli -> "homework"; acme-domain -> "domain". Weaker than the full name.
        org_words = {w for ws in orgs.values() for w in ws} | {p["org"]}
        p["parts"] = sorted({w for n in (p["name"], p["repo"]) for w in n.lower().split("-")
                             if len(w) >= 4 and w not in GENERIC | NOISE | org_words} - set(p["strong"]))
    return projects, orgs


def word_weights(projects: list[dict]) -> dict[str, dict[str, float]]:
    """Per project: signal word -> weight, rarer across projects = heavier (IDF)."""
    df: dict[str, int] = {}
    for p in projects:
        for w in set(p["signals"]):
            df[w] = df.get(w, 0) + 1
    n = len(projects)
    out = {}
    for p in projects:
        out[p["name"]] = {w: math.log(n / df[w]) for w in p["signals"]
                          if w not in NOISE and len(w) >= 4 and df[w] <= max(3, n // 15)}
    return out


def has(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def score_text(text: str, projects: list[dict], weights: dict) -> list[tuple[int, int, float, str, list[str]]]:
    """(name hits, name-part hits, word score, project, evidence), best first."""
    t = norm(text)
    scored = []
    for p in projects:
        hits = [s for s in p["strong"] if has(t, s)]
        parts = [w for w in p["parts"] if has(t, w)]
        words = [w for w in weights[p["name"]] if has(t, w) and w not in parts and w not in p["strong"]]
        if hits or parts or words:
            scored.append((len(hits), len(parts), round(sum(weights[p["name"]][w] for w in words), 1),
                           p["name"], hits + parts + words))
    scored.sort(reverse=True)
    return scored


def shot_time(name: str) -> datetime | None:
    m = SHOT_TIME.search(name.replace(" ", " "))
    if not m:
        return None
    day, h, mi, se, ap = m.groups()
    h = int(h) % 12 + (12 if ap == "PM" else 0)
    return datetime.fromisoformat(f"{day}T{h:02d}:{mi}:{se}")


def match_shots(ocr: dict, projects: list[dict], orgs: dict[str, list[str]], burst: int) -> list[dict]:
    weights = word_weights(projects)
    rows = []
    for path, v in ocr.items():
        text = v.get("text") or ""
        scored = score_text(text, projects, weights)
        # No project's name shows but an org's does -> the org's own folder.
        if not scored or scored[0][0] == 0:
            t = norm(text)
            for org, ws in orgs.items():
                hits = [w for w in ws if has(t, w)]
                if hits:
                    scored.append((len(hits), 0, 0.0, org, hits))
            scored.sort(reverse=True)
        t = shot_time(Path(path).name)
        row = {"file": path, "time": t.isoformat() if t else None, "status": "none",
               "project": None, "score": 0, "why": [], "candidates": []}
        if scored:
            top, second = scored[0], (scored[1] if len(scored) > 1 else (0, 0, 0.0, None, []))
            # A full name wins outright; a name part only when no other project shows anything.
            if top[0] > second[0] or (top[0] == 0 and top[1] > 0 and len(scored) == 1):
                row.update(status="matched", project=top[3], score=top[0] or 0.5, why=top[4][:6])
            else:
                row.update(status="unclear", candidates=[c[3] for c in scored[:3]],
                           why=top[4][:6])
        rows.append(row)
    # Bursts: an unsure shot takes the label of a matched shot taken moments before/after.
    rows.sort(key=lambda r: r["time"] or "")
    for i, r in enumerate(rows):
        if r["status"] == "matched" or not r["time"]:
            continue
        t = datetime.fromisoformat(r["time"])
        near = [o for o in rows[max(0, i - 4): i + 5] if o is not r and o["status"] == "matched"
                and o["time"] and abs((datetime.fromisoformat(o["time"]) - t).total_seconds()) <= burst]
        if near:
            best = max(near, key=lambda o: o["score"])
            r.update(status="matched", project=best["project"], score=0,
                     why=[f"burst with {Path(best['file']).name}"])
    return rows


def folder_candidates(desktop: Path) -> list[Path]:
    out = []
    for d in sorted(desktop.iterdir()):
        if d.is_dir() and not d.name.startswith("."):
            out.append(d)
            if d.name in ("Debugging", "Developing"):
                out += sorted(c for c in d.iterdir() if c.is_dir())
    return out


def folder_key(name: str) -> tuple[str, bool]:
    """'Debugging Acme Blog' -> ('acme-blog', True). True = it had a work prefix."""
    stripped = FOLDER_PREFIX.sub("", name)
    key = re.sub(r"[\s_]+", "-", norm(stripped))
    return key, stripped != name


def match_folders(desktop: Path, projects: list[dict], orgs: dict[str, list[str]],
                  pinned: dict[str, str]) -> list[dict]:
    """A folder maps to a project only on a name match, never on its contents.

    Ranked: same name > the folder name starts with the project's (atlas-studio -> atlas)
    or the project's starts with it (getting-started-with-claude) > a near spelling
    (portolio). Generic project names (blog, scripts ...) count only when the folder
    carries a work prefix (debugging-, developing-, project-). Ties are left unclear.
    Last resort: the folder names an org (Acme, Tea Shop) -> the org's own folder.
    A folder listed in the aliases file's "_folders" (Desktop-relative path -> project) is
    decided there, after someone looked at it; that beats every rule.
    """
    rows = []
    for d in folder_candidates(desktop):
        key, prefixed = folder_key(d.name)
        hits: list[tuple[int, str, str]] = []
        for p in projects:
            names = {p["name"].lower(), p["repo"].lower(), *[s.replace(" ", "-") for s in p["strong"]]}
            names = {n for n in names if len(n) >= 4 and (prefixed or n not in GENERIC)}
            if key in names:
                hits.append((3, p["name"], "same name"))
            elif any(key.startswith(n + "-") or (len(key) >= 10 and n.startswith(key)) for n in names):
                hits.append((2, p["name"], "name starts the same"))
            elif prefixed and any(difflib.SequenceMatcher(None, key, n).ratio() >= 0.88 for n in names):
                hits.append((1, p["name"], "near spelling"))
        hits.sort(reverse=True)
        top = [h for h in hits if h[0] == hits[0][0]] if hits else []
        row = {"folder": str(d), "project": None, "kind": None, "why": "", "files": None}
        rel = str(d.relative_to(desktop))
        if rel in pinned:
            row.update(project=pinned[rel], kind="pinned", why="decided in the aliases file")
        elif len(top) == 1:
            row.update(project=top[0][1], kind="project", why=top[0][2])
        elif len(top) > 1:
            row.update(kind="unclear", why="could be " + " or ".join(h[1] for h in top))
        else:
            words = set(key.split("-")) | {key, key.replace("-", " ")}
            org = next((o for o, ws in orgs.items() if any(w in words or key.startswith(w.replace(" ", "-"))
                                                             for w in ws)), None)
            if org:
                row.update(project=org, kind="org", why="names the org")
        if row["kind"]:
            files = [f for f in d.rglob("*") if f.is_file() and f.name != ".DS_Store"]
            row["files"] = len(files)
            # Not just screenshots: code, documents, maybe keys. Show them before a move.
            row["non_images"] = sum(1 for f in files if f.suffix.lower() not in IMAGE_EXTS)
            row["secrets"] = [str(f.relative_to(d)) for f in files if SECRET.search(f.name)]
        rows.append(row)
    return rows


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["shots", "folders"])
    ap.add_argument("--projects", type=Path, required=True)
    ap.add_argument("--aliases", type=Path)
    ap.add_argument("--ocr", type=Path, help="batch_ocr.py JSON (shots mode)")
    ap.add_argument("--desktop", type=Path, default=Path.home() / "Desktop")
    ap.add_argument("--burst", type=int, default=120, help="seconds that make one burst")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", type=Path, help="write JSON rows here")
    a = ap.parse_args()
    projects, orgs = load_projects(a.projects, a.aliases)
    if a.mode == "shots":
        if not a.ocr:
            sys.exit("shots mode needs --ocr")
        rows = match_shots(json.loads(a.ocr.read_text()), projects, orgs, a.burst)
    else:
        pinned = {}
        if a.aliases and a.aliases.is_file():
            pinned = json.loads(a.aliases.read_text()).get("_folders", {})
        rows = match_folders(a.desktop.expanduser(), projects, orgs, pinned)
    if a.out:
        a.out.write_text(json.dumps(rows, indent=2, ensure_ascii=False))
        print(f"wrote {len(rows)} rows to {a.out}", file=sys.stderr)
    if a.json:
        print(json.dumps(rows, indent=2, ensure_ascii=False))
        return
    if a.mode == "shots":
        counts: dict[tuple, int] = {}
        for r in rows:
            k = (r["status"], r["project"] if r["status"] == "matched" else "")
            counts[k] = counts.get(k, 0) + 1
        for (status, proj), n in sorted(counts.items(), key=lambda kv: (kv[0][0], -kv[1])):
            print(f"{status:8} {n:4}  {proj}")
    else:
        for r in rows:
            if r["kind"]:
                print(f"{r['kind']:8} {r['project'] or '?':34} <- "
                      f"{Path(r['folder']).relative_to(a.desktop.expanduser())}  ({r['files']} files, "
                      f"{r['non_images']} not images; {r['why']})"
                      + (f"  !! {len(r['secrets'])} key/secret files" if r["secrets"] else ""))


if __name__ == "__main__":
    main()
