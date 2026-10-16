---
name: recreate-technique
description: Turn a technique screenshot into a Claude-style HTML page built only from the shared React component library (claude-ui.js) — read the screenshot with Vision, write a structured spec, scan it for identifying details, and render it with a script so every page looks and behaves the same
---

# Recreate a Technique as a Page

You turn a screenshot of Claude being used well into an HTML page that explains the technique and recreates the session in a Claude Code–style terminal. **Every page is built from the same React components.** Your job is to write the *spec* (data). The components do the rendering.

**Before this:** `/screenshot-manager:suggest-techniques` fills the Techniques folder and its `techniques.json`.
**After this:** `/technique-manager:package-gallery` builds the gallery and the zip.

## Paths

```bash
# The skill's own folder: use the "Base directory for this skill" line shown when the skill loads.
# Don't search ~/.claude/plugins/cache: a plugin installed from a local marketplace loads from its repo folder.
RT="<base directory of this skill>"
TECH="$HOME/Desktop/📸 Screenshots of Techniques"
PAGES="$TECH/pages"          # specs/, internal/, post/
mkdir -p "$PAGES/specs"
```

Pages live next to the screenshots, **never in this repo**. The marketplace is public.

## Two views of every spec

| View | Folder | Shows | For |
|---|---|---|---|
| **Internal** | `$PAGES/internal/` | The faithful transcription, the original screenshot beside it, every replacement the post makes, the source session, and a credit line ("Recreated from a real Claude Code session on <date>…" plus the session JSONL path) | Checking fidelity and redaction. Never shared |
| **Post** | `$PAGES/post/` | Replacements applied. No screenshot, no session, no credit line | Sharing, or publishing as a blog post. The only view that goes in the zip |

You write one spec. The real values stay in it, and the replacements live in `redactions` lists, so the transcription is never edited by hand to hide something.

## What makes it feel like a session

The page should read as the terminal it came from, not as a document about it. These are rules for the components; a page never overrides them:

- **The terminal is always dark** (Claude Code's dark terminal colors), whatever the page theme. Only the page around it follows light and dark mode.
- **Dense, like the terminal:** monospace 13px with line-height about 1.45, one blank line between messages, and none inside one. The post view gives the terminal about 1180px so lines wrap where the terminal wrapped them. The reading text stays narrower.
- **Transcribe, don't add:** don't invent headings (a "Tasks" title, for example), task ids or numbering the screenshot doesn't show. A task list printed under a spinner line has no `title`; it hangs under the spinner with `⎿`.
- **Text that is already there:** a `spinner` verb or task `summary` that already ends or starts with `…` isn't doubled. `*text*` renders as italics, the way Claude Code shows it, so keep the asterisks in the spec.

Check the feel by putting a rendered page beside the original. If Chromium can't launch here, use headless Chrome on another Mac you can SSH to (`"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --screenshot=… --window-size=1300,2000 file://…`).

## The component rule

`$RT/components/claude-ui.js` is the only place markup lives. A spec is a list of **blocks**, and each block type maps to one component:

| Block `type` | Component | Fields |
|---|---|---|
| `user_prompt` | `<UserPrompt>` | `text`, `glyph` (`"!"` for a command the user ran in their own shell) |
| `assistant_text` | `<AssistantText>` | `text` (supports `**bold**`, `` `code` ``, `- ` bullets, blank lines) |
| `tool_call` | `<ToolCall>` | `name`, `args` |
| `tool_result` | `<ToolResult>` | `text` |
| `spinner` | `<Spinner>` | `verb`, `meta` |
| `note` | `<Note>` | `text` (e.g. "Baked for 2m · done 9:54 AM") |
| `recap` | `<Recap>` | `text` |
| `task_list` | `<TaskList>` | `title`, `mark` (`""` when the title has no ✻), `tasks: [{id, title, status, note}]`, `summary` |
| `prompt_input` | `<PromptInput>` | `text` |
| `statusline` | `<StatusLine>` | `segments: [{text, tone, pct}]`, `right` |
| `footer` | `<Footer>` | `mode` (`auto`/`plan`/`accept-edits`), `text` |
| `question` | `<Question>` | `header`, `question`, `options: [{label, description, recommended}]`, `selected` (1-based), `hint`; or `question` + `answer` for the answered form |
| `permission_prompt` | `<PermissionPrompt>` | `title`, `from`, `description`, `command`, `hook: {label, text}`, `question`, `choices`, `selected`, `cut` (a permission or hook confirmation box) |
| `divider` | `<Divider>` | — |

`status` is one of `pending`, `in_progress`, `completed`, `blocked`. `tone` is one of `path`, `branch`, `model`, `meter`, `cost`, `dim`.

**If the screenshot shows something no component covers** (a permission dialog, a diff, a plan-mode box, a subagent panel), do not work around it:
1. Add a component and a `BLOCKS` entry to `claude-ui.js`, with styles in `claude-ui.css` that use only the existing tokens.
2. Add a sample of it to `SAMPLES` so it appears in `components/catalog.html`.
3. Then use the new type in the spec.

Edit the plugin source in the marketplace repo (`plugins/technique-manager/skills/recreate-technique/components/`), not the cache. Bump the plugin version and run `make update`, so every later page gets the component. `render_page.py` refuses a spec with an unknown block type, which keeps one-off markup out.

## Tasks

Create with `TaskCreate`: one task per screenshot (`Recreate <title>`), plus `Find sessions`, `Redactions` and `Render pages`.

## Step 1: Pick screenshots

- With a path argument, use that file.
- With `--all-new` or no argument, read `$TECH/techniques.json` and pick the entries that have no `$PAGES/specs/<slug>.json` yet. If there is no manifest, list the images in `$TECH` and use `AskUserQuestion` to pick.

A group of screenshots taken in a row (the same `group` in the manifest) becomes **one page**. Its blocks follow the shots in order.

## Step 2: Write the spec

Read the screenshot with the Read tool. Write `$PAGES/specs/<slug>.json`:

```json
{
  "slug": "hook-runs-linter-after-edit",
  "technique": {
    "title": "A hook that runs the linter after every edit",
    "mechanism": "hooks",
    "why": "Lint errors get fixed in the same turn instead of piling up for review.",
    "when": "Any repo with a fast linter and a habit of style drift.",
    "how": ["Ask Claude for a `PostToolUse` hook on Edit/Write.", "Point it at the lint command for one file.", "Watch the next edit fix its own warnings."]
  },
  "source": { "file": "Screenshot 2026-01-01 at 9.00.00 AM.png", "taken": "2026-01-01 09:00" },
  "terminal_title": "claude — example-app",
  "blocks": [
    { "type": "user_prompt", "text": "can we lint after every edit?" },
    { "type": "spinner", "verb": "Wiring", "meta": "12s · thinking" },
    { "type": "assistant_text", "text": "Done. **What changed:**\n- A `PostToolUse` hook in `.claude/settings.json`" },
    { "type": "recap", "text": "I added a lint hook. Next, decide whether it also runs on commit." },
    { "type": "statusline", "segments": [{ "text": "workspace/example-app", "tone": "path" }, { "text": "42%", "tone": "meter", "pct": 42 }] }
  ]
}
```

Guidance:
- **Transcribe faithfully, then trim.** Keep the lines that show the technique. Shorten long assistant output with a closing `…` line rather than retyping a wall of text.
- **The header carries the teaching.** `why` is one sentence. `how` is 2–4 steps someone could follow tomorrow. `mechanism` is the same tag the manifest uses.
- `slug` is short kebab-case from the title, unique within `specs/`.
- `backstory` (optional): a few short paragraphs on how the moment came up, for the post. Write it from the source session (Step 2b), not from guesses.
- **Many screenshots:** hand them to subagents, 3 or 4 each, with this spec format and the block table. Ask each one to report every identifier it transcribed and any UI no block covers. The identifier list feeds Step 3, and the uncovered UI tells you which component to add.

## Step 2b: Find the source session

```bash
python3 "$RT/scripts/find_session.py" --all --write
```

It matches each spec's typed prompts against `~/.claude/projects/*/*.jsonl` near the time the screenshot was taken, and saves the match as `source.session`. When the screenshot shows no typed prompt, it falls back to Claude's own text, such as the recap line. The internal view links the transcript. Open it to write a `backstory`, or to check a line the screenshot cut off.

- It matches by word overlap, because specs fix the user's typos. A match is saved only with a score of at least 0.5 and within 30 minutes of the screenshot.
- **Claude Code deletes sessions older than `cleanupPeriodDays` (30 by default).** For an older screenshot it says so and saves nothing. Run this step soon after taking screenshots.

## Step 3: Redactions

The post view must not identify anyone. Replacements are `{"find", "replace"}` rules, matched as whole tokens (so `EC` never touches `SECRET`):
- `$PAGES/specs/_redactions.json` holds names that recur across specs: people, the employer, products, projects, repos, paths.
- A spec's own `redactions` list holds one-off rules.
- A rule whose `replace` equals its `find` means "reviewed, fine to publish".

```bash
python3 "$RT/scripts/scan_privacy.py" --all --post    # what the post view would still show
```

1. Ask once with `AskUserQuestion` how to treat identifiers: **replace all (Recommended)**, replace only scanner hits, or keep everything (private pages only).
2. Build the rules from the scanner hits **and** the identifiers the subagents listed. The scanner can't recognize names of people, companies, products or internal tools; that list is the only way to catch them.
3. Choose stand-ins the scanner won't flag again: `$XX.XX`, `PR #N`, `feature/pack-trim`, `example-app`, `Alex`.
4. Re-run the scan until it is empty. Then grep the post text for each name on the subagents' lists.

## Step 4: Render

```bash
python3 "$RT/scripts/render_page.py" --spec "$PAGES/specs/<slug>.json"   # or --all
```

The script syncs the component library into each view's `_lib/`. It writes `internal/<slug>.html`, with the screenshot copied to `internal/img/`, and `post/<slug>.html`. **It refuses to write the post page while the scan still finds something**, and deletes any stale one.

**Pages work without JavaScript.** macOS Quick Look, Finder and iCloud previews (and many blog importers and feed readers) don't run scripts, so a page React draws in the browser would show blank there. `scripts/prerender.js` renders each page with the same `claude-ui.js` in Node at build time. It uses the vendored `react-dom-server`, with no npm packages. The markup goes into `#root`, and the CSS is inlined because previews may not load a linked stylesheet. In a browser, `ClaudeUI.mount` hydrates that markup instead of redrawing it, so the props in the template and the props given to `prerender.js` must match. Without Node, the pages are JavaScript-only, and `render_page.py` warns about it. Exit code 1 lists the problems (unknown block type, missing title, screenshot not found, identifiers left in the post). Fix the spec, the redactions or the components, then run it again.

## Step 5: Check

Open the internal page (`open "$PAGES/internal/<slug>.html"`). It puts the recreation and the screenshot side by side, with the replacement table below. Check:
- the order of the blocks, glyphs (`›` `●` `⎿` `✻` `※`), task states, and that statusline segments wrap on a narrow window
- that each replacement reads naturally in the post. Then open `post/<slug>.html` to read it as a reader would
- both light and dark mode

Then run `/technique-manager:validate-pages`.

## Output

```
Recreated N techniques → 📸 Screenshots of Techniques/pages/{internal,post}/
  hooks      hook-runs-linter-after-edit.html        session ✓
  prompting  one-line-principle-reframes-plan.html   session — (older than 30 days)
Redactions: R rules (S shared); post scan clean
New components added: <none | names>
Next: /technique-manager:package-gallery
```
