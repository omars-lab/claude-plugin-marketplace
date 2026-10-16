"""Shared helpers for technique-manager scripts: paths, the component library, templates.

Imported by recreate-technique/scripts/*.py and package-gallery/scripts/*.py.
"""
import json
import re
import shutil
import subprocess
import unicodedata
from pathlib import Path

SKILL_DIR = Path(__file__).resolve().parent.parent
COMPONENTS_DIR = SKILL_DIR / "components"
PAGE_TEMPLATE = SKILL_DIR / "templates" / "page.html"

DEFAULT_ROOT = Path.home() / "Desktop" / "📸 Screenshots of Techniques"
# Which root to use when no --root is given: {"root": "~/workspace/technique-hub"}. migrate_to_hub.py
# writes it, so every script switches to the hub at once.
SETTINGS = Path.home() / ".config" / "technique-manager" / "settings.json"
# A hub root is a private git repo with this file (see build-hub). It keeps specs in specs/, builds
# pages into .cache/hub/, and reads screenshots from the folder named in it.
HUB_FILE = "hub.json"


# Every spec renders twice:
#   internal/  the faithful transcription, the original screenshot beside it, the list of
#              replacements and the source session. For checking; never shared.
#   post/      redactions applied, no screenshot, no session. The shareable, blog-ready view.
VIEWS = ("internal", "post")
SHARED_REDACTIONS = "_redactions.json"   # in specs/: replacements that apply to every spec


def is_hub(root: Path) -> bool:
    return (root / HUB_FILE).exists()


def hub_settings(root: Path) -> dict:
    return json.loads((root / HUB_FILE).read_text(encoding="utf-8")) if is_hub(root) else {}


def pages_dir(root: Path, view: str | None = None) -> Path:
    base = root / ".cache" / "hub" if is_hub(root) else root / "pages"
    return base / view if view else base


def specs_dir(root: Path) -> Path:
    return root / "specs" if is_hub(root) else pages_dir(root) / "specs"


def screenshots_dir(root: Path) -> Path:
    """Where the original screenshots are: the hub's "screenshots" setting, else the root itself."""
    shots = hub_settings(root).get("screenshots")
    return find_root(shots) if shots else root


def archive_dir(root: Path) -> Path:
    """Copies of linked sessions, kept before Claude Code deletes the originals (hub only)."""
    return root / "archive" / "sessions"


def default_root() -> Path:
    if SETTINGS.exists():
        raw = json.loads(SETTINGS.read_text(encoding="utf-8")).get("root")
        if raw:
            return Path(raw).expanduser()
    return DEFAULT_ROOT


def find_root(raw: str | None) -> Path:
    """Resolve the techniques folder, tolerating NFC/NFD differences in the emoji name."""
    root = Path(raw).expanduser() if raw else default_root()
    if root.exists():
        return root
    for form in ("NFC", "NFD"):
        alt = Path(unicodedata.normalize(form, str(root)))
        if alt.exists():
            return alt
    raise SystemExit(f"Techniques folder not found: {root}")


def sync_lib(pages: Path) -> Path:
    """Copy the component library into pages/_lib so every page loads the same files."""
    lib = pages / "_lib"
    if lib.exists():
        shutil.rmtree(lib)
    # The server renderer is only for prerender.js; browsers never load it.
    shutil.copytree(COMPONENTS_DIR, lib, ignore=shutil.ignore_patterns(".DS_Store", "react-dom-server*"))
    return lib


PRERENDER = Path(__file__).resolve().parent / "prerender.js"


def prerender(component: str, props: dict) -> str:
    """Static HTML for one component, rendered by Node with the same claude-ui.js.

    Pages need it to show in places that run no JavaScript: macOS Quick Look and Finder
    previews, iCloud previews, feed readers. Returns "" (and the page stays JS-only) when
    Node isn't installed; render_page.py reports that.
    """
    if not shutil.which("node"):
        return ""
    r = subprocess.run(["node", str(PRERENDER)], input=json.dumps([{"component": component, "props": props}]),
                       capture_output=True, text=True)
    if r.returncode != 0:
        raise SystemExit(f"prerender.js failed: {r.stderr.strip().splitlines()[-1:] or r.stderr}")
    return json.loads(r.stdout)[0]


def block_types() -> set[str]:
    """Block types claude-ui.js can render, read from its BLOCKS registry."""
    src = (COMPONENTS_DIR / "claude-ui.js").read_text(encoding="utf-8")
    m = re.search(r"var BLOCKS = \{(.*?)\n  \};", src, re.S)
    if not m:
        raise SystemExit("Could not find the BLOCKS registry in claude-ui.js")
    return set(re.findall(r"^\s+(\w+): function", m.group(1), re.M))


def embed_json(data) -> str:
    """JSON safe to place inside <script type="application/json">."""
    return (json.dumps(data, ensure_ascii=False, indent=1)
            .replace("</", "<\\/").replace("<!--", "<\\!--"))


def html_escape(text: str) -> str:
    return (text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace('"', "&quot;"))


def fill(template: Path, title: str, data, static: str = "", extra=None) -> str:
    """static: the pre-rendered markup for #root. The CSS is inlined because Quick Look
    may not load a linked stylesheet. extra: more props for the gallery (e.g. links)."""
    out = template.read_text(encoding="utf-8")
    out = out.replace("{{EXTRA}}", embed_json(extra))
    out = out.replace("{{CSS}}", (COMPONENTS_DIR / "claude-ui.css").read_text(encoding="utf-8").replace("</", "<\\/"))
    out = out.replace("{{STATIC}}", static)
    out = out.replace("{{TITLE_JSON}}", json.dumps(title, ensure_ascii=False).replace("</", "<\\/"))
    out = out.replace("{{TITLE}}", html_escape(title))
    return out.replace("{{DATA}}", embed_json(data))


def slugify(text: str, limit: int = 60) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text[:limit].rstrip("-") or "technique"


def spec_paths(root: Path) -> list[Path]:
    d = specs_dir(root)
    return sorted(p for p in d.glob("*.json") if not p.name.startswith("_")) if d.exists() else []


def load_specs(root: Path) -> list[dict]:
    return [json.loads(p.read_text(encoding="utf-8")) for p in spec_paths(root)]


def shared_redactions(root: Path) -> list[dict]:
    f = specs_dir(root) / SHARED_REDACTIONS
    return json.loads(f.read_text(encoding="utf-8")) if f.exists() else []


def redactions_for(spec: dict, root: Path) -> list[dict]:
    """The spec's own replacements plus the shared ones, longest "find" first so a long
    identifier is replaced before a shorter one inside it."""
    rules = [r for r in (spec.get("redactions") or []) + shared_redactions(root) if r.get("find")]
    seen, out = set(), []
    for r in sorted(rules, key=lambda r: -len(r["find"])):
        if r["find"] not in seen:
            seen.add(r["find"])
            out.append({"find": r["find"], "replace": r.get("replace", "")})
    return out


def forbidden_terms(spec: dict, root: Path) -> list[str]:
    """Identifiers that must not appear in the post view: every replaced "find", except rules
    kept as is (replace == find) and finds that are part of some stand-in."""
    rules = redactions_for(spec, root)
    stand_ins = [r["replace"] for r in rules]
    return [r["find"] for r in rules if r["find"] != r["replace"] and not any(r["find"] in s for s in stand_ins)]


# Keys whose values are structure, not prose; never rewritten.
STRUCTURAL = {"slug", "type", "tone", "status", "mode", "view"}


def redaction_pattern(find: str) -> re.Pattern:
    """Matches find as a whole token: "EC" replaces "EC flow" but never the EC in "SECRET"."""
    return re.compile(r"(?<!\w)" + re.escape(find) + r"(?!\w)")


def apply_redactions(node, rules: list[dict]):
    if isinstance(node, str):
        for r in rules:
            node = redaction_pattern(r["find"]).sub(lambda _m: r["replace"], node)
        return node
    if isinstance(node, list):
        return [apply_redactions(v, rules) for v in node]
    if isinstance(node, dict):
        return {k: (v if k in STRUCTURAL else apply_redactions(v, rules)) for k, v in node.items()}
    return node


# Hub: where a technique stands on its way to a post. "focused" is reached by confirming a focus.
STATUSES = ("idea", "focused", "drafting", "ready", "posted")
# Never in the post view: the hub's working notes and Claude's unconfirmed suggestions.
INTERNAL_ONLY = ("redactions", "context", "context_href", "notes", "status")


def effective_status(spec: dict) -> str:
    status = spec.get("status") or "idea"
    if status == "idea" and (spec.get("focus") or {}).get("confirmed"):
        return "focused"
    return status


def post_spec(spec: dict, root: Path) -> dict:
    """The shareable version: replacements applied; screenshot, session, the replacement list,
    the context and anything not confirmed removed. A focus goes in only once confirmed."""
    keep = {k: v for k, v in spec.items() if k not in INTERNAL_ONLY}
    focus = spec.get("focus") or {}
    keep.pop("focus", None)
    if focus.get("confirmed"):
        keep["focus"] = {k: focus[k] for k in ("line", "blocks") if k in focus}
    out = apply_redactions(keep, redactions_for(spec, root))
    src = out.get("source") or {}
    out["source"] = {"taken": src["taken"][:10]} if src.get("taken") else {}
    out["view"] = "post"
    return out
