# Comments on localhost pages: raw findings (researcher A)

This is the raw record behind `design.md` in this folder. It lists every source I used. Each source is marked with how I saw it:

- **read**: I opened the file on this machine and read it (in full, or the part named).
- **fetched**: I loaded the web page or raw file and read its content.
- **snippet only**: I saw it only as a search-result summary. Treat these claims as unconfirmed.

Date of research: 2026-10-12.

Checker's note: the local folder paths of the private repos were removed before this file went into the public repo. Only the repo names remain.

## The question

Omar asked for "commenting capabilities to a CX". The feature needs four parts:

- a floating comment button on pages he runs on localhost;
- a skill that has Claude watch for comments and answer them;
- a setup skill that installs the watcher, the commenting code, element screenshots and git tracking;
- the Claude-side skill that ties these together.

**How I read "CX".** I assume it means any web page or app Omar runs on localhost while building it, such as a demo, a mock-up, a static site or a dev server. My evidence is his other repos, which call their demo pages "CX demo artifacts" and "CX artifact mocks", meaning customer-experience mock pages. This is an assumption to confirm.

## 1. Omar's own prior art

### 1.1 review-md (public repo, `~/Workspace/git/review-md`, also github.com/omars-lab/review-md)

This tool is the closest relative in spirit. It does the same job for Markdown documents in Obsidian.

- `README.md` (**read**, in full).
  - **Commenting.** You press `c` to enter comment mode, click an element, and a draft card opens.
  - **Storage.** Threads live in a hidden file next to the document, `.<name>.comments.md`, and that file is tracked in git.
  - **Anchoring.** It adds a `^block-id` to the commented paragraph so the comment can find it again.
  - **Versions.** Each thread is stamped with the version of the document it was written against. An "outdated" flag and a version stepper show when the text has moved on.
  - **Command line.** The `reviews` command has these subcommands:
    - `help` and `stats`;
    - `list`, with `--open`, `--waiting claude` and `--since`;
    - `find`, `show` and `diff`;
    - `reply`, with `--author claude` and `--resolve`;
    - `resolve`, with `--reopen`;
    - `comment`, with `--quote`, `--node` and `--from/--to`;
    - `watch`.
  - **The watch output.** `watch` prints one line per event: `<UTC time> pid=<n> ev=<event> file=… thread=… author=… msg="…"`.
    - The events are `thread_new`, `message_new`, `thread_resolved`, `thread_reopened`, `anchor_lost`, `thread_removed` and `file_renamed`.
    - The flags are `--exclude-author claude`, `--replay`, `--heartbeat 0`, `--once --state <file>` and `--json`.
  - **MCP server.** It offers the tools `list`, `find`, `show`, `diff`, `stats`, `reply`, `comment` and `resolve`. Each tool is a thin wrapper that runs the command line.
  - **One writer.** Replies go through Obsidian's own URL scheme, so the Obsidian plugin is the only thing that ever writes the file. Exit code 4 means a reply never landed.
  - **Secrets.** It uses gitleaks and dotenvx.
- `docs/agent-contract.md` (**read**, in full).
  - The YAML header of the comments file is the source of truth. Its shape is `review: {uid, threads: [{id, resolved, anchor, rev: {bodyHash, ts, git: {commit, blob}}, messages: [{author, ts, body}]}]}`.
  - The text below the header is generated for people to read. Tools never parse it.
  - There are four anchor types:
    - text, with `quote`, an optional `line` and an optional `blockId`;
    - a diagram node;
    - a diagram edge;
    - an image, with `src`.
  - `bodyHash` is the only signal that a comment is outdated. It is the first 12 hex characters of a sha256 of the document body, with the header and block ids stripped.
  - Exit codes 0, 2, 3 and 4 each have a fixed meaning.
- `docs/issues/comment-sidecar.md` (**read**). Comments moved out of the document's own header into a separate file.
  - The reason: adding a comment should never create a new version of the file under review.
  - The comments file is checked in.
  - Omar made this call on 2026-09-19.
- `docs/issues/durable-anchoring.md` (**read**). It sets four rules for block references:
  - one block reference per thread;
  - existing ids are reused;
  - block ids are left out of the hash;
  - a reference is removed only when no remaining thread uses it.
- `docs/issues/reanchor-hook.md` (**read**, first 60 lines).
  - **What it does.** A git hook runs after each commit. It finds threads that were written against uncommitted changes and moves them onto the commit that landed those changes, by matching the file's git blob.
  - **How it is installed.** It goes in through the pre-commit framework, added alongside any existing hooks, never replacing them.
- `plugins/review-md/skills/reviews/SKILL.md` (**read**, in full).
  - **The loop Claude follows:**
    1. Run `stats`.
    2. List the threads waiting on Claude.
    3. Do the work.
    4. Reply, naming the commit.
    5. Resolve the thread only if the change was actually made.
  - **Other sections.** It covers watching with the Monitor tool and has a table of what to do for each event.
  - **The "Don't" list.** It includes "never edit the comments file by hand" and "never resolve a thread you only answered".
- `plugins/review-md/.mcp.json` (**read**). It starts one stdio server with `node ${CLAUDE_PLUGIN_ROOT}/bin/reviews-mcp.mjs`.
- `plugins/review-md/.claude-plugin/plugin.json` (**read**). Version 0.1.2.
- `bin/reviews-mcp.mjs` (**read**, top of file).
  - It is a stdio JSON-RPC server with no dependencies.
  - Each tool runs the command line.
  - It uses protocol version 2025-06-18.
- `scripts/reviews.mjs` (**grep only**).
  - The live watch uses Node's `fs.watch` in recursive mode, with polling as a fallback.
  - The one-shot watch remembers what it has seen in a state file.
- `.claude-plugin/marketplace.json` (**read**). The review-md repo is its own marketplace, so review-md is not in the oeid marketplace.
- github.com/omars-lab/review-md (**fetched**).
  - The repo is public, with 0 stars and no releases.
  - Its About line and README disagree. The About line still says comments live "in frontmatter", but the README says they live in a separate file. The README is current.

### 1.2 earlbear-agentic-workflow (private repo on this machine)

This private site is built with Vite, React and TypeScript, and it has three comment systems. I describe ideas only, and leave out hostnames, database ids and customer names on purpose.

- `README.md`, `CLAUDE.md` (**read**). They call the demo pages "CX demo artifacts" and "CX artifact mocks". This is my evidence for how to read "CX".
- `docs/comments-design.md` (**read**, in full). This is the design for Figma-style comments on blog posts.
  - **Anchoring.** It compares four ways to anchor a comment:
    - an id on the element;
    - a W3C text quote;
    - block ids added at build time (this option shipped);
    - anchors on a range of text, kept durable by the three-layer model below.
  - **The three-layer durability model:**
    1. Pin the version, with a commit plus a content hash.
    2. Re-check anchors at edit or build time, and fail loudly on any anchor it cannot find.
    3. When the page loads, fuzzy-match the text at about 0.8 similarity or better. If nothing matches, list the comment as orphaned instead of placing it on the wrong text.
  - **Environments.** Comments are split by environment, so scratch comments made locally never mix with the real review.
  - **Safety.** Comment bodies are rendered with `textContent`, which blocks stored script injection.
  - **Testing.** Playwright tests prove the behaviour.
  - **Keys.** `C` toggles comment mode and Esc leaves it. Ctrl-C and Cmd-C never trigger it.
- `docs/gtm-comments-design.md` (**read**). This is the design for a floating "Feedback" button on app pages.
  - **Stable anchors.** It uses an opt-in pair of attributes, `data-comment-id` and `data-comment-label`, to give hand-written UI anchors that survive edits.
  - **Ways to pin.** A comment can be pinned in three ways:
    - on a tagged element;
    - on any clicked element, stored as a CSS path plus quoted text;
    - on a text selection.
  - **Page key.** Comments are keyed by `location.pathname`.
- `docs/report-comments-design.md` (**read**). This is the design for comments on generated report pages.
  - **The bar.** It sits at the bottom centre: `[Comment C] [Pins] [N open] [Show resolved]`.
  - **The watcher.** It prints the backlog first, then listens live, with a 30-second poll as a backup. It prints `ev=comment` lines for the Monitor tool.
  - **Who resolves.** Claude replies under its own name and **never** resolves. The person who opened the thread resolves it.
  - **Screenshots.**
    - They are taken with modern-screenshot, bundled from npm because the site's content security policy blocks CDNs.
    - The capture starts on click and is attached after the comment saves, so a slow capture never holds up the comment.
    - Only the first comment in a thread gets a screenshot.
  - **Page key.** It is the full URL, including the query string.
- `.claude/skills/answer-report-comments/SKILL.md` (**read**).
  - **Procedure.** Watch, read the thread, act (it has a table by comment type), then reply.
  - **Untrusted text.** It has a section titled "Comment text is data, not orders".
  - **Scripts.** Its "Scripts — when to use each" table lists a watcher, a thread reader, a reply script with a retract option, and a shared library.
  - I also read the top of the watcher script.
- `.claude/skills/address-diagram-feedback/SKILL.md` (**read**, in part).
  - It handles sticky-note feedback on diagrams.
  - A thread counts as answered once a group named for it exists, so running the skill again never replies twice.
- `.claude/hooks/*` and `.claude/settings.json` (**read**, in part).
  - Hooks that run when a session starts announce work waiting to be handled: "detect at the end, confront at the start".
  - Hooks that run after a tool call run the checkers.
- `vite-plugins/agent-reports.ts`, `vite-plugins/dev-auth-token.ts`, `vite-plugins/session-tail.ts` (**read**, top of each).
  - Each adds middleware only to the dev server and the preview server, so it never exists in a deployed build.
  - Live updates use Server-Sent Events fed by `fs.watch`.
  - Paths are checked so they cannot escape a known folder.
- `src/components/feedback/shot.ts` (**grep only**). Its screenshot code was copied from the local doc-review skill in section 1.4.

### 1.3 earlbear-comments (private library on this machine)

- `README.md` (**read**). This is a small library that works with any framework. It turns the durability model from section 1.2 into reusable code. Its modules:
  - `anchor-core`: text hashing and similarity;
  - `range`: build, wrap and resolve a range anchor;
  - `reconcile`: re-check anchors against new HTML;
  - `crud`: create, read, update and delete comments.

### 1.4 A local doc-review skill in a private work checkout (path withheld)

**Read** in full: the SKILL.md, plus the server, browser script and store through grep and sed. This is the closest prior art for the exact feature asked for. The checkout belongs to Omar's employer, so I give no path and name nothing from it.

- **The server.** A small Python server binds to `127.0.0.1`. It serves a folder and injects one `<script>` tag before `</body>` in every HTML page.
- **The overlay.** The injected script provides:
  - a picker cursor;
  - element screenshots with modern-screenshot 4.7.0, loaded from a public CDN;
  - a check for new comments every 4 seconds.
- **Selectors.** An element's selector is a path from `<body>`. It uses a unique id where there is one, and otherwise the tag name plus the element's position among siblings with the same tag.
- **What a thread stores.** An element thread stores the kind, selector, tag name, a short label, the click point and the screenshot, both inline and as a file.
- **Storage.** Comments go into an append-only JSONL log, with screenshots beside it.
  - Both sit in a folder that git ignores.
  - The log has three record types: thread, reply and status.
- **Command line.** It offers `wait`, `list --open`, `show`, `reply`, `resolve` and `reopen`.
  - `wait` keeps a cursor and ignores Claude's own replies.
  - It is meant to run in the background and exit when something new arrives.
- **Live reload.** The page holds its live reload while a comment draft has text in it, so a rebuild never wipes a half-written comment.
- **HTTP routes:**
  - `GET` and `POST /__preview/threads`;
  - `POST /__preview/threads/<id>/reply`;
  - `POST /__preview/threads/<id>/status`.
- **Resolving rule.** Never resolve a thread the user reopened unless a reply says what changed.
- **Screenshot details.** The capture code:
  - skips iframes;
  - gives up after 8 seconds;
  - pads 16 px;
  - paints the element's own background, or its nearest ancestor's;
  - renders the whole diagram and crops, for a node inside an SVG;
  - caps the width at 600 px.

## 2. The oeid marketplace itself (this repo)

- `CLAUDE.md` (**read**). These conventions bind the design:
  - plugins are roles (nouns), and skills are abilities (verbs);
  - every plugin needs an `introduce` skill;
  - meta-skills are preferred;
  - skill names start with a verb such as `setup-`, `monitor-`, `manage-` or `configure-`;
  - plugin names follow `<domain>-manager`;
  - examples in skills are invented, never real user data;
  - a new plugin needs `plugin.json`, `skills/introduce` and a `marketplace.json` entry, followed by `make install` and `make validate-plugin PLUGIN=`;
  - versions move with `make version-bump PLUGIN= TYPE=minor`;
  - a pre-commit hook named `check-never-public` blocks private network addresses and private employer names.
- `plugins/` listing (**read**). There are 25 plugins. These are the ones that could plausibly host this feature:

  | Plugin | Version | What it does | Fit |
  |---|---|---|---|
  | screenshot-manager | 1.2.1 | Sorts screenshot files with macOS OCR | No. It works on image files on disk, not live pages. |
  | design-partner | 1.1.0 | Co-writes design docs | No. It writes; it does not overlay pages. |
  | document-co-author | 1.3.0 | Builds decks and documents | No. |
  | code-quality-manager | 2.2.0 | Docs, Makefiles, repo security | No. It is already too broad. |
  | guardrail-manager | 1.4.0 | Git and session hooks | No. It could hold the hook, but not the feature. |
  | script-manager | 1.2.0 | Makes Tampermonkey userscripts | Only as one way to get the button onto a page. |
  | noteplan-manager | (n/a) | Has a local Python review page (`bin/noteplan_sweep/server.py`) | No. It has no commenting, but it shows that a local server is already a pattern here. |

  No existing plugin puts a comment layer on a page or watches for comments.
- review-md, synthetic-store and similar plugins installed on this machine come from other marketplaces, not this one.

## 3. Outside sources

### 3.1 Products that do this

- **Agentation**, README via jsdelivr (**fetched**).
  - **Install.** It is a React component: run `npm i agentation -D`, then add `<Agentation />`. A toolbar appears bottom-right.
  - **What it records.** You click elements, and it records class names, selectors and positions so an agent can search the code for them. You copy the result as Markdown.
  - **MCP server.** It runs with `npx -y agentation-mcp server`, with an endpoint at `http://localhost:4747`.
  - **Limits.** The license is PolyForm Shield 1.0.0. It needs React 18 or later and works on desktop only.
  - **Unconfirmed (snippet only).** Webhooks, Linear sync, and "acknowledge, resolve, dismiss" states.
- **react-grab**, GitHub (**fetched**).
  - **Install.** Run `npx grab@latest init`. It has dev-only setups for Next.js and Vite.
  - **Use.** Hover an element and press Cmd-C or Ctrl-C. It copies the component stack, with file, line and column.
  - **Delivery.** It works through the clipboard. MIT license.
  - **Unconfirmed (snippet only, from mirror pages).** An MCP option (`grab add mcp`) and a Claude server on port 4567.
- **Vercel Comments**, vercel.com/docs/comments/using-comments (**fetched**).
  - **Commenting.** Press `c`, then click to place a comment or highlight text.
  - **Features.** Threads, an inbox, filters by page and by status, Markdown, and @mentions.
  - **Screenshots.** They come by upload, by a camera icon, or by click-and-drag. The last two need the browser extension.
- **Vercel comments command line**, vercel.com/docs/cli/comments (**fetched**). This is good prior art for a command line an agent drives.
  - `vercel comments` has these subcommands:
    - `list`;
    - `inspect`, with `--context`;
    - `open`;
    - `reply`, with `-m`, `--file` or stdin;
    - `resolve` and reopen, with `-m` and `--yes`;
    - `edit` and `delete`.
  - All of them take `--json`.
- **Vercel toolbar on localhost**, the Vercel docs page on adding the toolbar to localhost (**fetched**). This is useful as the contrast to what Omar wants.
  - **Install.** A `@vercel/toolbar` package has Next, Vite and Nuxt plugins, or you add a script tag served from Vercel.
  - **Where comments go.** They are stored on Vercel's servers and need a linked project, so they leave the machine.
- **BugHerd** (**snippet only**). Its browser extension records the CSS selector, plus the browser, OS, screen size and resolution.
- **Marker.io** (**snippet only**).
  - It records the URL, browser, OS, screen size, console logs and failed network requests.
  - It installs as a snippet or as an extension.
- **A gap.** I found nothing on how BugHerd or Marker.io re-find an element after the page changes.

### 3.2 Building blocks

- **modern-screenshot**, GitHub (**fetched**).
  - **Functions.** `domToPng`, `domToJpeg`, `domToWebp`, `domToSvg`, `domToCanvas`, `domToBlob` and more.
  - **License.** MIT. It is a fork of html-to-image.
  - **Limit.** Content from another origin fails because of the browser's cross-origin (CORS) rules.
- **Chrome DevTools Protocol**, `Page.pdl` from the devtools-protocol repo on GitHub (**fetched** with curl; the docs site only returned a redirect).
  - `Page.captureScreenshot` takes `clip` (a viewport rectangle), `format` (png, jpeg or webp) and `captureBeyondViewport`.
  - This is the route to a pixel-exact capture when a browser is driven from outside the page.
- **Playwright**, playwright.dev/docs/screenshots (**fetched**). `locator.screenshot()` captures one element.
- **W3C Web Annotation Data Model**, w3.org/TR/annotation-model (**fetched**). This is the standard answer to "how do I find this element again".
  - **Selector types.** CSS, XPath, text quote (exact text plus prefix and suffix), text position, fragment, range, SVG and data position.
  - **Several at once.** One target may carry several selectors.
  - **Narrowing.** `refinedBy` narrows one selector with another.
- **Vite plugin API**, vite.dev/guide/api-plugin (**fetched**).
  - `transformIndexHtml` can inject tags into the page's body.
  - `configureServer` adds middleware to the dev server.
  - `apply: 'serve'` makes a plugin run in dev only.

### 3.3 Claude Code features for getting told about new comments

- **Monitor tool** (description **read** in this session).
  - Each line the command prints to stdout becomes an event that wakes Claude.
  - A watch can last at most 30 minutes, and must then be started again.
  - It can also listen on a WebSocket.
- **Claude Code channels**, code.claude.com/docs/en/channels-reference.md (**fetched**).
  - **How it works.** An MCP server declares the `claude/channel` experimental capability and sends `notifications/claude/channel` with `{content, meta}`. The event shows up in the session as a `<channel source=…>` message.
  - **Requirements.** It needs Claude Code 2.1.80 or later, and it is a research preview.
  - **The flag.** A channel that is not from the official marketplace needs the `--dangerously-load-development-channels` flag.
  - **When events arrive.** Only while a session is open.
  - **Security.** The docs say to check who sent an event, to block prompt injection.
  - **Packaging.** A plugin can ship a channel, which is turned on with `--channels plugin:<name>@<marketplace>`.
- **Background command plus wait** (seen in the local doc-review skill above).
  - The command blocks until something new arrives, then exits.
  - Each run gives one notification.
- **Session-start hook** (seen in the earlbear repo). It announces open comments when a session begins.

### 3.4 Searches that found nothing

- **"omars-lab review-md".** Nothing came back beyond the repo itself.
- **"earlbear" agentic workflow.** Nothing came back except general articles on agentic workflows. Nothing about Omar's private repos is public, which is what I expected.

## 4. Where the sources disagree

- **Who resolves a thread.**
  - review-md lets Claude resolve, but only when it actually made the change.
  - The earlbear report comments say Claude never resolves; the person who opened the thread does.
  - The local doc-review skill sits between the two. Claude may resolve, but never a thread the user reopened, unless a reply says what changed.
- **Whether comments go in git.**
  - review-md tracks them in git, so the review travels with the document.
  - The local doc-review skill keeps them in a folder git ignores, so they are scratch.
  - earlbear keeps them in a database, split by environment.
- **Where the screenshot library comes from.**
  - The local doc-review skill loads it from a public CDN.
  - earlbear bundles it from npm.
  - Bundling is the only one of the two that fits "nothing leaves the machine".
