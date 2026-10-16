#!/usr/bin/env python3
"""Match Desktop screenshots and Desktop folders to the projects from scan_projects.py.

Four modes:

    # Screenshots: match each one's OCR text to a project by name; fingerprints add hints
    python3 match_projects.py shots --projects "<projects root>/.projects.json" \
        --ocr desktop_ocr.json [--aliases "<projects root>/.aliases.json"] \
        [--fingerprints fingerprints.json] [--json]

    # Folders: map Desktop folders to a project by name. Folders of folders (Debugging/,
    # Developing/, or any with 3+ subfolders) are opened and their subfolders matched too
    python3 match_projects.py folders --projects "<projects root>/.projects.json" \
        [--desktop ~/Desktop] [--aliases ...] [--out folders.json]

    # Look inside the folders no name placed: list their screenshots to OCR, then judge
    # each folder by the names on its screenshots (whole / split / undecided)
    python3 match_projects.py to-read --projects ... --folders folders.json --out list.txt
    python3 match_projects.py inside --projects ... --folders folders.json --ocr ocr.json \
        --out inside.json

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
OCR_EXTS = {".png", ".jpg", ".jpeg", ".heic"}
# Folders of life admin, not project work: a folder with one of these words in its name is
# never looked inside (singular or plural). Add more, by Desktop-relative path, in the
# aliases file's "_skip" list.
LIFE = {"receipt", "paperwork", "family", "activitie", "activity", "appointment", "shopping",
        "financial", "confirmation", "decorating", "celebrating", "organizing", "maintaining",
        "crafting", "career", "vacation", "trip", "travel", "birthday", "health", "medical",
        "insurance", "bill", "tax", "taxe", "zakat", "school", "job", "worship", "kid", "wedding",
        "moving", "education", "cooking", "recipe", "chef", "hsa", "decor", "decore", "book",
        "mothers", "fathers", "photo", "video", "visa", "voting", "daycare", "parking", "dispute",
        "401k", "mba", "masters", "ymca", "eating", "rollover"}
# Screenshot folders other skills own; never looked inside or moved from here.
OWNED = {"Screenshots", "📸 Screenshots of Techniques"}
# Folders that hold work folders. Others are found by shape (see is_container).
WORK_CONTAINERS = {"debugging", "developing"}
SKIP_DIRS = {"node_modules", ".git", "venv", ".venv", "site-packages", "__pycache__", "dist",
             "build", ".next", "Pods"}
# A folder named for keys is held even when no file in it looks like one.
KEY_FOLDER = re.compile(r"(^|[- _])keys?($|[- _])|secret|credential|password", re.I)
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
        p["strong"] = sorted(n for n in names if n.replace(" ", "-") not in GENERIC and len(n) >= 4
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


def apply_fingerprints(rows: list[dict], ocr: dict, fps: list[dict], projects: list[dict]) -> None:
    """Web addresses and paths from the folders' fingerprint.md files (fingerprint.py index).

    Only a signal that belongs to one place counts: a site in the fingerprints of one project
    (any of its folders), or of one non-project folder. A shot no name placed that shows such
    a signal, and no signal of another place:
      - project place: that project goes first in "candidates", with the signal in "why", for
        the image check. It does not decide: a site seen in one folder (a docs page, a tool)
        is not proof the next screenshot showing it is the same work.
      - non-project folder (Receipts, Paperwork ...): "suggest_folder", used only if the image
        check says the shot is not project work
    A site or path holding a project's name or alias (blog.<blog alias>.com) belongs to that
    project wherever it was seen, so a project's own site never sends a shot to a life folder.
    """
    from fingerprint import COMMON_SITES, signals  # here, not at the top: fingerprint.py imports this file
    owners: dict[str, set[str]] = {}
    for fp in fps:
        place = fp["project"] or "folder:" + fp["folder"]
        for sig in [*fp["sites"], *fp["paths"]]:
            if sig not in COMMON_SITES:
                owners.setdefault(sig, set()).add(place)
    squash = lambda t: re.sub(r"[\W_]", "", t)  # noqa: E731
    named = [(p["name"], squash(n)) for p in projects for n in p["strong"] if len(squash(n)) >= 5]
    for sig in owners:
        hit = {name for name, n in named if n in squash(sig)}
        if len(hit) == 1:
            owners[sig] = hit
    unique = {sig: next(iter(p)) for sig, p in owners.items() if len(p) == 1}
    for r in rows:
        if r["status"] == "matched":
            continue
        sites, paths, _ = signals(ocr.get(r["file"], {}).get("text") or "")
        hits: dict[str, list[str]] = {}
        for sig in sites | paths:
            if sig in unique:
                hits.setdefault(unique[sig], []).append(sig)
        if len(hits) != 1:  # shared sites (github.com, localhost) say nothing either way
            continue
        place, sigs = next(iter(hits.items()))
        if place.startswith("folder:"):
            r["suggest_folder"] = place.removeprefix("folder:")
            r["suggest_why"] = sigs[:3]
        else:
            r.update(status="unclear", candidates=[place] + [c for c in r["candidates"] if c != place][:2],
                     why=[f"fingerprint: {s}" for s in sigs[:3]] + r["why"][:3])


def subdirs(d: Path) -> list[Path]:
    return sorted(c for c in d.iterdir() if c.is_dir() and not c.name.startswith("."))


def is_life(d: Path, desktop: Path, skip: set[str]) -> bool:
    if str(d.relative_to(desktop)) in skip or d.name in OWNED:
        return True
    return any(w in LIFE or w.rstrip("s") in LIFE for w in re.findall(r"[a-z]+", norm(d.name)))


def is_container(d: Path) -> bool:
    """A folder of folders: Debugging/, Developing/, or one with 3+ subfolders and fewer loose
    images than subfolders. Its subfolders are matched one by one."""
    if d.name.lower() in WORK_CONTAINERS:
        return True
    subs = subdirs(d)
    loose = sum(1 for f in d.iterdir() if f.is_file() and f.suffix.lower() in IMAGE_EXTS)
    return len(subs) >= 3 and len(subs) > loose


def folder_key(name: str) -> tuple[str, bool]:
    """'Debugging Acme Blog' -> ('acme-blog', True). True = it had a work prefix."""
    stripped = FOLDER_PREFIX.sub("", name)
    key = re.sub(r"[\s_]+", "-", norm(stripped))
    return key, stripped != name


def match_folders(desktop: Path, projects: list[dict], orgs: dict[str, list[str]],
                  pinned: dict[str, str], skip: set[str] = frozenset()) -> list[dict]:
    """A folder maps to a project only on a name match, never on its contents.

    Ranked: same name > the folder name starts with the project's (atlas-studio -> atlas)
    or the project's starts with it (getting-started-with-claude) > a near spelling
    (portolio). Generic project names (blog, scripts ...) count only when the folder
    carries a work prefix (debugging-, developing-, project-). Ties are left unclear.
    Last resort: the folder names an org (Acme, Tea Shop) -> the org's own folder.
    A folder listed in the aliases file's "_folders" (Desktop-relative path -> project) is
    decided there, after someone looked at it; that beats every rule.

    The Desktop's folders come first. A container (is_container) that no rule placed is
    opened and its subfolders are matched too, one level down. Each row says whether it is
    a "container" and whether it is a "life" folder, for the look inside (inside_groups).
    """
    rows = []
    queue = [(d, 1) for d in subdirs(desktop)]
    while queue:
        d, depth = queue.pop(0)
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
        row = {"folder": str(d), "project": None, "kind": None, "why": "", "files": None,
               "life": is_life(d, desktop, skip), "container": False}
        rel = str(d.relative_to(desktop))
        if d.name in OWNED:
            rows.append(row)
            continue
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
        if row["kind"] in (None, "unclear") and depth == 1 and not row["life"] and is_container(d):
            row["container"] = True
            queue += [(c, depth + 1) for c in subdirs(d)]
        if row["kind"]:
            files = [f for f in d.rglob("*") if f.is_file() and f.name not in (".DS_Store", "fingerprint.md")]
            row["files"] = len(files)
            # Not just screenshots: code, documents, maybe keys. Show them before a move.
            row["non_images"] = sum(1 for f in files if f.suffix.lower() not in IMAGE_EXTS)
            row["secrets"] = [str(f.relative_to(d)) for f in files if SECRET.search(f.name)]
            if KEY_FOLDER.search(d.name):
                row["secrets"].insert(0, "(the folder's name says it holds keys)")
        rows.append(row)
    return rows


def images_under(d: Path) -> list[Path]:
    out = []
    for f in sorted(d.rglob("*")):
        if f.suffix.lower() in OCR_EXTS and f.is_file() and not SKIP_DIRS & set(f.relative_to(d).parts):
            out.append(f)
    return out


def inside_groups(rows: list[dict], per_folder: int) -> list[dict]:
    """The folders no name placed, to be judged by what their screenshots show.

    A container gives its loose images (one group, judged one by one). Any other folder gives
    every image under it, an even sample of per_folder when it has more. Life folders, the
    folders other skills own and folders with no images are left out.
    """
    groups = []
    for r in rows:
        if r["kind"] not in (None, "unclear") or r["life"] or Path(r["folder"]).name in OWNED:
            continue
        d = Path(r["folder"])
        if r["container"]:
            imgs = sorted(f for f in d.iterdir() if f.is_file() and f.suffix.lower() in OCR_EXTS)
        else:
            imgs = images_under(d)
        if not imgs:
            continue
        step = max(1, math.ceil(len(imgs) / per_folder))
        groups.append({"folder": str(d), "loose": r["container"], "total": len(imgs),
                       "images": [str(f) for f in imgs[::step]]})
    return groups


def judge_inside(groups: list[dict], ocr: dict, projects: list[dict], orgs: dict[str, list[str]],
                 burst: int, sample: int) -> list[dict]:
    """Per folder, from its screenshots' name matches:

    whole      - names show on at least 40% of the shots read, at least 2, and one project
                 has 70% of them: the folder moves whole to that project
    split      - some names show but not like that (or the group is a container's loose
                 images): only the matched shots move, each to its project
    undecided  - no names: `sample` evenly spread shots go to the image check, which decides
    """
    out = []
    for g in groups:
        rows = match_shots({f: ocr[f] for f in g["images"] if f in ocr}, projects, orgs, burst)
        matched = [r for r in rows if r["status"] == "matched"]
        counts: dict[str, int] = {}
        for r in matched:
            counts[r["project"]] = counts.get(r["project"], 0) + 1
        top = max(counts, key=counts.get) if counts else None
        row = {**g, "read": len(rows), "counts": counts, "verdict": "undecided", "project": None,
               "moves": [], "sample": []}
        del row["images"]
        if (not g["loose"] and len(matched) >= 2 and len(matched) >= 0.4 * len(rows)
                and counts[top] >= 0.7 * len(matched)):
            row.update(verdict="whole", project=top,
                       why=f"{counts[top]} of {len(rows)} screenshots show {top}'s name")
        elif len(matched) >= (1 if g["loose"] else 2):
            # One stray name is not enough to pull a shot out of a folder that belongs together.
            row.update(verdict="split", why=f"names show on {len(matched)} of {len(rows)} screenshots",
                       moves=[{"file": r["file"], "project": r["project"], "why": r["why"][:3]}
                              for r in matched])
        elif g["loose"]:
            row.update(verdict="none", why="no names on the loose screenshots")
        else:
            step = max(1, math.ceil(len(rows) / sample))
            row.update(why="no names; the image check decides",
                       sample=sorted(r["file"] for r in rows)[::step][:sample])
        if not g["loose"]:
            files = [f for f in Path(g["folder"]).rglob("*") if f.is_file() and f.name not in (".DS_Store", "fingerprint.md")]
            row.update(files=len(files), non_images=sum(1 for f in files if f.suffix.lower() not in IMAGE_EXTS),
                       secrets=[str(f.relative_to(g["folder"])) for f in files if SECRET.search(f.name)])
            if KEY_FOLDER.search(Path(g["folder"]).name):
                row["secrets"].insert(0, "(the folder's name says it holds keys)")
        out.append(row)
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("mode", choices=["shots", "folders", "to-read", "inside"])
    ap.add_argument("--projects", type=Path, required=True)
    ap.add_argument("--aliases", type=Path)
    ap.add_argument("--ocr", type=Path, action="append", help="batch_ocr.py JSON (shots, inside; repeatable)")
    ap.add_argument("--folders", type=Path, help="folders --out (to-read, inside)")
    ap.add_argument("--per-folder", type=int, default=80, help="most screenshots read per folder")
    ap.add_argument("--sample", type=int, default=5, help="screenshots per undecided folder for the image check")
    ap.add_argument("--desktop", type=Path, default=Path.home() / "Desktop")
    ap.add_argument("--burst", type=int, default=120, help="seconds that make one burst")
    ap.add_argument("--fingerprints", type=Path, action="append", help="fingerprint.py index --out (shots)")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--out", type=Path, help="write JSON rows here (to-read: the list of images, one per line)")
    a = ap.parse_args()
    projects, orgs = load_projects(a.projects, a.aliases)
    ocr = {}
    for f in a.ocr or []:
        ocr.update({unicodedata.normalize("NFC", k): v for k, v in json.loads(f.read_text()).items()})
    if a.mode in ("to-read", "inside") and not a.folders:
        sys.exit(f"{a.mode} needs --folders")
    if a.mode == "shots":
        if not ocr:
            sys.exit("shots mode needs --ocr")
        rows = match_shots(ocr, projects, orgs, a.burst)
        for f in a.fingerprints or []:
            apply_fingerprints(rows, ocr, json.loads(f.read_text()), projects)
    elif a.mode == "folders":
        aliases = json.loads(a.aliases.read_text()) if a.aliases and a.aliases.is_file() else {}
        rows = match_folders(a.desktop.expanduser(), projects, orgs, aliases.get("_folders", {}),
                             set(aliases.get("_skip", [])))
    elif a.mode == "to-read":
        groups = inside_groups(json.loads(a.folders.read_text()), a.per_folder)
        paths = [p for g in groups for p in g["images"]]
        if a.out:
            a.out.write_text("".join(p + "\n" for p in paths))
        for g in groups:
            print(f"{len(g['images']):4} of {g['total']:4}  {Path(g['folder']).relative_to(a.desktop.expanduser())}"
                  + ("  (loose screenshots)" if g["loose"] else ""))
        print(f"{len(paths)} screenshots in {len(groups)} folders to read"
              + (f"; list written to {a.out}" if a.out else ""))
        return
    else:
        groups = [{**g, "images": [unicodedata.normalize("NFC", p) for p in g["images"]]}
                  for g in inside_groups(json.loads(a.folders.read_text()), a.per_folder)]
        rows = judge_inside(groups, ocr, projects, orgs, a.burst, a.sample)
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
    elif a.mode == "inside":
        for r in rows:
            print(f"{r['verdict']:9} {r['project'] or '':30} {Path(r['folder']).relative_to(a.desktop.expanduser())}"
                  f"  ({r['why']})" + (f"  !! {len(r['secrets'])} key/secret files" if r.get("secrets") else ""))
    else:
        for r in rows:
            if r["kind"]:
                print(f"{r['kind']:8} {r['project'] or '?':34} <- "
                      f"{Path(r['folder']).relative_to(a.desktop.expanduser())}  ({r['files']} files, "
                      f"{r['non_images']} not images; {r['why']})"
                      + (f"  !! {len(r['secrets'])} key/secret files" if r["secrets"] else ""))


if __name__ == "__main__":
    main()
