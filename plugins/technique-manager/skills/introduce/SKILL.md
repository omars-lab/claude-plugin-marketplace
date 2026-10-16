---
name: introduce
description: Introduce the technique-manager plugin — turning screenshots of Claude techniques into Claude-style HTML pages built from one shared React component library, then packaging them into a gallery and a zip and syncing the shareable content to another Mac
---

# Introduce Technique Manager

You are the Technique Manager plugin. When invoked, explain what you do and route the user to the right skill.

## What This Plugin Does

Screenshots of Claude being used well (a hook, a recap, a task list, a prompting move) are easy to take and hard to share or learn from. Technique Manager turns each one into a page that explains the technique and recreates the session in a Claude Code–style terminal. It then combines the pages into a gallery and a zip that opens offline.

Every page, the gallery and the catalog render from **one React component library** (`claude-ui.js`, React 18 + htm, no build step). A page is data (a spec), never its own markup, so improving a component improves every page. Pages are also pre-rendered at build time with the same components, so they show in macOS Quick Look and Finder previews, where no JavaScript runs.

## The Flow

```
/screenshot-manager:suggest-techniques   Desktop → 📸 Screenshots of Techniques (+ techniques.json)
          ↓
/technique-manager:recreate-technique    screenshot → spec → page (shared components)
          ↓
/technique-manager:validate-pages        Playwright checks + side-by-side fidelity review
          ↓
/technique-manager:package-gallery       post pages → index.html gallery → techniques-YYYYMMDD.zip
          ↓
/technique-manager:sync-studio           post view + redacted content → another Mac over SSH (rsync)

/technique-manager:build-hub             private hub repo: gallery with status, page comments on every
                                         block, sessions archived; the place to pick each post's focus
/technique-manager:manage-hub            day to day in the hub: what's waiting, answer comments, fetch
                                         back stories, serve, sync, the background comment responder
```

## How to Introduce Yourself

### Step 1: Welcome

```
Technique Manager: 7 skills that turn Claude technique screenshots into pages.

- recreate-technique: one screenshot (or a group of them) becomes a Claude-style HTML page
- validate-pages: a headless browser checks every page renders the right content
- package-gallery: all pages become a gallery and an offline zip
- sync-studio: the shareable content goes to a dedicated folder on another Mac
Picking screenshots happens first, in /screenshot-manager:suggest-techniques.
```

### Step 2: Ask What They Want

Use `AskUserQuestion`:
- Pick technique screenshots from my Desktop → `/screenshot-manager:suggest-techniques`
- Turn screenshots into pages → `/technique-manager:recreate-technique`
- Check the pages render correctly → `/technique-manager:validate-pages`
- Build the gallery and zip → `/technique-manager:package-gallery`
- Send new techniques to the studio Mac → `/technique-manager:sync-studio`
- Show me the component catalog → open `skills/recreate-technique/components/catalog.html`

## Skills

### `recreate-technique`
**Invocation:** `/technique-manager:recreate-technique [<screenshot> | --all-new]`

Reads the screenshot with Vision and writes a spec: the technique header (title, mechanism, why, when, how), an optional back story, and transcript blocks. A UI element no component covers gets a new component in the library first.

- `find_session.py` links the Claude Code session the screenshot came from (its JSONL transcript), so a post can be expanded with the back story later. Sessions older than 30 days are usually deleted by Claude Code.
- Each spec renders into **two views**:
  - **internal**: the faithful transcription beside the original screenshot, with the replacement table and the session link. For checking only.
  - **post**: identifiers replaced, no screenshot. Shareable and blog-ready.
- Replacements are whole-token rules in `specs/_redactions.json` (shared) or the spec's `redactions` list (one-off). `render_page.py` won't write a post page while the privacy scan still finds something.

### `validate-pages`
**Invocation:** `/technique-manager:validate-pages [--only <slug>]`

Loads every page in both views, the galleries and the catalog in headless Chromium (Playwright), in light and dark mode at desktop and phone width. It fails on console errors, an unmounted React root, missing components, block counts that differ from the spec, broken images or sideways scrolling, and on any replaced identifier showing in a post page. It saves screenshots so Claude can compare each page with its original and score how faithful it is.

### `package-gallery`
**Invocation:** `/technique-manager:package-gallery`

Re-renders all pages and builds a gallery `index.html` for each view (cards plus mechanism filters, from the same components). It runs the validate-pages checks and the post-view privacy check, then zips **only the post view**, checked for broken links.

### `sync-studio`
**Invocation:** `/technique-manager:sync-studio [--dry-run | --prune]`

Stages the post view plus each technique's redacted JSON and an `index.json`, re-runs the privacy scan, and rsyncs them over SSH into one dedicated folder on another Mac. The host and folder are kept in `~/.config/technique-manager/studio.json`, outside the repo. It never sends the internal view, screenshots or unredacted specs.

### `build-hub`
**Invocation:** `/technique-manager:build-hub`

Sets up the **technique hub**: a private git repo, with its upstream on the user's own machine, that holds the specs, replacements, notes and page-comment threads. It copies every linked Claude Code session into an archive before Claude Code deletes it, and builds a local site: a gallery with each technique's status, and pages with a comment anchor on every terminal block. `make serve` serves it with page comments (development-manager), and the hub's `CLAUDE.md` says which edit each comment asks for (set the focus, fetch context, add a replacement, mark it posted). Once a hub exists, every other skill here uses it as its root.

### `manage-hub`
**Invocation:** `/technique-manager:manage-hub` (or "what's waiting in the hub", "answer my comments")

The entry point once a hub exists. It routes:
- "what's waiting" to the waiting page's counts;
- comments to `development-manager:answer-page-comments` and the hub's routing table;
- back stories to `research-backstory`;
- rebuild, serve, backup and sync to the hub's `make` targets;
- the background responder to `make responder-on`, `responder-off` and `responder-status`. The responder answers comments while no session is open (macOS, launchd).

### `research-backstory`
**Invocation:** `/technique-manager:research-backstory <slug>` (or a hub comment such as "fetch what led here")

Fetches the pre-context behind one technique and writes it to `context/<slug>.md`:
- the session turns that led up to the screenshot, and what came of them;
- the files those turns touched;
- the user's own commits around that time;
- related techniques.

It then suggests a focus and a back story, which the user confirms by replying "yes" on the page. Any suggestion the privacy scan flags is refused, because it will show in the post once confirmed.

## Where Things Live

| What | Where |
|---|---|
| Components, CSS, vendored React/htm, catalog | `skills/recreate-technique/components/` (in this plugin) |
| Screenshots + `techniques.json` | `~/Desktop/📸 Screenshots of Techniques/` |
| Specs and `_redactions.json` | `~/Desktop/📸 Screenshots of Techniques/pages/specs/` |
| Internal view (+ `img/`) | `~/Desktop/📸 Screenshots of Techniques/pages/internal/` |
| Post view (shareable) | `~/Desktop/📸 Screenshots of Techniques/pages/post/` |
| Zip | `~/Desktop/📸 Screenshots of Techniques/techniques-YYYYMMDD.zip` |
| Studio sync settings | `~/.config/technique-manager/studio.json` |
| Hub (once set up): specs, notes, threads | `~/workspace/technique-hub/` (private repo); site in `.cache/hub/`, sessions in `archive/` |
| Which root the scripts use | `~/.config/technique-manager/settings.json` (`root`); without it, the Techniques folder |

Pages never go into the marketplace repo, which is public.
