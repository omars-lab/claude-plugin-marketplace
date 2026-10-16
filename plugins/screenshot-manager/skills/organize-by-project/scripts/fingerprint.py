#!/usr/bin/env python3
"""Write a fingerprint.md into every folder of screenshots: what its screenshots have in
common (web addresses, folder paths, recurring words, dates), so new screenshots can be
filed into it. The file also keeps a Guidance section: the user's answers about what
belongs there, added over time and never rewritten.

    # 1. Which screenshots to read (an even sample of --per-folder per folder)
    python3 fingerprint.py to-read --under ~/Desktop [--under "<projects root>"] --out list.txt

    # 2. Read them (macOS Vision), then write or refresh every fingerprint.md
    conda run -n screenshot-ocr python3 batch_ocr.py --list list.txt --out ocr.json
    python3 fingerprint.py build --under ~/Desktop --ocr ocr.json [--ocr more.json] \
        [--root "<projects root>"] [--folders folders.json] [--inside inside.json]

    # 3. Add what the user said to a folder's Guidance (dated, in plain words)
    python3 fingerprint.py note --folder "<folder>" --text "Shopify admin screens for the tea shop go here" \
        [--project tea-shop]   # only read when the folder has no fingerprint.md yet

    # 4. One JSON of every fingerprint, for match_projects.py shots --fingerprints and the
    #    image-check batches
    python3 fingerprint.py index --under ~/Desktop --under "<projects root>" --out fingerprints.json

A folder gets a fingerprint when it holds at least --min screenshots of its own (not counting
its subfolders). Folders other skills own (Screenshots/, the techniques folder), code folders
(node_modules, .git ...) and hidden folders are skipped.

Only web addresses and paths are name-like enough to file a screenshot by. Words are listed for
people and for the image check, never to decide; see
docs/issues/organize-by-project-word-matching.md.
"""
import argparse
import difflib
import json
import math
import re
import sys
import unicodedata
from datetime import date, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from match_projects import NOISE, OCR_EXTS, OWNED, SKIP_DIRS, shot_time  # noqa: E402

GUIDANCE = "## Guidance"
# Sites on screenshots of every kind of work. A fingerprint lists them for people, but they never
# point a screenshot at a folder: a folder's list keeps only its top sites, so a site everyone uses
# can look like one folder's own.
COMMON_SITES = {"claude.ai", "claude.com", "anthropic.com", "chatgpt.com", "openai.com", "example.com",
                "github.com", "gist.github.com", "google.com", "accounts.google.com", "docs.google.com",
                "drive.google.com", "mail.google.com", "console.cloud.google.com", "gmail.com",
                "youtube.com", "facebook.com", "instagram.com", "linkedin.com", "x.com", "twitter.com",
                "amazon.com", "apple.com", "icloud.com", "microsoft.com", "office.com", "outlook.com",
                "yahoo.com", "slack.com", "notion.so", "stackoverflow.com", "reddit.com", "wikipedia.org",
                "en.wikipedia.org", "medium.com", "localhost.com", "cdn.shopify.com", "shopify.com"}
DOMAIN = re.compile(r"(?<![\w@.-])((?:[a-z0-9][a-z0-9-]*\.)+(?:com|org|net|io|dev|app|ai|co|gov|edu|us|me|so"
                    r"|xyz|store|shop|site|page|cloud|tech|info|biz|ly|gg|tv|fm|uk|ca|lb|ae|sa))(?![\w-])")
# Matched against lower-cased text, so case is ignored ("/Users/" shows as "/users/"). Two
# folders at least, so a cut-off "~/Wor..." is not one. No ".sh" above: it is mostly script names.
PATH = re.compile(r"(?:~|/Users/[\w.-]+)((?:/[\w.@+-]+){2,3})", re.I)
WORD = re.compile(r"[a-z][a-z'-]{3,}")
STOP = {"this", "that", "with", "from", "have", "your", "will", "about", "when", "were", "been", "here",
        "there", "which", "would", "could", "should", "also", "just", "like", "than", "then", "some",
        "these", "those", "only", "very", "most", "much", "many", "such", "does", "done", "make", "made",
        "want", "need", "using", "used", "into", "onto", "where", "while", "please", "thank", "thanks"}


def nfc(s: str) -> str:
    return unicodedata.normalize("NFC", s)


# A screenshot: named like one, or a PNG. Phone photos (.jpg/.heic named IMG_...) are not.
SHOT_NAME = re.compile(r"^(screen ?shot|cleanshot|simulator screen|screen recording)", re.I)


def own_images(d: Path) -> list[Path]:
    return sorted(f for f in d.iterdir() if f.is_file() and f.suffix.lower() in OCR_EXTS
                  and (SHOT_NAME.match(f.name) or f.suffix.lower() == ".png"))


def screenshot_folders(under: Path, least: int, depth_limit: int = 3) -> list[Path]:
    """Every folder below `under` (not `under` itself, at most depth_limit deep) with `least`
    screenshots of its own."""
    out, stack = [], [(under, 0)]
    while stack:
        d, depth = stack.pop()
        try:
            # Saved web pages ("<page>_files") hold the page's images, not screenshots.
            subs = sorted(c for c in d.iterdir() if c.is_dir() and not c.name.startswith(".")
                          and c.name not in SKIP_DIRS and c.name not in OWNED
                          and not c.name.endswith(("_files", ".app")))
        except PermissionError:
            continue
        if depth < depth_limit:
            stack += [(c, depth + 1) for c in subs]
        if d != under and len(own_images(d)) >= least:
            out.append(d)
    return sorted(out)


def sample(imgs: list[Path], n: int) -> list[Path]:
    return imgs[::max(1, math.ceil(len(imgs) / n))]


def signals(text: str) -> tuple[set[str], set[str], set[str]]:
    t = nfc(text).lower()
    sites = {m.removeprefix("www.") for m in DOMAIN.findall(t)}
    paths = {"~" + m.rstrip(".,:;)") for m in PATH.findall(t)}
    words = {w.strip("'-") for w in WORD.findall(t)} - NOISE - STOP
    return sites, paths, words


def fold_misreads(c: dict[str, int]) -> dict[str, int]:
    """Count OCR misreads of a site or path ("tacebook.com" for "facebook.com") as the more
    common spelling they nearly match."""
    out: dict[str, int] = {}
    for v, n in sorted(c.items(), key=lambda kv: (-kv[1], kv[0])):
        near = next((k for k in out if abs(len(k) - len(v)) <= 2
                     and difflib.SequenceMatcher(None, k, v).ratio() >= 0.85), None)
        out[near or v] = out.get(near or v, 0) + n
    return out


def shot_day(f: Path) -> str:
    t = shot_time(f.name)
    return (t or datetime.fromtimestamp(f.stat().st_mtime)).date().isoformat()


def project_of(d: Path, root: Path | None, placed: dict[str, str]) -> str:
    """The project (or company) a folder belongs to: its place under the projects folder, else
    the nearest folder the match placed (folders.json / inside.json)."""
    if root and d.is_relative_to(root):
        parts = d.relative_to(root).parts
        orgs = {p.name for p in root.iterdir() if p.is_dir() and not p.name.startswith(".")}
        if parts and parts[0] in orgs:
            return parts[1] if len(parts) > 1 and (root / parts[0] / parts[1]).is_dir() \
                and parts[1] not in ("screenshots",) else parts[0]
    for p in [d, *d.parents]:
        if str(p) in placed:
            return placed[str(p)]
    return ""


def render(d: Path, under: Path, project: str, n_imgs: int, read: int, days: list[str],
           counts: dict[str, dict[str, int]], words: list[tuple[str, int]], guidance: str) -> str:
    rel = d.relative_to(under)
    lines = ["---", f"folder: {rel}", f"project: {project or '(none: not a project folder)'}",
             f"screenshots: {n_imgs}", f"read: {read}"]
    if days:
        lines += [f"first: {min(days)}", f"last: {max(days)}"]
    lines += [f"built: {date.today().isoformat()}", "---", "", f"# Fingerprint: {d.name}", "",
              "What the screenshots in this folder have in common, so new ones can be filed here. "
              "The sections above Guidance are rebuilt from the screenshots each run. Guidance is "
              "the user's word on what belongs here; it is only ever added to.", ""]

    def section(title: str, blurb: str, items: list[tuple[str, int]], fmt) -> None:
        lines.extend([f"## {title}", "", blurb, ""])
        lines.extend(fmt(k, v) for k, v in items) if items else lines.append("- (none found)")
        lines.append("")

    top = lambda c: sorted(c.items(), key=lambda kv: (-kv[1], kv[0]))[:15]  # noqa: E731
    section("Sites", "Web addresses that show on its screenshots.", top(counts["sites"]),
            lambda k, v: f"- `{k}`: {v} of {read} screenshots")
    section("Paths", "Folders on this Mac that show (terminal prompts, file paths).", top(counts["paths"]),
            lambda k, v: f"- `{k}`: {v} of {read}")
    section("Words", "Words common here and rare in other folders. For people and the image check only; "
            "words never decide where a screenshot goes.", words, lambda k, v: f"- {k} ({v})")
    lines.append(guidance.rstrip() + "\n" if guidance else f"{GUIDANCE}\n\n- (nothing yet)\n")
    return "\n".join(lines)


def kept_guidance(f: Path) -> str:
    if not f.is_file():
        return ""
    text = f.read_text()
    i = text.find(GUIDANCE)
    return text[i:] if i >= 0 else ""


def to_read(a) -> None:
    paths = []
    for under in a.under:
        for d in screenshot_folders(under.expanduser(), a.min, a.depth):
            paths += [str(p) for p in sample(own_images(d), a.per_folder)]
    a.out.write_text("".join(p + "\n" for p in paths))
    print(f"{len(paths)} screenshots to read; list written to {a.out}")


def build(a) -> None:
    ocr = {}
    for f in a.ocr:
        ocr.update({nfc(k): v for k, v in json.loads(f.read_text()).items()})
    placed = {}
    for f in [a.folders, a.inside]:
        for r in json.loads(f.read_text()) if f else []:
            if r.get("project") and r.get("kind") != "unclear" and r.get("verdict", "whole") == "whole":
                placed[r["folder"]] = r["project"]
    root = a.root.expanduser() if a.root else None
    folders = []
    for under in a.under:
        under = under.expanduser()
        for d in screenshot_folders(under, a.min, a.depth):
            imgs = own_images(d)
            read = [p for p in sample(imgs, a.per_folder) if nfc(str(p)) in ocr]
            per = [signals(ocr[nfc(str(p))].get("text") or "") for p in read]
            folders.append((under, d, imgs, read, per))
    # How many folders each word shows in, so a folder's words are the ones rare elsewhere.
    df: dict[str, int] = {}
    for *_, per in folders:
        for w in set().union(*(s[2] for s in per)) if per else ():
            df[w] = df.get(w, 0) + 1
    written = 0
    for under, d, imgs, read, per in folders:
        counts: dict[str, dict[str, int]] = {"sites": {}, "paths": {}, "words": {}}
        for sites, paths, words in per:
            for k, vals in (("sites", sites), ("paths", paths), ("words", words)):
                for v in vals:
                    counts[k][v] = counts[k].get(v, 0) + 1
        counts["sites"], counts["paths"] = fold_misreads(counts["sites"]), fold_misreads(counts["paths"])
        # A site or path on one screenshot of a small folder still says something; a word on
        # one screenshot does not.
        least = 1 if len(read) <= 3 else 2
        for k in counts:
            counts[k] = {v: n for v, n in counts[k].items() if n >= (2 if k == "words" else least)}
        idf = {w: n * math.log(len(folders) / df[w]) for w, n in counts["words"].items() if df[w] <= max(2, len(folders) // 10)}
        words = [(w, counts["words"][w]) for w, _ in sorted(idf.items(), key=lambda kv: -kv[1])[:15]]
        f = d / "fingerprint.md"
        text = render(d, under, project_of(d, root, placed), len(imgs), len(read),
                      [shot_day(p) for p in imgs], counts, words, kept_guidance(f))
        if a.dry_run:
            print(f"--- {f}\n{text}")
        else:
            f.write_text(text)
        written += 1
        print(f"ev=fingerprint folder={json.dumps(str(d.relative_to(under)), ensure_ascii=False)} "
              f"read={len(read)} of={len(imgs)} sites={len(counts['sites'])} paths={len(counts['paths'])}",
              file=sys.stderr)
    print(f"{'would write' if a.dry_run else 'wrote'} {written} fingerprint.md files")


def note(a) -> None:
    d = a.folder.expanduser()
    f = d / "fingerprint.md"
    line = f"- {date.today().isoformat()}: {a.text.strip()}\n"
    if not f.is_file():
        # A project's folder in the projects root may not exist before its first move.
        d.mkdir(parents=True, exist_ok=True)
        project = a.project or "(none: not a project folder)"
        f.write_text(f"---\nfolder: {d.name}\nproject: {project}\nscreenshots: 0\nread: 0\n"
                     f"built: {date.today().isoformat()}\n---\n\n# Fingerprint: {d.name}\n\n{GUIDANCE}\n\n")
    text = f.read_text()
    if GUIDANCE not in text:
        text = text.rstrip() + f"\n\n{GUIDANCE}\n\n"
    text = text.replace("- (nothing yet)\n", "").rstrip()
    f.write_text(text + ("\n\n" if text.endswith(GUIDANCE) else "\n") + line)
    print(f"added to {f}: {line.strip()}")


def parse(f: Path) -> dict:
    text = f.read_text()
    meta = dict(re.findall(r"^(\w+): (.*)$", text.split("\n---", 1)[0], re.M))
    out = {"folder": str(f.parent), "project": "" if meta.get("project", "").startswith("(") else meta.get("project", ""),
           "screenshots": int(meta.get("screenshots", 0) or 0), "sites": {}, "paths": {}, "words": [], "guidance": []}
    sect = None
    for line in text.splitlines():
        if line.startswith("## "):
            sect = line[3:].strip().lower()
        elif line.startswith("- ") and "(none found)" not in line and "(nothing yet)" not in line:
            if sect in ("sites", "paths"):
                m = re.match(r"- `([^`]+)`: (\d+)", line)
                if m:
                    out[sect][m.group(1)] = int(m.group(2))
            elif sect == "words":
                out["words"].append(line[2:].split(" (")[0])
            elif sect == "guidance":
                out["guidance"].append(line[2:])
    return out


def index(a) -> None:
    rows = [parse(f) for under in a.under for f in sorted(under.expanduser().rglob("fingerprint.md"))
            if not SKIP_DIRS & set(f.parts)]
    a.out.write_text(json.dumps(rows, indent=1, ensure_ascii=False))
    print(f"{len(rows)} fingerprints written to {a.out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("to-read", "build", "index"):
        p = sub.add_parser(name)
        p.add_argument("--under", type=Path, action="append", required=True, help="a folder tree (repeatable)")
        p.add_argument("--min", type=int, default=3, help="screenshots a folder needs of its own")
        p.add_argument("--per-folder", type=int, default=80, help="most screenshots read per folder")
        p.add_argument("--depth", type=int, default=3, help="how many folders deep to look")
        if name == "build":
            p.add_argument("--ocr", type=Path, action="append", required=True, help="batch_ocr.py JSON (repeatable)")
            p.add_argument("--root", type=Path, help="the projects folder: its folders' project is their place in it")
            p.add_argument("--folders", type=Path, help="match_projects.py folders --out (projects of Desktop folders)")
            p.add_argument("--inside", type=Path, help="match_projects.py inside --out")
            p.add_argument("--dry-run", action="store_true", help="print the files instead of writing them")
        if name in ("to-read", "index"):
            p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("note")
    p.add_argument("--folder", type=Path, required=True)
    p.add_argument("--text", required=True, help="what the user said belongs (or doesn't) here, in plain words")
    p.add_argument("--project", help="the folder's project, for a fingerprint.md this makes new")
    a = ap.parse_args()
    {"to-read": to_read, "build": build, "note": note, "index": index}[a.cmd](a)


if __name__ == "__main__":
    main()
