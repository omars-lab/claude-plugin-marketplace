# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml>=6", "playwright==1.63.0"]
# ///
"""Keep a list of reference sites and repos, screenshot them, and lay our page beside them.

    uv run references.py check                                  # is the list well formed?
    uv run references.py shoot --ids a,b                        # shots of listed references
    uv run references.py shoot --url <address> --name ours-lifecycle   # a shot of any page, ours included
    uv run references.py sheet --ours ours-lifecycle --ids a,b --title Lifecycle

The list is --list, else $HUBS_REPO/references.yaml, else ~/Workspace/git/hubs/references.yaml.
Shots go to --out, else .cache/references/ next to the list: <name>/desktop.png and phone.png.
The browser only reads: every request that is not GET or HEAD is refused, and dialogs are
dismissed, so a shot can't submit, sign up or buy anything. Logs one line per event to
<out>/references.log. Playwright is pinned to 1.63.0 to reuse the Chromium already cached for it.
"""
import argparse
import html
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

KINDS = {"site", "repo"}
GOOD_FOR = {"sidebar", "calendar", "board", "table", "filing", "stats", "review", "landing", "forms", "type"}
SIZES = {
    "desktop": {"viewport": {"width": 1280, "height": 820}},
    "phone": {"viewport": {"width": 390, "height": 844}, "is_mobile": True, "has_touch": True},
}
LOAD_MS, SETTLE_MS = 20000, 1500
ID = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")


def default_list() -> Path:
    hubs = Path(os.environ.get("HUBS_REPO") or Path.home() / "Workspace/git/hubs")
    return hubs / "references.yaml"


def log(out: Path, ev: str, **kv) -> None:
    out.mkdir(parents=True, exist_ok=True)
    parts = [datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), f"pid={os.getpid()}", f"ev={ev}"]
    for k, v in kv.items():
        v = str(v)
        parts.append(f'{k}="{v}"' if (" " in v or not v) else f"{k}={v}")
    with open(out / "references.log", "a") as f:
        f.write(" ".join(parts) + "\n")


# --------------------------------------------------------------------------- the list

def load(path: Path) -> list[dict]:
    import yaml

    if not path.is_file():
        sys.exit(f"no references list at {path}; start one (see SKILL.md, 'Where the list lives') or pass --list")
    data = yaml.safe_load(path.read_text()) or {}
    return data.get("references") or []


def problems(refs: list[dict]) -> list[str]:
    """What is wrong with the list, one line each; empty when it is fine."""
    out, seen = [], set()
    for n, r in enumerate(refs, 1):
        rid = r.get("id") or f"entry {n}"
        if not ID.match(str(r.get("id") or "")):
            out.append(f"{rid}: id must be short-kebab-case")
        if rid in seen:
            out.append(f"{rid}: listed twice")
        seen.add(rid)
        for field in ("name", "kind", "url", "good_for", "borrow", "checked"):
            if not r.get(field):
                out.append(f"{rid}: missing {field}")
        if r.get("kind") and r["kind"] not in KINDS:
            out.append(f"{rid}: kind is {r['kind']!r}, not site or repo")
        if r.get("kind") == "repo":
            for field in ("repo", "license", "tokens"):
                if not r.get(field):
                    out.append(f"{rid}: a repo needs {field}")
        unknown = set(r.get("good_for") or []) - GOOD_FOR
        if unknown:
            out.append(f"{rid}: good_for has {', '.join(sorted(unknown))}; use {', '.join(sorted(GOOD_FOR))}")
        if r.get("found_by") and r["found_by"] not in ("both", "a", "b"):
            out.append(f"{rid}: found_by is {r['found_by']!r}, not both, a or b")
        if r.get("url") and not str(r["url"]).startswith(("http://", "https://")):
            out.append(f"{rid}: url must start with http:// or https://")
    return out


# --------------------------------------------------------------------------- shots

def shoot(targets: list[tuple[str, str]], out: Path, full: bool = False) -> list[dict]:
    """Screenshot each (name, url) at desktop and phone width into out/<name>/."""
    from playwright.sync_api import Error as PwError, TimeoutError as PwTimeout, sync_playwright

    results = []
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        for name, url in targets:
            folder = out / name
            folder.mkdir(parents=True, exist_ok=True)
            entry = {"name": name, "url": url, "shots": {}, "notes": {}}
            for size, opts in SIZES.items():
                ctx = browser.new_context(**opts, service_workers="block")
                ctx.route("**/*", lambda route: route.continue_() if route.request.method in ("GET", "HEAD")
                          else route.abort())
                page = ctx.new_page()
                page.on("dialog", lambda d: d.dismiss())
                log(out, "shot_start", name=name, size=size, url=url)
                try:
                    resp = page.goto(url, wait_until="load", timeout=LOAD_MS)
                    if resp is not None and resp.status >= 400:
                        entry["notes"][size] = f"answered {resp.status}"
                    page.wait_for_timeout(SETTLE_MS)
                    page.screenshot(path=str(folder / f"{size}.png"), full_page=full, timeout=LOAD_MS)
                    entry["shots"][size] = f"{size}.png"
                except PwTimeout:
                    entry["notes"][size] = f"still loading after {LOAD_MS // 1000} s"
                    log(out, "shot_timeout", name=name, size=size)
                except PwError as e:
                    entry["notes"][size] = str(e).splitlines()[0][:160]
                    log(out, "shot_fail", name=name, size=size, msg=entry["notes"][size])
                finally:
                    ctx.close()
                log(out, "shot_done", name=name, size=size, ok=size in entry["shots"])
            (folder / "shots.json").write_text(json.dumps(entry, indent=2) + "\n")
            results.append(entry)
        browser.close()
    return results


# --------------------------------------------------------------------------- the side-by-side sheet

def sheet(out: Path, ours: str, ids: list[str], refs: dict[str, dict], title: str) -> Path:
    """One HTML page: our page and each reference, desktop row then phone row, same scale."""
    cols = [ours] + ids

    def cell(name: str, size: str) -> str:
        shot = out / name / f"{size}.png"
        ref = refs.get(name, {})
        label = html.escape(ref.get("name") or name)
        borrow = "".join(f"<li>{html.escape(str(b))}</li>" for b in ref.get("borrow") or [])
        img = (f'<a href="{html.escape(str(shot))}"><img src="{html.escape(shot.as_uri())}" alt=""></a>'
               if shot.is_file() else '<div class="none">no shot</div>')
        return (f'<figure class="{size}"><figcaption><b>{label}</b>'
                f'{" (ours)" if name == ours else ""}</figcaption>{img}'
                f'{f"<ul>{borrow}</ul>" if borrow and size == "desktop" else ""}</figure>')

    rows = "".join(f'<section><h2>{size}</h2><div class="row">{"".join(cell(c, size) for c in cols)}</div></section>'
                   for size in SIZES)
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(title)} beside its references</title>
<style>
  body {{ margin: 0; padding: 16px; font: 14px/1.45 system-ui, sans-serif; background: #f4f3ef; color: #1d1d1b; }}
  h1 {{ font-size: 20px; margin: 0 0 4px; }} h2 {{ font-size: 13px; text-transform: uppercase; letter-spacing: .08em; color: #6b6a65; }}
  .row {{ display: flex; gap: 16px; overflow-x: auto; align-items: flex-start; }}
  figure {{ margin: 0; flex: none; }} figure.desktop {{ width: 520px; }} figure.phone {{ width: 220px; }}
  figure img {{ display: block; width: 100%; border: 1px solid #d8d6cf; border-radius: 6px; }}
  figcaption {{ margin-bottom: 6px; }} ul {{ margin: 6px 0 0; padding-left: 18px; color: #4a4945; }}
  .none {{ height: 160px; display: grid; place-items: center; border: 1px dashed #c9c7c0; color: #8a8983; }}
</style></head><body>
<h1>{html.escape(title)}: ours beside {len(ids)} reference{'' if len(ids) == 1 else 's'}</h1>
<p>Same width, same scale. Under each reference, the things the list says to borrow.</p>
{rows}
</body></html>
"""
    path = out / f"sheet-{ours}.html"
    path.write_text(page)
    return path


# --------------------------------------------------------------------------- command line

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--list", type=Path, default=None, help="the references file (default: the hubs repo's)")
    ap.add_argument("--out", type=Path, default=None, help="where shots go (default: .cache/references/ beside the list)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("check", help="say what is wrong with the list")
    s = sub.add_parser("shoot", help="screenshot references, or any one page")
    s.add_argument("--ids", help="comma-separated ids from the list (default: all)")
    s.add_argument("--url", help="shoot this address instead of the list; --name names its folder")
    s.add_argument("--name", help="the folder for --url, e.g. ours-lifecycle")
    s.add_argument("--full", action="store_true", help="the whole page, not just the first screen")
    h = sub.add_parser("sheet", help="lay one of our shots beside references, as an HTML page")
    h.add_argument("--ours", required=True, help="the folder name our page was shot into")
    h.add_argument("--ids", required=True, help="comma-separated reference ids")
    h.add_argument("--title", default="Our page")
    a = ap.parse_args(argv)

    lst = a.list or default_list()
    out = a.out or lst.parent / ".cache" / "references"

    if a.cmd == "check":
        refs = load(lst)
        found = problems(refs)
        for line in found:
            print(line)
        print(f"{lst}: {len(refs)} references, {len(found)} problem{'' if len(found) == 1 else 's'}")
        return 1 if found else 0

    if a.cmd == "shoot":
        if a.url:
            if not a.name or not ID.match(a.name):
                ap.error("--url needs --name in short-kebab-case")
            targets = [(a.name, a.url)]
        else:
            refs = load(lst)
            want = set(a.ids.split(",")) if a.ids else None
            targets = [(r["id"], r["url"]) for r in refs if want is None or r["id"] in want]
            missing = (want or set()) - {t[0] for t in targets}
            if missing:
                ap.error(f"not in {lst}: {', '.join(sorted(missing))}")
        for e in shoot(targets, out, a.full):
            got = ", ".join(e["shots"]) or "nothing"
            notes = "; ".join(f"{k}: {v}" for k, v in e["notes"].items())
            print(f"{e['name']}: {got}{f'  ({notes})' if notes else ''}  -> {out / e['name']}")
        return 0

    refs = {r["id"]: r for r in load(lst)} if lst.is_file() else {}
    print(sheet(out, a.ours, a.ids.split(","), refs, a.title))
    return 0


if __name__ == "__main__":
    sys.exit(main())
