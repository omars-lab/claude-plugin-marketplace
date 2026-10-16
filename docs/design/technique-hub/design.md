# Technique hub: a commented gallery of Claude techniques, the design to build

This is the one design to act on. It turns the technique pages that `technique-manager` makes
into a **hub**: a small local site with a gallery, one page per technique, and page comments on
everything. From that site the user decides what each future post is really about (its **true
focus**), asks Claude to fetch the **pre-context** behind a technique, and tracks each one from
idea to posted.

Most of it exists already. The page components, the two views, the privacy scan, the studio sync
and page comments are all built. This design adds a private home for the data, a hub build,
four spec fields, a skill that fetches context, and the rules that turn a comment into an edit.
Nothing here is built yet.

## Summary

- **Where it lives.** A private git repo, `~/workspace/technique-hub`, because page comments
  are saved as files in git (section 2). Its upstream is a bare repo on the user's other Mac
  (`<host>:git/technique-hub.git`), the same pattern as their other private repos. It is never
  this public marketplace repo, and its pre-push hook refuses any remote not in `hub.json`.
- **Status.** Phases 0 to 4 are built (`technique-manager:build-hub` and `research-backstory`). What differs from this design:
  - Comment anchors resolve by the block's place in the CSS path, so `anchors.json` isn't needed.
  - The share-menu intake still has to be pointed at the hub (it is unbuilt).
- **What the user sees.** `make serve` opens the hub on localhost with comments on (press C). The
  hub has a gallery with a status on each card, a page per technique with a "Post plan" panel,
  and a "Waiting on you" page. With `--phone`, the same pages take comments from the phone over
  Tailscale.
- **What a comment does.** Claude follows `development-manager:answer-page-comments`, plus a
  routing table in the hub's `CLAUDE.md` (section 5). For example, a comment on a terminal block
  saying "this is the point" sets the focus and the blocks that prove it. "Fetch the PR" runs
  the context step. "Don't show this name" adds a replacement. Claude edits the spec,
  re-renders, and replies on the page.
- **Pre-context.** A new skill, `technique-manager:research-backstory`, reads the linked session
  around the screenshot and the git history of the folder it ran in. It writes
  `context/<slug>.md` and suggests a focus and a back story. The user confirms them by comment.
- **Do first.** Claude Code deletes session files after about 30 days (`cleanupPeriodDays`),
  so phase 0 copies every linked session into the hub's archive before anything else is built.

## 1. The problem and the goal

The techniques exist as pages, and the post view is safe to share. Three things are missing
before they become posts:

1. **A focus.** A screenshot often shows three moves at once. A post needs one: the line the
   reader should leave with, and the part of the transcript that proves it.
2. **The back story.** The screenshot shows the moment, not what led to it. That lives in the
   session (the turns before) and in git (what changed after).
3. **A place to think out loud.** Remarks such as "this one is really about compaction" or "pair
   it with the hook one" have nowhere to go today.

**The goal:** open one local site, comment on any technique or any line of its transcript, and
have Claude turn each comment into a change. Then each post is ready to write from the studio.

## 2. Where it lives: a private data repo

Page comments save each thread as a file in `.page-comments/threads/` and track them in git
(`development-manager:enable-page-comments`). The technique pages live today in a Desktop
folder and in iCloud, and neither is a repo. The marketplace repo is public. So the hub gets its
own private repo, the same pattern as the instagram-manager data repo behind `build-hub`.

```
~/workspace/technique-hub/            private git repo; never a public remote
├── Makefile                          hub, serve, archive, context, sync (section 8)
├── CLAUDE.md                         the comment routing table (section 5.3)
├── hub.json                          settings: screenshots folder, studio sync, defaults
├── techniques.json                   the manifest (moved from the Techniques folder)
├── specs/
│   ├── _redactions.json              shared replacements
│   └── <slug>.json                   one spec per technique, with the new fields (section 3)
├── context/
│   └── <slug>.md                     fetched pre-context, written by research-backstory
├── notes/
│   └── <slug>.md                     free-form notes and drafts (optional, hand-written)
├── .page-comments/                   threads (tracked), config, run launcher
├── archive/                          git-ignored, never deleted by a build
│   └── sessions/<session_id>.jsonl   copies of linked sessions (phase 0)
└── .cache/                           git-ignored, rebuilt by `make hub`
    └── hub/                          the site: gallery, pages, waiting page, _lib, img
```

**What is tracked:** specs, replacements, context, notes and comment threads. These are the
user's thinking, and git gives them history.

**What is not tracked:**
- The screenshots stay in the Techniques folder, and the build copies them into `.cache/hub/img`.
- The session copies stay in `archive/`. They are large and hold whole conversations.
- The built site goes in `.cache/`.

**Root resolution.** The scripts already take `--root`. `lib.find_root` gains one more rule: a
folder with a `hub.json` is a root. Its `screenshots` setting says where the screenshot images
are. Existing users with only the Techniques folder see no change.

**Migration** (one script, `migrate_to_hub.py`):
- copies `pages/specs/*.json` and `techniques.json` into the repo;
- rewrites `source.image` to a name relative to the screenshots folder;
- leaves the Techniques folder in place;
- prints a summary.

It never deletes anything. It refuses to run if the target already has specs.

## 3. The data: four new spec fields

```json
{
  "status": "focused",
  "focus": {
    "line": "Ask whether a fix should become a rule and a hook, not just a note.",
    "blocks": [2, 7],
    "source": "comment",
    "confirmed": true
  },
  "context": {
    "file": "context/<slug>.md",
    "fetched": "2026-10-20",
    "sources": ["session-before", "session-after", "git"],
    "suggested_focus": "…",
    "suggested_backstory": "…"
  },
  "post": { "trim": false, "published": null }
}
```

| Field | Meaning | Who sets it |
|---|---|---|
| `status` | `idea` → `focused` → `drafting` → `ready` → `posted` | A build derives the first two: no confirmed focus means `idea`, and a confirmed focus means `focused`. The user sets the rest by comment |
| `focus.line` | The one line the reader should leave with | A comment, or a suggestion the user confirms |
| `focus.blocks` | Indexes of the transcript blocks that prove it | A comment on those blocks |
| `focus.confirmed` | `false` while it is only Claude's suggestion | The user, by comment ("yes" on the suggestion) |
| `context.*` | Where the pre-context is and what it suggested | `research-backstory` |
| `post.trim` | The post view shows only the focus blocks, with `…` between them | A comment ("trim the post to the focus") |
| `post.published` | `{url, date}` once it is posted | A comment, or by hand |

**The rules that keep this safe:**
- `focus.line` and `backstory` appear in the post view, so the privacy scan covers them, as it
  already covers `backstory`.
- A suggestion never reaches the post view until it is confirmed.
- `context/*.md` is never rendered into the post view, never zipped and never synced. It is
  internal by definition.

`render_page.py` validates the new fields. A bad block index or an unknown status is an error,
not a silent skip.

## 4. The hub site

`build_hub.py` (in a new skill, `technique-manager:build-hub`) builds into `.cache/hub/` with
the same `claude-ui.js` and the same pre-rendering (`prerender.js`), so pages also preview in
Quick Look.

| Page | What it shows |
|---|---|
| `index.html`: gallery | The existing `Gallery`, plus a `StatusChip` on each card and a filter by status as well as by mechanism. Each card shows the focus line, or "No focus yet" |
| `<slug>.html`: technique | The internal view (recreation beside the original screenshot, replacements, session), plus a **Post plan** panel at the top: focus line and status, a link to the post preview, the context summary with a link to `context/<slug>.md`, and the suggested focus and back story, marked "suggested" until confirmed |
| `post/<slug>.html`: post preview | The post view exactly as it will be shared: focus blocks highlighted, trimmed if `post.trim` is set |
| `waiting.html`: waiting on you | Techniques with no confirmed focus, suggestions to confirm, context not fetched yet, sessions about to expire (with date), open comment threads, and replacements still under review |

**New components** (in `claude-ui.js` with a sample each in `SAMPLES`, following the component
rule): `StatusChip`, `PostPlan`, `ContextSummary`, `Waiting`. `Page` gains a `hub` view, which
is the internal view plus `PostPlan`.

**Focus in the post view.** Blocks in `focus.blocks` get the class `cu-focus`: a thin accent bar
in the gutter, the way a terminal selection looks. With `post.trim`, the other blocks are left
out, and a dim `⋯` line stands where blocks were cut.

**Stable comment anchors.** Every element a comment can mean gets a `data-comment-id` that
survives re-renders:

| Element | `data-comment-id` |
|---|---|
| Card in the gallery | `<slug>` |
| A terminal block | `<slug>:b<index>` |
| Post plan, focus line | `<slug>:focus` |
| Post plan, suggestion | `<slug>:suggested` |
| Context summary | `<slug>:context` |
| Replacement table row | `<slug>:r:<find>` |

A page comment records the `data-comment-id` of the element clicked, not of an ancestor. A
comment on a word *inside* a block therefore has `commentId: null`, plus a CSS path and a quote.
The answer step resolves it by walking up the CSS path to the nearest element with an id (the
hub keeps a map from CSS paths to ids in `.cache/hub/anchors.json`). A small upstream change
would make this simpler: development-manager's client could fall back to
`el.closest("[data-comment-id]")`. That would be a separate development-manager release, and the
hub works without it.

## 5. Comments

### 5.1 Turning them on

Run in the hub repo:

```bash
node "<development-manager>/skills/enable-page-comments/scripts/enable.mjs" --repo . --root .cache/hub
```

The hub's `make serve` runs `.page-comments/run serve --root .cache/hub --port 8790`, so there is
one address. `--phone` adds commenting from the phone over Tailscale. Screenshots of comments
go to the configured `shotsDir` as usual.

### 5.2 How a comment becomes a change

Claude follows `development-manager:answer-page-comments` for the loop (hear, act, reply,
resolve). The hub adds only the meaning: which edit a comment asks for. After any spec edit,
Claude runs `make hub SLUG=<slug>` so the page updates before it replies.

### 5.3 The routing table (goes in the hub's `CLAUDE.md`)

| The comment is on | It says something like | Claude does |
|---|---|---|
| A terminal block (`:b<i>`) | "this is the point", "this proves it" | Adds `i` to `focus.blocks`. If no focus line exists, proposes one in the reply |
| The focus line | a new wording, "the real focus is …" | Sets `focus.line`, `confirmed: true`, `source: "comment"`, then the derived status |
| The suggestion | "yes", "use this" | Copies the suggestion into `focus.line` or `backstory`, confirmed |
| Anything | "fetch the PR / what led here / the hook file" | Runs `research-backstory` for that slug with the named source, then replies with what it found |
| Any text | "don't show this", "rename X" | Adds a replacement (per-spec, or shared if it says "everywhere"), re-scans and re-renders the post view |
| The card or the page | "drafting" / "ready" / "posted at <url>" | Sets `status` (and `post.published`) |
| The page | "trim the post" / "show it all" | Sets `post.trim` |
| The page | "pair with <other technique>" | Adds a line to `notes/<slug>.md` and to the other technique's notes |
| Anything else | a question or a thought | Answers it in a reply. If it is a note to keep, appends it to `notes/<slug>.md` |

**The rules:**
- Claude never changes the post view's wording beyond what the comment asks.
- A change that reaches the shared component library is not answered by editing it. Claude
  replies with the proposal and leaves the thread open (the component rule).
- A replacement or a newly confirmed back story runs the privacy scan before replying.
- Replies say what changed in one line, and link the post preview when it changed.

## 6. Pre-context: `technique-manager:research-backstory`

A new skill with one script for the mechanical part (`fetch_context.py`), plus Claude for the
reading and the summary.

**Sources**, in order (the default set is the first three):

| Source | How | Gives |
|---|---|---|
| `session-before` | Walk the archived (or live) JSONL back from `source.session.uuid`, up to 40 turns or the previous compaction | The problem that led to the technique |
| `session-after` | Walk forward up to 60 minutes | What came of it: the hook added, the rule kept |
| `git` | `git -C <session cwd> log --since <ts−1h> --until <ts+2h> --stat`. Also `gh pr list --search <sha>` when the remote is GitHub | The change it produced, with a link |
| `files` | `file_path` of Edit and Write tool calls in that window | The hook, skill or config it touched |
| `related` | Other specs with the same mechanism or the same touched files | What to pair it with |

`fetch_context.py --spec <slug> [--sources …]` writes bounded JSON excerpts to stdout. It never
dumps whole transcripts, and every excerpt is cut to a size limit. Claude reads those excerpts
and writes `context/<slug>.md` with five headings: What led here / What happened after /
Changes / Touched files / Related. It then sets `context.suggested_focus` and
`context.suggested_backstory` in the spec, unconfirmed, and re-renders.

**Rules:**
- The context file is internal and may hold real names.
- Suggestions are written as they would appear in the post, so the privacy scan runs on them
  before they are shown as "suggested".
- A missing session or folder is a note in the context file, not an error.

## 7. Phase 0: archive the sessions now

Every linked session is a file under `~/.claude/projects/` that Claude Code deletes after
`cleanupPeriodDays` (30 by default). The oldest techniques are close to that line.

`archive_sessions.py`:
- copies each `source.session.path` to `archive/sessions/<session_id>.jsonl`, skipping copies
  already there;
- records `source.session.archived` in the spec;
- prints which sessions it could not find.

`find_session.py` and `fetch_context.py` read the archive first. `make hub` runs the archive
step every time, so new techniques are covered from their first build. The waiting page lists
every linked session that is not archived yet, with the date it expires.

## 8. What changes, and what stays

| Piece | Change |
|---|---|
| `recreate-technique/scripts/lib.py` | `find_root` knows `hub.json`; screenshots folder setting; validation of the new fields |
| `recreate-technique/components/claude-ui.js` + css | `StatusChip`, `PostPlan`, `ContextSummary`, `Waiting`; `hub` view; `cu-focus`; trim; `data-comment-id` on blocks and panels |
| `recreate-technique/scripts/render_page.py` | Post view honors `focus` and `post.trim`; scan covers `focus.line` |
| `recreate-technique/scripts/find_session.py` | Reads the archive first |
| New: `technique-manager:build-hub` | `build_hub.py` (gallery with status, hub pages, post previews, waiting page, `anchors.json`), `migrate_to_hub.py`, `archive_sessions.py`, a template `Makefile` and `CLAUDE.md` for the hub repo |
| New: `technique-manager:research-backstory` | `fetch_context.py` plus the steps in section 6 |
| `sync-studio` | Reads specs from the hub root; also sends `focus.line` and `status` in `content/index.json` (post-safe fields only) |
| `package-gallery` | Unchanged; works from the hub root |
| `technique-manager:introduce` | Adds the hub and the two new skills |
| `development-manager` | Nothing required. Optional, in its own release: the `closest()` fallback for comment anchors |

**The hub's `Makefile`:**

```make
PORT ?= 8790
hub:      ## archive sessions, render, build the hub site
	python3 $(TM)/build-hub/scripts/archive_sessions.py --root .
	python3 $(TM)/recreate-technique/scripts/render_page.py --root . --all
	python3 $(TM)/build-hub/scripts/build_hub.py --root . $(if $(SLUG),--only $(SLUG))
serve: hub ## the hub with page comments, one address
	.page-comments/run serve --root .cache/hub --port $(PORT)
context:  ## pre-context for one technique: make context SLUG=…
	python3 $(TM)/research-backstory/scripts/fetch_context.py --root . --spec $(SLUG)
sync:     ## send the post-safe content to the studio
	python3 $(TM)/sync-studio/scripts/sync_studio.py --root .
```

`TM` is the technique-manager skills folder. The template writes it from the plugin's install
path, the way the page-comments `run` launcher finds its plugin.

## 9. End to end

```
share or suggest-techniques ─▶ recreate-technique ─▶ make hub (archive, render, site)
                                                         │
                     comments on the hub (Mac or phone) ◀┘
                         │  focus · trim · replacements · status · "fetch context"
                         ▼
          answer-page-comments + routing table ─▶ spec edits ─▶ make hub SLUG=…
                         │
          research-backstory ─▶ context/<slug>.md + suggestions to confirm
                         │
          status ready ─▶ package-gallery (zip) · sync-studio ─▶ write the post on the studio
```

The share-menu intake (`docs/design/technique-intake/design.md`) writes new specs into the hub
root with `status: idea`. Its "review later" step becomes "comment on the hub".

## 10. Phased plan

Each phase ends with a check that proves it.

| Phase | Builds | Done when |
|---|---|---|
| 0 | `archive_sessions.py` | Every linked session has a copy in `archive/sessions/`; a second run copies nothing |
| 1 | Hub repo, `migrate_to_hub.py`, `build-hub` with gallery and hub pages, `make serve` with comments | `make serve` shows the gallery and every technique page; a test comment on a block is heard by the session watcher with `commentId` `<slug>:b<i>` |
| 2 | Spec fields, `PostPlan`, `StatusChip`, focus and trim in the post view, the routing table | Commenting "this is the point" on a block sets `focus.blocks`, and the post preview highlights it after the reply; validate-pages passes on all views |
| 3 | `research-backstory` and `fetch_context.py` | `make context SLUG=…` writes a context file with the five headings; the suggestion shows as "suggested" and passes the privacy scan |
| 4 | Waiting page, `anchors.json` resolution, studio fields, intake writing into the hub | The waiting page lists exactly what is open; a comment on a word inside a block still resolves to that block |

Tests follow the instagram-manager pattern: offline tests on an invented hub (`test_build_hub.py`,
`test_fetch_context.py`) with made-up specs and a made-up session file. They never use real data,
because this repo is public.

## 11. Risks and open questions

**Risks:**
- **The hub repo holds real names.** Threads, context and specs are internal. Mitigation: the
  template `.gitignore`, a README line, and a pre-push hook in the template that refuses any
  remote not on an allow list.
- **Comments on re-rendered pages.** A thread anchors to an element's hash, and a re-render can
  change it. The stable `data-comment-id`s keep threads attached. A thread whose block index
  moved (a spec edit that inserts a block) is re-pointed by the answer step and noted in its reply.
- **Session size.** Long sessions are tens of MB. The archive is git-ignored, and
  `fetch_context.py` reads with bounded excerpts.
- **Sessions from another Mac.** `find_session.py` searches only this Mac's `~/.claude/projects`.
  A technique captured on the studio needs `--remote <host>` there (an SSH `find` plus `scp`
  into the archive). This is phase 4 or later, if wanted.

**Open questions:**
1. *Decided:* the working copy lives on this Mac, where Claude answers comments. The upstream is
   a bare repo on the studio. Still open: should `archive/` (git-ignored, hundreds of MB) also be
   copied to the studio as a backup, with rsync next to the bare repo?
2. Is `focus` a line plus blocks (recommended), or a line only?
3. Which context sources are on by default? This design picks session-before, session-after and git.
4. Should `drafting` connect to a draft file? For example, `notes/<slug>.md` could hold the
   draft, with the studio reading it through the sync.
5. Should the optional `closest()` change in development-manager be made, so the CSS-path
   fallback can go?
