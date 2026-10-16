#!/usr/bin/env python3
"""Ask about many unclear screenshots at once, in one Obsidian doc with the pictures and tick
boxes, and read the ticks back as answers.

AskUserQuestion fits 1-4 questions. A Desktop leaves dozens of screenshots unclear, so they
go into a review doc instead: one section per group of screenshots, the pictures shown, one
tick box per choice. The person ticks a box under each group, and leaves a comment with the
review-md Obsidian plugin (press c, click a picture or heading) when a box isn't enough.

    # 1. Draft the groups from the plan's leftovers: unsure screenshots taken close together
    #    on the same day form one group; each undecided folder and each folder held for key
    #    files is its own group. Edit titles, questions and choices in the JSON before writing.
    python3 review_doc.py draft --plan plan.json [--shots shots.json] [--gap 1800] \
        --out groups.json

    # 2. Write the doc: small copies of the pictures go to <vault>/images/<doc name>/, the doc to
    #    <vault>/<date> Screenshots to file.md, the groups beside it as .<doc name>.groups.json
    python3 review_doc.py write --groups groups.json --vault "<projects root>/_review"

    # 3. Read the ticks: answers for plan --vision, folder rules for the aliases file, and
    #    the key-file decisions as plan flags. Comments are read with `reviews list`.
    python3 review_doc.py read --doc "<vault>/<date> Screenshots to file.md" \
        --answers vision_answers_user.json [--aliases "<projects root>/.aliases.json"]

    # 4. After the moves, start the next doc from what is still open, and move the old doc to
    #    <vault>/done/. Then write the new one under its own name and open it in Obsidian.
    python3 review_doc.py carry --doc "<vault>/<date> Screenshots to file.md" --out next.json --retire
    python3 review_doc.py write --groups next.json --vault "<vault>" --name "<date> Screenshots to file, round 2"

groups.json:
    {"made": "2026-10-16", "plan": "<plan.json>", "none_count": 31,
     "groups": [{"id": "G01", "kind": "shots" | "folder" | "keys", "title": "...",
                 "ask": "Which project is this for?", "files": ["<path>", ...],
                 "captions": {"<path>": "what the image check saw"},
                 "folder": "<Desktop folder>  (kind folder/keys only)",
                 "choices": [{"label": "naqshcoffee", "value": "naqshcoffee", "why": "..."}],
                 "recommend": "naqshcoffee"}]}

Choice values: for "shots", a project or company name, "none" (not project work, stays on
the Desktop) or "folder:<Desktop folder>" (file it in that folder); for "folder", a project
name, or "none" (a life folder: added to _skip); for "keys", "keys-first" (its key files move
to --keys-to first, then the folder) or "leave". write adds "unsure" (ask again next time)
for shots and "other" (a comment says where) for every group.

The doc lives in its own small vault (<projects root>/_review), so Obsidian never indexes the
moved code folders; the scans skip _review. It holds private screenshots: never copy it, or
anything in it, into a repo.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import date, datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from match_projects import IMAGE_EXTS, shot_time  # noqa: E402
from move_to_projects import key  # noqa: E402

DESKTOP = Path.home() / "Desktop"
CHOICE = re.compile(r"^\s*[-*] \[(.)\] .*?%%\s*(.+?)\s*%%")
HEADING = re.compile(r"^## (G\d+)\b")
ALWAYS = {"shots": [{"label": "Not sure yet: ask me again next time", "value": "unsure"}],
          "folder": [], "keys": []}
OTHER = {"label": "Somewhere else: leave a comment on this group saying where", "value": "other"}


def log(ev: str, **kv) -> None:
    parts = " ".join(f"{k}={json.dumps(str(v), ensure_ascii=False) if ' ' in str(v) else v}"
                     for k, v in kv.items())
    print(f"{datetime.now(timezone.utc).isoformat(timespec='seconds')} pid={os.getpid()} ev={ev} {parts}",
          file=sys.stderr)


def when(path: str) -> str:
    t = shot_time(Path(path).name)
    return t.strftime("%b %-d, %-I:%M %p") if t else ""


def rel(path: str) -> str:
    p = Path(path)
    return str(p.relative_to(DESKTOP)) if p.is_relative_to(DESKTOP) else str(p)


def images_in(folder: Path, n: int) -> list[str]:
    found = sorted(f for f in folder.rglob("*") if f.is_file() and f.suffix.lower() in IMAGE_EXTS
                   and not any(part.startswith(".") for part in f.relative_to(folder).parts))
    step = max(1, len(found) // n)
    return [str(f) for f in found[::step][:n]]


def shot_groups(held: list[dict], cands: dict, gap: int, recommend: str | None = None) -> list[dict]:
    """One group per run of held screenshots taken on the same day within gap seconds of each other."""
    runs: list[list[dict]] = []
    for h in sorted(held, key=lambda h: shot_time(Path(h["src"]).name) or datetime.min):
        t = shot_time(Path(h["src"]).name)
        last = runs[-1][-1] if runs else None
        lt = shot_time(Path(last["src"]).name) if last else None
        if t and lt and t.date() == lt.date() and (t - lt).total_seconds() <= gap:
            runs[-1].append(h)
        else:
            runs.append([h])
    groups = []
    for run in runs:
        files = [h["src"] for h in run]
        names = []
        for f in files:
            names += [c for c in cands.get(key(f), []) if c not in names]
        groups.append({"kind": "shots", "title": run[0]["why"].removeprefix("image: ")[:70],
                       "ask": "Which project are these for?" if len(files) > 1 else "Which project is this for?",
                       "files": files, "captions": {h["src"]: h["why"].removeprefix("image: ") for h in run},
                       "choices": [{"label": n, "value": n} for n in names[:3]]
                       + [{"label": "Not project work: leave on the Desktop", "value": "none"}],
                       "recommend": recommend})
    return groups


def draft(a) -> None:
    plan = json.loads(a.plan.read_text())
    cands = {key(r["file"]): r.get("candidates", []) for r in json.loads(a.shots.read_text())} if a.shots else {}
    held = plan["held"]
    groups = shot_groups([h for h in held if h["reason"] == "unsure"], cands, a.gap)
    for h in held:
        if h["reason"] == "folder: undecided":
            folder = Path(h["src"])
            groups.append({"kind": "folder", "title": f"The {rel(h['src'])} folder", "folder": h["src"],
                           "ask": "Which project does this folder belong to?",
                           "files": images_in(folder, 4), "captions": {},
                           "choices": [{"label": "Not project work: leave it on the Desktop", "value": "none"}],
                           "recommend": None})
        elif h["reason"] == "has key/secret files":
            named = h["why"].startswith("(")
            choices = [{"label": "Leave the whole folder on the Desktop", "value": "leave"}]
            if not named:
                choices.insert(0, {"label": "Move its key files to the keys folder first, then move the folder",
                                   "value": "keys-first",
                                   "why": "keys stay in one known place; the project folder holds no secrets"})
            groups.append({"kind": "keys", "title": f"The {rel(h['src'])} folder holds key files",
                           "folder": h["src"], "ask": f"Key files in it: {h['why']}. What should happen?",
                           "files": [], "captions": {}, "choices": choices,
                           "recommend": "leave" if named else "keys-first"})
    for i, g in enumerate(groups, 1):
        g["id"] = f"G{i:02d}"
    out = {"made": date.today().isoformat(), "plan": str(a.plan),
           "none_count": sum(1 for h in held if h["reason"] == "none"), "groups": groups}
    a.out.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"{len(groups)} groups ({sum(len(g['files']) for g in groups if g['kind'] == 'shots')} screenshots) "
          f"written to {a.out}. Give each a plain title, a question and its choices, then run write.")


def thumb(src: str, dst: Path) -> bool:
    dst.parent.mkdir(parents=True, exist_ok=True)
    log("thumb_start", src=src)
    try:
        r = subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "1200", src, "--out", str(dst)],
                           capture_output=True, timeout=30)
    except subprocess.TimeoutExpired:
        log("thumb_timeout", src=src)
        return False
    ok = r.returncode == 0 and dst.is_file()
    log("thumb_done" if ok else "thumb_failed", src=src, dst=dst)
    return ok


def write(a) -> None:
    data = json.loads(a.groups.read_text())
    vault = a.vault.expanduser()
    made = data.get("made") or date.today().isoformat()
    doc = vault / f"{a.name or made + ' Screenshots to file'}.md"
    # One picture folder per doc, so a second doc made the same day keeps the first one's pictures.
    imgdir = Path("images") / doc.stem
    if doc.is_file() and not a.force and (any(ticks(doc)[0].values()) or ticks(doc)[1]):
        sys.exit(f"{doc} already has ticked boxes: run read first, or pass --force to start it over")
    lines = ["---", f"made: {made}", f"groups: {len(data['groups'])}", "---", "",
             "Some screenshots and folders on the Desktop could not be filed. Each group below shows "
             "them and asks one question.", "",
             "1. **Tick one box under each group.** The recommended choice is marked.",
             "2. **To say more,** comment on a picture or a group's heading: press `c`, click it, "
             "write, and press **Comment**.",
             "3. **When you're done,** tick the last box and tell Claude \"read my screenshot answers\".", "",
             "A group with no box ticked stays on the Desktop and comes back next time.", ""]
    for g in data["groups"]:
        n = len(g["files"])
        count = {"shots": f" ({n} screenshot{'s' if n != 1 else ''})"}.get(g["kind"], "")
        lines += [f"## {g['id']} · {g['title']}{count}", "", g["ask"], ""]
        if g.get("folder"):
            lines += [f"Folder: `{rel(g['folder'])}`", ""]
        rec = next((c for c in g["choices"] if c["value"] == g.get("recommend")), None)
        if rec:
            lines += [f"**Recommended:** {rec['label']}" + (f", because {rec['why']}" if rec.get("why") else ""), ""]
        # Pictures side by side (embeds on one line wrap like a gallery), so the tick boxes
        # stay close to the question; one caption line per picture under them.
        width = 560 if len(g["files"]) == 1 else 300
        shown, caps = [], []
        for i, f in enumerate(g["files"], 1):
            dst = imgdir / f"{g['id']}-{i}.jpg"
            cap = " · ".join(x for x in (when(f), g.get("captions", {}).get(f, "")) if x)
            if thumb(f, vault / dst):
                shown.append(f"![[{dst}|{width}]]")
                caps.append(f"{i}. {cap} `{Path(f).name}`")
            else:
                caps.append(f"{i}. *(could not show)* `{Path(f).name}`")
        if shown:
            lines += [" ".join(shown), ""]
        if caps:
            lines += caps + [""]
        for c in g["choices"] + ALWAYS[g["kind"]] + [OTHER]:
            mark = " **(recommended)**" if c["value"] == g.get("recommend") else ""
            why = f": {c['why']}" if c.get("why") and c is not rec else ""
            lines.append(f"- [ ] {c['label']}{mark}{why} %%{c['value']}%%")
        lines.append("")
    if data.get("none_count"):
        lines += ["## The rest", "",
                  f"{data['none_count']} more screenshots show no project work (shopping, forms, chats). "
                  "They stay on the Desktop.", "",
                  "- [ ] Show me these too next time %%show-none%%", ""]
    lines += ["---", "", "- [ ] I'm done: read my answers %%done%%", ""]
    vault.mkdir(parents=True, exist_ok=True)
    doc.write_text("\n".join(lines))
    (vault / f".{doc.stem}.groups.json").write_text(json.dumps(data, indent=1, ensure_ascii=False))
    print(f"wrote {doc} ({len(data['groups'])} groups)")


def ticks(doc: Path) -> tuple[dict[str, list[str]], set[str]]:
    """Ticked values per group id, and ticked values outside any group (done, show-none)."""
    per: dict[str, list[str]] = {}
    loose: set[str] = set()
    gid = None
    for line in doc.read_text().splitlines():
        if m := HEADING.match(line):
            gid = m.group(1)
            per.setdefault(gid, [])
        elif line.startswith("## ") or line.strip() == "---":
            # The rule above the "I'm done" box ends the last group, or done reads as its answer.
            gid = None
        elif (m := CHOICE.match(line)) and m.group(1) in "xX":
            (per[gid].append(m.group(2)) if gid else loose.add(m.group(2)))
    return per, loose


def plain(s: str) -> str:
    return s.replace(" ", " ").replace(" ", " ")


def comments(doc: Path, groups: list[dict]) -> list[dict]:
    """Open review-md threads on the doc, each placed on its group and, when it can be told,
    its picture: an image comment by the picture's file name (G12-3.jpg), a text comment by
    the line its block id sits on (a heading, a tick line, or the end of the caption list,
    which Obsidian treats as one block) and by the screenshot file name in its quote."""
    log("reviews_start", doc=doc)
    try:
        r = subprocess.run(["reviews", "list", str(doc), "--open", "--json"],
                           capture_output=True, text=True, timeout=30)
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        log("reviews_failed", err=type(e).__name__)
        return []
    log("reviews_done", code=r.returncode)
    if r.returncode != 0:
        return []
    lines = doc.read_text().splitlines()
    by_id = {g["id"]: g for g in groups}
    out = []
    for t in json.loads(r.stdout).get("threads", []):
        anchor, gid, pic = t.get("anchor", {}), None, None
        if m := re.search(r"/(G\d+)-(\d+)\.jpg", anchor.get("src", "")):
            gid, pic = m.group(1), int(m.group(2))
        elif bid := anchor.get("blockId"):
            at = next((i for i, ln in enumerate(lines) if ln.endswith(f"^{bid}")), None)
            for ln in reversed(lines[:at + 1] if at is not None else []):
                if m := HEADING.match(ln):
                    gid = m.group(1)
                    break
            quote = plain(anchor.get("quote", ""))
            for i, f in enumerate(by_id.get(gid, {}).get("files", []), 1):
                if plain(Path(f).name) in quote:
                    pic = i
        out.append({"id": t["id"], "group": gid, "picture": pic,
                    "said": " / ".join(m["body"] for m in t.get("messages", []))})
    return out


def read(a) -> None:
    doc = a.doc.expanduser()
    data = json.loads((doc.parent / f".{doc.stem}.groups.json").read_text())
    per, loose = ticks(doc)
    # --set G12=3d-models answers a whole group, --set G12.3=hifth one picture of it: what the
    # user wrote in a comment. A --set wins over a tick.
    whole, pics = {}, {}
    for s in a.set or []:
        m = re.fullmatch(r"(G\d+)(?:\.(\d+))?=(.+)", s)
        if not m:
            sys.exit(f"--set {s!r}: write it as G12=<project> or G12.3=<project>")
        (pics.__setitem__((m.group(1), int(m.group(2))), m.group(3)) if m.group(2)
         else whole.__setitem__(m.group(1), m.group(3)))
    answers = json.loads(a.answers.read_text()) if a.answers.is_file() else {}
    aliases = None if not a.aliases else json.loads(a.aliases.read_text()) if a.aliases.is_file() else {}
    filed, rules, keys, comment, open_, many = [], [], [], [], [], []
    for g in data["groups"]:
        got = [whole[g["id"]]] if g["id"] in whole else per.get(g["id"], [])
        mine = {i: v for (gid, i), v in pics.items() if gid == g["id"]}
        if g["kind"] == "shots" and mine:
            base = got[0] if len(got) == 1 and got[0] not in ("unsure", "other") else None
            reason = f"the user, review doc {data.get('made', '')}: {g['title']}"
            done = []
            for i, f in enumerate(g["files"], 1):
                v = mine.get(i, base)
                if v and v != "unsure":
                    answers[f] = ({"project": "none", "folder": v.removeprefix("folder:"), "reason": reason}
                                  if v.startswith("folder:") else {"project": v, "reason": reason})
                    done.append(f"{i}->{v}")
            filed.append(f"{g['id']} pictures {', '.join(done)}: {g['title']} "
                         f"({len(done)} of {len(g['files'])}; the rest stay)")
            continue
        if len(got) > 1:
            many.append(g["id"])
            continue
        if not got or got[0] == "unsure":
            open_.append(g["id"])
            continue
        v = got[0]
        if v == "other":
            comment.append(g["id"])
            continue
        reason = f"the user, review doc {data.get('made', '')}: {g['title']}"
        if g["kind"] == "shots":
            for f in g["files"]:
                answers[f] = ({"project": "none", "folder": v.removeprefix("folder:"), "reason": reason}
                              if v.startswith("folder:") else {"project": v, "reason": reason})
            filed.append(f"{g['id']} -> {v}: {g['title']} ({len(g['files'])})")
        elif g["kind"] == "folder":
            r = rel(g["folder"])
            rules.append(f"{g['id']} -> {v}: {r}")
            if aliases is not None:
                if v == "none":
                    aliases.setdefault("_skip", [])
                    aliases["_skip"] += [r] if r not in aliases["_skip"] else []
                else:
                    aliases.setdefault("_folders", {})[r] = v
        elif g["kind"] == "keys" and v == "keys-first":
            keys.append(g["folder"])
    a.answers.write_text(json.dumps(answers, indent=1, ensure_ascii=False))
    if aliases is not None and rules:
        a.aliases.write_text(json.dumps(aliases, indent=1, ensure_ascii=False))
    print(f"done box ticked: {'yes' if 'done' in loose else 'no'}")
    print(f"answers file: {a.answers} ({sum(1 for v in answers.values() if 'review doc' in v.get('reason', ''))} "
          "screenshots from review docs)")
    for title, rows in (("filed (write each in that place's fingerprint Guidance)", filed),
                        ("folder rules" + (" (added to the aliases file)" if aliases is not None and rules else ""), rules),
                        ("say where in a comment: run reviews list on the vault", comment),
                        ("more than one box ticked: ask again", many),
                        ("not answered or not sure yet: stay on the Desktop", open_)):
        if rows:
            print(f"\n{title}:")
            print("\n".join(f"  {r}" for r in rows))
    if keys:
        print("\nkey files move first; add to plan: --keys-to ~/Desktop/api-keys "
              + " ".join(f'--keys-from "{k}"' for k in keys))
    if "show-none" in loose:
        print("\nthe user wants the not-project-work screenshots in the next review doc too")
    threads = comments(doc, data["groups"])
    if threads:
        print("\nopen comments (turn each answer into --set G12=<project> or G12.3=<project>, run read "
              "again, then reply and resolve):")
        for t in threads:
            where = (t["group"] or "?") + (f" picture {t['picture']}" if t["picture"] else "")
            print(f"  {where} [{t['id']}]: {t['said']}")


def carry(a) -> None:
    """Start the next doc from what the last one left open: the groups with no answer (no box,
    "not sure", "somewhere else", or two boxes) whose screenshots or folder are still where they
    were. A screenshot that moved was answered, by a box or a comment, so it drops out. When
    "Show me these too next time" is ticked, the plan's not-project screenshots that are still
    there come in as groups too, with "not project work" recommended. With --retire the old
    doc, its groups and its comments go to <vault>/done/; its pictures stay."""
    doc = a.doc.expanduser()
    side = doc.parent / f".{doc.stem}.groups.json"
    data = json.loads(side.read_text())
    per, loose = ticks(doc)
    kept = []
    for g in data["groups"]:
        got = per.get(g["id"], [])
        if len(got) == 1 and got[0] not in ("unsure", "other"):
            continue
        if g["kind"] == "shots":
            files = [f for f in g["files"] if Path(f).is_file()]
            if not files:
                continue
            g = {**g, "files": files, "captions": {f: c for f, c in g.get("captions", {}).items() if f in files},
                 "was": g["id"]}
        elif not Path(g["folder"]).exists():
            continue
        else:
            g = {**g, "was": g["id"]}
        kept.append(g)
    print(f"{len(kept)} of {len(data['groups'])} groups still open")
    none_count = data.get("none_count", 0)
    if "show-none" in loose and data.get("plan"):
        held = [h for h in json.loads(Path(data["plan"]).read_text())["held"]
                if h["reason"] == "none" and Path(h["src"]).is_file()]
        added = shot_groups(held, {}, a.gap, recommend="none")
        kept += added
        none_count = 0
        print(f"show-none ticked: added {len(added)} groups of not-project screenshots ({len(held)} screenshots)")
    for i, g in enumerate(kept, 1):
        g["id"] = f"G{i:02d}"
    out = {**data, "made": date.today().isoformat(), "from": str(doc), "groups": kept, "none_count": none_count}
    a.out.write_text(json.dumps(out, indent=1, ensure_ascii=False))
    print(f"{len(kept)} groups ({sum(len(g['files']) for g in kept if g['kind'] == 'shots')} screenshots) "
          f"written to {a.out}")
    for g in kept:
        print(f"  {g['id']} ({'was ' + g['was'] if g.get('was') else 'not project work'}): {g['title']}")
    if a.retire:
        done = doc.parent / "done"
        done.mkdir(exist_ok=True)
        for f in (doc, side, doc.parent / f".{doc.stem}.comments.md"):
            if f.is_file():
                shutil.move(str(f), str(done / f.name))
                log("retired", src=f, dst=done / f.name)
        print(f"moved the old doc to {done}/")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("draft")
    p.add_argument("--plan", type=Path, required=True, help="move_to_projects.py plan --out")
    p.add_argument("--shots", type=Path, help="match_projects.py shots --out, for each shot's candidates")
    p.add_argument("--gap", type=int, default=1800, help="seconds between shots in one group")
    p.add_argument("--out", type=Path, required=True)
    p = sub.add_parser("write")
    p.add_argument("--groups", type=Path, required=True)
    p.add_argument("--vault", type=Path, required=True, help="the review vault, e.g. <projects root>/_review")
    p.add_argument("--name", help="the doc's name (default: '<date> Screenshots to file')")
    p.add_argument("--force", action="store_true", help="rewrite a doc that already has ticked boxes")
    p = sub.add_parser("read")
    p.add_argument("--doc", type=Path, required=True)
    p.add_argument("--answers", type=Path, required=True, help="merged into; pass it last to plan --vision")
    p.add_argument("--aliases", type=Path, help="add folder answers to its _folders / _skip")
    p.add_argument("--set", action="append", metavar="G12[.3]=VALUE",
                   help="an answer the user wrote in a comment, for a group or one picture of it (repeatable)")
    p = sub.add_parser("carry")
    p.add_argument("--doc", type=Path, required=True, help="the last doc, after read and the moves")
    p.add_argument("--out", type=Path, required=True, help="groups.json for the next write")
    p.add_argument("--retire", action="store_true", help="move the old doc and its files to <vault>/done/")
    p.add_argument("--gap", type=int, default=1800,
                   help="seconds between not-project shots in one group, when show-none is ticked")
    a = ap.parse_args()
    {"draft": draft, "write": write, "read": read, "carry": carry}[a.cmd](a)


if __name__ == "__main__":
    main()
