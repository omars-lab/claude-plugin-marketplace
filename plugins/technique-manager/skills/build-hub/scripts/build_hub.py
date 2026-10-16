#!/usr/bin/env python3
"""Build the hub site in <hub>/.cache/hub/ from the already-rendered views (render_page.py):

    index.html          the hub gallery: every technique with its status and focus, linking
                        to its internal page (recreation, original, replacements, session)
    waiting.html        everything waiting on a person: comments, suggestions to confirm,
                        techniques with no focus or no context, sessions not archived yet
    internal/index.html the internal gallery     post/index.html  the post gallery

Page comments serve this folder (`.page-comments/run serve --root .cache/hub`). Cards and
terminal blocks carry stable data-comment-id anchors (<slug>, <slug>:b<i>).

Usage:
    python3 build_hub.py [--root R] [--title T]
Output (JSON): {"index", "cards", "views": [...]}
"""
import argparse
import datetime as dt
import json
import subprocess
import sys
from pathlib import Path

SKILLS = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(SKILLS / "recreate-technique" / "scripts"))
sys.path.insert(0, str(SKILLS / "package-gallery" / "scripts"))
import lib  # noqa: E402
import build_gallery  # noqa: E402


WAITING_TEMPLATE = Path(__file__).resolve().parent.parent / "templates" / "waiting.html"


def open_threads(root: Path) -> list[dict]:
    """Open page-comment threads, read through the comment store's own CLI (threads are
    append-only event files; folding them is its job)."""
    run = root / ".page-comments" / "run"
    if not run.exists():
        return []
    r = subprocess.run([str(run), "list", "--open", "--json"], cwd=root, capture_output=True, text=True)
    if r.returncode != 0:
        return []
    out = []
    for page in json.loads(r.stdout).get("files", []):
        for t in page.get("threads", []):
            msgs = t.get("messages") or [{}]
            out.append({"id": t.get("id"), "page": page.get("file"), "waiting": t.get("waiting"),
                        "anchor": (t.get("anchor") or {}).get("commentId"), "first": msgs[0].get("body", ""),
                        "lost": t.get("lost")})
    return out


def cleanup_days() -> int:
    settings = Path.home() / ".claude" / "settings.json"
    try:
        return int(json.loads(settings.read_text(encoding="utf-8")).get("cleanupPeriodDays", 30))
    except (OSError, ValueError):
        return 30


def waiting(root: Path) -> dict:
    specs = lib.load_specs(root)
    page = lambda slug: f"internal/{slug}.html"
    title = lambda sp: (sp.get("technique") or {}).get("title", sp["slug"])
    threads = open_threads(root)
    you = [t for t in threads if t["waiting"] != "claude"]
    claude = [t for t in threads if t["waiting"] == "claude"]
    thread_item = lambda t: {"slug": (t["anchor"] or "").split(":")[0] or None, "href": (t["page"] or "/").lstrip("/") or "index.html",
                             "title": " ".join(t["first"].split())[:90] or t["id"],
                             "detail": f"{t['id']}" + (", not found on the page" if t["lost"] else "")}
    suggested, no_focus, no_context, sessions = [], [], [], []
    days, now = cleanup_days(), dt.datetime.now(dt.timezone.utc)
    for sp in specs:
        f, c = sp.get("focus") or {}, sp.get("context") or {}
        item = {"slug": sp["slug"], "href": page(sp["slug"]), "title": title(sp)}
        if c.get("suggested_focus") or c.get("suggested_backstory") or (f.get("line") and not f.get("confirmed")):
            suggested.append(dict(item, detail="reply \"yes\" on the suggestion to use it"))
        if not f.get("confirmed"):
            no_focus.append(dict(item, detail="comment \"this is the point\" on a terminal line"))
        sess = (sp.get("source") or {}).get("session") or {}
        if sess and not c.get("fetched"):
            no_context.append(dict(item, detail="comment \"fetch what led here\""))
        if sess and not sess.get("archived"):
            gone = not Path(sess.get("path", "")).exists()
            when = dt.datetime.fromisoformat(sess["timestamp"].replace("Z", "+00:00")) + dt.timedelta(days=days) if sess.get("timestamp") else None
            detail = "gone, never archived" if gone else f"run make archive; deleted around {when:%Y-%m-%d}" if when else "run make archive"
            sessions.append(dict(item, detail=detail))
    return {"title": "Waiting on you", "backHref": "index.html", "sections": [
        {"key": "you", "title": "Comment replies waiting on you", "items": [thread_item(t) for t in you]},
        {"key": "suggested", "title": "Suggestions to confirm", "items": suggested},
        {"key": "sessions", "title": "Sessions not archived", "hint": f"Claude Code deletes session files after {days} days.", "items": sessions},
        {"key": "focus", "title": "No focus yet", "items": no_focus},
        {"key": "context", "title": "No context yet", "items": no_context},
        {"key": "claude", "title": "Comments Claude hasn't answered yet", "hint": "Open a Claude session in the hub; it hears them.", "items": [thread_item(t) for t in claude]},
    ]}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root")
    ap.add_argument("--title", default="Technique hub")
    args = ap.parse_args()
    root = lib.find_root(args.root)
    if not lib.is_hub(root):
        raise SystemExit(f"{root} is not a hub (no {lib.HUB_FILE}); run migrate_to_hub.py first")

    views = [build_gallery.build(root, v, args.title) for v in lib.VIEWS]
    site = lib.pages_dir(root)
    lib.sync_lib(site)

    # The front page is the internal gallery, re-pointed from the site root.
    cards = [dict(c, href=f"internal/{c['href']}", image=f"internal/{c['image']}" if c.get("image") else None)
             for c in build_gallery.cards_for(root, "internal")[0]]
    wait = waiting(root)
    (site / "waiting.html").write_text(lib.fill(WAITING_TEMPLATE, wait["title"], wait, lib.prerender("Waiting", wait)),
                                       encoding="utf-8")
    count = sum(len(s["items"]) for s in wait["sections"])
    extra = {"links": [{"href": "waiting.html", "label": f"Waiting on you ({count})"},
                       {"href": "post/index.html", "label": "Post gallery"}]}
    index = site / "index.html"
    index.write_text(lib.fill(build_gallery.TEMPLATE, args.title, cards,
                              lib.prerender("Gallery", dict(extra, title=args.title, cards=cards)), extra), encoding="utf-8")
    print(json.dumps({"index": str(index), "cards": len(cards), "waiting": {s["key"]: len(s["items"]) for s in wait["sections"]},
                      "views": views}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
