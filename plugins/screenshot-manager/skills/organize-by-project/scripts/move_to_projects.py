#!/usr/bin/env python3
"""Plan, make and undo the moves from the Desktop into the projects folder.

    # 0. Batch: split the screenshots the name match could not place, plus a few from each
    #    folder the look inside left undecided, into batch files, one per image-check agent.
    #    Each agent writes vision_answers_<n>.json.
    python3 move_to_projects.py batch --root "<projects root>" --shots shots.json \
        [--inside inside.json] [--fingerprints fingerprints.json] --size 40 [--start N] \
        --out-dir <work dir>

    # 1. Plan: read the matches, print the table, write the plan. Moves nothing.
    python3 move_to_projects.py plan --root "<projects root>" --shots shots.json \
        --folders folders.json [--inside inside.json] [--vision vision_answers_0.json ...] \
        [--keys-to ~/Desktop/api-keys --keys-from ~/Desktop/<folder>] --out plan.json

    # 2. Apply: write the undo list to <root>/.moves/<UTC time>.json FIRST, then move.
    python3 move_to_projects.py apply --plan plan.json [--only shots|folders]

    # 3. Undo one batch: move everything back where it came from, newest first.
    python3 move_to_projects.py undo --log "<root>/.moves/<UTC time>.json"

Layout (chosen 2026-10-16): grouped by company.
    <root>/<org>/<project>/screenshots/<screenshot>   a loose Desktop screenshot
    <root>/<org>/<project>/<Desktop folder>/          a Desktop folder, moved whole, name kept
    <root>/<org>/screenshots/ and <root>/<org>/<Desktop folder>/   work on the company as a whole
org is "personal" for ~/Workspace/git, else the git-<org> folder's name.

A screenshot's project comes from the image check (--vision) when there is one, else from
the name match. "none" and "unsure" stay on the Desktop, except that a "none" shot showing a
site only one Desktop folder's fingerprint has goes into that folder. An answer can name the
folder itself: {"<file>": {"project": "none", "folder": "<Desktop folder>", "reason": "..."}}.
A folder the look inside left undecided moves whole when at least 3 of its sampled shots
(or all, if fewer) are called for one project and none for another. An unsure screenshot taken within
--burst seconds of a decided one takes that one's project.

Never moved: a folder with key or secret files in it (listed, for you to decide), unless the
user named it in --keys-from: then its key files move to --keys-to/<folder name>/ first (kind
"key", run with the folders), and the folder moves without them. A folder named for keys
(api-keys) is never moved. Also never moved: an iCloud placeholder (".name.icloud": the file is not on this Mac yet).
"""
import argparse
import json
import os
import shutil
import sys
import unicodedata
from datetime import datetime, timezone
from pathlib import Path


def key(path: str) -> str:
    """macOS puts a narrow no-break space before AM/PM; image checkers often write a space."""
    return unicodedata.normalize("NFC", path).replace(" ", " ")


def log(ev: str, **kv) -> None:
    parts = " ".join(f"{k}={json.dumps(str(v), ensure_ascii=False) if ' ' in str(v) else v}"
                     for k, v in kv.items())
    print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} pid={os.getpid()} ev={ev} {parts}",
          file=sys.stderr)


def free_name(dst: Path, taken: set[str]) -> Path:
    """dst, or 'name (2).png' if dst (or a planned move) already uses that name."""
    n, cand = 2, dst
    while cand.exists() or str(cand) in taken:
        cand = dst.with_name(f"{dst.stem} ({n}){dst.suffix}")
        n += 1
    return cand


def batch(a) -> None:
    """Every unclear AND every none shot gets a look: "none" only means no project words."""
    root = a.root.expanduser()
    projects = json.loads((root / ".projects.json").read_text())["projects"]
    plist = [{k: p[k] for k in ("name", "org", "title", "active")} for p in projects]
    plist += [{"name": o, "org": o, "title": f"{o}: work on the company as a whole (no single repo)",
               "active": True} for o in sorted({p["org"] for p in projects}) if o != "personal"]
    todo = [{"file": s["file"], "candidates": s.get("candidates", [])}
            for s in (json.loads(a.shots.read_text()) if a.shots else []) if s["status"] != "matched"]
    # A folder no name placed sends a few of its screenshots; the answers decide the folder.
    for g in json.loads(a.inside.read_text()) if a.inside else []:
        todo += [{"file": f, "candidates": [], "folder": g["folder"]} for f in g.get("sample", [])]
    # What each folder's fingerprint says (top sites, the user's guidance), so the checker can
    # see what already belongs where. Only folders with a project or with guidance.
    folders = [{"folder": f["folder"], "project": f["project"],
                "sites": sorted(f["sites"], key=f["sites"].get, reverse=True)[:5], "guidance": f["guidance"]}
               for fp in a.fingerprints or [] for f in json.loads(fp.read_text()) if f["project"] or f["guidance"]]
    a.out_dir.mkdir(parents=True, exist_ok=True)
    n = a.start
    for n, i in enumerate(range(0, len(todo), a.size), start=a.start):
        part = todo[i: i + a.size]
        f = a.out_dir / f"vision_batch_{n}.json"
        f.write_text(json.dumps({"projects": plist, "folders": folders, "shots": part}, indent=1, ensure_ascii=False))
        print(f"{f}  {len(part)} shots")
    print(f"{len(todo)} shots in batches {a.start}..{n}; answers go to vision_answers_<n>.json")


def plan(a) -> None:
    root = a.root.expanduser()
    projects = json.loads((root / ".projects.json").read_text())["projects"]
    org_of = {p["name"]: p["org"] for p in projects}
    orgs = {p["org"] for p in projects}
    vision: dict[str, dict] = {}
    for f in a.vision or []:
        vision.update({key(k): v for k, v in json.loads(f.read_text()).items()})

    def home(project: str) -> Path | None:
        if project in orgs:
            return root / project
        if project in org_of:
            return root / org_of[project] / project
        return None

    shots = json.loads(a.shots.read_text()) if a.shots else []
    decided = []
    for s in shots:
        v = vision.get(key(s["file"]))
        if v and v.get("folder"):
            # The user named a Desktop folder for it (review_doc.py read): file it there.
            s = {**s, "suggest_folder": v["folder"], "suggest_why": ["the user's answer"]}
        project = v["project"] if v else (s["project"] if s["status"] == "matched" else "none")
        why = (f"image: {v['reason']}" if v else "name on screen: " + ", ".join(s["why"][:3]))
        decided.append({**s, "project": project, "why": why})
    # Unsure shots borrow a project from a decided shot taken moments before or after.
    timed = sorted((d for d in decided if d["time"]), key=lambda d: d["time"])
    for i, d in enumerate(timed):
        if d["project"] != "unsure":
            continue
        t = datetime.fromisoformat(d["time"])
        near = [o for o in timed[max(0, i - 4): i + 5] if o["project"] not in ("unsure", "none")
                and abs((datetime.fromisoformat(o["time"]) - t).total_seconds()) <= a.burst]
        if near:
            o = min(near, key=lambda o: abs((datetime.fromisoformat(o["time"]) - t).total_seconds()))
            d.update(project=o["project"], why=f"taken moments after/before {Path(o['file']).name}")

    moves, held, taken = [], [], set()
    for d in decided:
        src = Path(d["file"])
        dest = home(d["project"])
        if dest is None and d["project"] == "none" and d.get("suggest_folder"):
            # Not project work, and a site only one Desktop folder's fingerprint has shows on
            # it (match_projects.py --fingerprints): file it there, next to its kind.
            folder = Path(d["suggest_folder"])
            dst = free_name(folder / src.name, taken)
            taken.add(str(dst))
            moves.append({"kind": "shot", "project": "", "place": str(folder), "src": str(src), "dst": str(dst),
                          "why": f"{d['why']}; fingerprint: {', '.join(d.get('suggest_why', []))}"})
            continue
        if dest is None:
            held.append({"src": str(src), "reason": d["project"], "why": d["why"]})
            continue
        dst = free_name(dest / "screenshots" / src.name, taken)
        taken.add(str(dst))
        moves.append({"kind": "shot", "project": d["project"], "src": str(src), "dst": str(dst), "why": d["why"]})
    keys_from = {key(str(p.expanduser())) for p in a.keys_from or []}

    def move_folder(f: dict, project: str, why: str) -> None:
        src = Path(f["folder"])
        if f.get("secrets"):
            files = [s for s in f["secrets"] if not s.startswith("(")]
            if not (a.keys_to and key(str(src)) in keys_from and len(files) == len(f["secrets"])):
                held.append({"src": str(src), "reason": "has key/secret files", "why": ", ".join(f["secrets"][:3])})
                return
            # The user said where its keys go: they move out first, then the folder moves
            # without them. A folder named for keys is never moved this way.
            for s in files:
                dst = free_name(a.keys_to.expanduser() / src.name / s, taken)
                taken.add(str(dst))
                moves.append({"kind": "key", "project": "", "place": str(a.keys_to), "src": str(src / s),
                              "dst": str(dst), "why": f"key file out of {src.name} before it moves"})
        dst = free_name(home(project) / src.name, taken)
        taken.add(str(dst))
        moves.append({"kind": "folder", "project": project, "src": str(src), "dst": str(dst),
                      "why": why, "files": f["files"], "non_images": f["non_images"]})

    for f in json.loads(a.folders.read_text()) if a.folders else []:
        if f["project"] and f["kind"] != "unclear" and home(f["project"]):
            move_folder(f, f["project"], f["why"])
    # Folders placed by what their screenshots show (match_projects.py inside).
    for g in json.loads(a.inside.read_text()) if a.inside else []:
        src = Path(g["folder"])
        if g["verdict"] == "whole" and home(g["project"]):
            move_folder(g, g["project"], g["why"])
        elif g["verdict"] == "split":
            # Only the shots that name a project move, under the folder's name so it still
            # reads as one set at the destination. A container's loose shots go to screenshots/.
            for m in g["moves"]:
                if not home(m["project"]):
                    continue
                f = Path(m["file"])
                sub = Path("screenshots") / f.name if g["loose"] else Path(src.name) / f.relative_to(src)
                dst = free_name(home(m["project"]) / sub, taken)
                taken.add(str(dst))
                moves.append({"kind": "shot", "project": m["project"], "src": str(f), "dst": str(dst),
                              "why": "name on screen: " + ", ".join(m["why"])})
        elif g["verdict"] == "undecided":
            answers = [vision[key(f)]["project"] for f in g["sample"] if key(f) in vision]
            named = {p for p in answers if p not in ("none", "unsure")}
            need = min(3, len(g["sample"]))
            if len(named) == 1 and answers.count(next(iter(named))) >= need and home(next(iter(named))):
                p = next(iter(named))
                move_folder(g, p, f"image check: {answers.count(p)} of {len(answers)} sampled shots show {p}")
            elif answers and all(p == "none" for p in answers):
                held.append({"src": str(src), "reason": "folder: not project work",
                             "why": f"image check: all {len(answers)} sampled shots"})
            else:
                held.append({"src": str(src), "reason": "folder: undecided",
                             "why": "image check: " + (", ".join(answers) or "not checked yet")})
    out = {"root": str(root), "planned": datetime.now(timezone.utc).isoformat(timespec="seconds"),
           "moves": moves, "held": held}
    a.out.write_text(json.dumps(out, indent=2, ensure_ascii=False))
    by: dict[str, list[int]] = {}
    for m in moves:
        rel = (str(home(m["project"]).relative_to(root)) if m["project"]
               else "Desktop: " + str(Path(m["place"]).relative_to(Path.home() / "Desktop")))
        c = by.setdefault(rel, [0, 0, 0])
        if m["kind"] in ("shot", "key"):
            c[0] += 1
        else:
            c[1] += 1
            c[2] += m["files"]
    print(f"{'destination':42} {'shots':>5} {'folders':>7} {'files in them':>13}")
    for rel, (s, n, f) in sorted(by.items()):
        print(f"{rel:42} {s:5} {n:7} {f:13}")
    reasons: dict[str, int] = {}
    for h in held:
        r = {"none": "screenshots: not project work", "unsure": "screenshots: unsure"}.get(h["reason"], h["reason"])
        reasons[r] = reasons.get(r, 0) + 1
    print(f"\n{len(moves)} moves planned; {len(held)} left on the Desktop:")
    for r, n in sorted(reasons.items()):
        print(f"  {n:4}  {r}")
    print(f"plan written to {a.out}", file=sys.stderr)


def resolve(raw: str) -> Path | None:
    p = Path(raw)
    if p.exists():
        return p
    try:
        for entry in os.listdir(p.parent):
            if key(entry) == key(p.name):
                return p.parent / entry
    except FileNotFoundError:
        pass
    return None


def apply(a) -> None:
    pl = json.loads(a.plan.read_text())
    # Key files move with the folders pass, and come before their folder in the plan.
    kinds = {"shots": {"shot"}, "folders": {"key", "folder"}}.get(a.only)
    moves = [m for m in pl["moves"] if not kinds or m["kind"] in kinds]
    logdir = Path(pl["root"]) / ".moves"
    logdir.mkdir(parents=True, exist_ok=True)
    logfile = logdir / f"{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}.json"
    # The undo list goes to disk before the first move, so a crash mid-way can be undone.
    logfile.write_text(json.dumps({"plan": str(a.plan), "moves": moves}, indent=2, ensure_ascii=False))
    log("undo_list_written", path=logfile, moves=len(moves))
    done, failed = [], []
    for m in moves:
        src = resolve(m["src"])
        if src is None:
            failed.append({**m, "error": "not found"})
            log("move_skip", src=m["src"], reason="not_found")
            continue
        if src.name.endswith(".icloud") or (src.parent / f".{src.name}.icloud").exists():
            failed.append({**m, "error": "iCloud placeholder"})
            log("move_skip", src=src, reason="icloud_placeholder")
            continue
        dst = Path(m["dst"])
        if dst.exists():
            failed.append({**m, "error": "destination exists"})
            log("move_skip", src=src, reason="dst_exists")
            continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        log("move_start", src=src, dst=dst)
        shutil.move(str(src), str(dst))
        done.append({**m, "src": str(src)})
    logfile.write_text(json.dumps({"plan": str(a.plan), "moves": done, "failed": failed}, indent=2,
                                  ensure_ascii=False))
    log("apply_done", moved=len(done), failed=len(failed), undo=logfile)
    print(f"moved {len(done)}, skipped {len(failed)}. To undo: move_to_projects.py undo --log \"{logfile}\"")


def undo(a) -> None:
    moves = json.loads(a.log.read_text())["moves"]
    back = 0
    for m in reversed(moves):
        dst, src = Path(m["dst"]), Path(m["src"])
        if not dst.exists() or src.exists():
            log("undo_skip", dst=dst, reason="gone" if not dst.exists() else "src_taken")
            continue
        src.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(dst), str(src))
        back += 1
    log("undo_done", moved_back=back, of=len(moves))
    print(f"moved {back} of {len(moves)} back")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("batch")
    p.add_argument("--root", type=Path, required=True, help="the projects folder")
    p.add_argument("--shots", type=Path, help="match_projects.py shots --out")
    p.add_argument("--inside", type=Path, help="match_projects.py inside --out (sample shots of undecided folders)")
    p.add_argument("--size", type=int, default=40, help="shots per image-check agent")
    p.add_argument("--start", type=int, default=0, help="first batch number, to keep earlier batches")
    p.add_argument("--fingerprints", type=Path, action="append", help="fingerprint.py index --out")
    p.add_argument("--out-dir", type=Path, required=True)
    p = sub.add_parser("plan")
    p.add_argument("--root", type=Path, required=True, help="the projects folder")
    p.add_argument("--shots", type=Path, help="match_projects.py shots --out")
    p.add_argument("--folders", type=Path, help="match_projects.py folders --out")
    p.add_argument("--inside", type=Path, help="match_projects.py inside --out")
    p.add_argument("--vision", type=Path, action="append", help="image-check answers (repeatable)")
    p.add_argument("--burst", type=int, default=120)
    p.add_argument("--keys-to", type=Path, help="where key files go when a --keys-from folder moves")
    p.add_argument("--keys-from", type=Path, action="append",
                   help="a held folder with key files the user said may move once its keys are out (repeatable)")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("apply")
    p.add_argument("--plan", type=Path, required=True)
    p.add_argument("--only", choices=["shots", "folders"])
    p = sub.add_parser("undo")
    p.add_argument("--log", type=Path, required=True)
    a = ap.parse_args()
    {"batch": batch, "plan": plan, "apply": apply, "undo": undo}[a.cmd](a)


if __name__ == "__main__":
    main()
