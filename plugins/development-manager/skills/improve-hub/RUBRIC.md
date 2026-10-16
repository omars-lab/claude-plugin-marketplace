# improve-hub rubric

What a good hub looks like, one row per check. `improve-hub` reads this file at run time, so a row
can be added or sharpened without touching the skill.

Each row has:

- **How to tell:** `script` means `audit_hub.py` prints it; `look` means you have to look at the page.
- **ROI:** how much the fix is worth for the effort, from 5 (do first) to 1 (log it). It is a
  starting point; raise it when the finding blocks Omar or exposes data, and lower it when the fix
  turns out large.

## Catalog and ports (script)

| Id | Check | Why it matters | Fix | ROI |
|---|---|---|---|---|
| C1 | The repo has a `hub.yaml` | Without it the hub is not on the hubs page and has no name | Follow the hubs repo's join checklist (`research/ai-site-building/join-the-catalog.md`) | 5 |
| C2 | The catalog's own check is clean for this repo | Port clashes and missing make targets break other hubs too | Fix what it names; to-dos are known port moves, do them when touching the repo | 4 |
| P1 | Each runner's port is written in the repo's own config or make target | A port worked out at run time (a hash of the folder name, a framework default) changes in a worktree or a renamed folder, and then the hub runs where nothing looks for it | Put the port in the server config and the make target, matching `hub.yaml` | 5 |
| P2 | Vite servers set `strictPort: true` | Without it a taken port silently moves the hub to another one | Add `strictPort: true` next to the port | 5 |
| P3 | Everything the repo serves listens on `127.0.0.1` only | A server on a Tailscale or network address skips every sign-in the catalog relies on | Bind to `127.0.0.1`. To open one hub on another device, Omar adds a `tailscale serve` entry for it; never bind the server itself wider, and never Funnel | 5 |
| P4 | The hub runs on the port `hub.yaml` lists | The hubs page and the `<name>.localhost` address only know that port | Start it through its make target; fix P1 if the port drifted | 4 |
| S1 | Requests that change data need a sign-in once the hub is reachable beyond this Mac | Anyone who can load the page can then change the data | Keep it on loopback, or check a token or the Tailscale login header on each write | 5 when exposed, else note only |
| F1 | Page comments are on | Omar gives feedback fastest by clicking on the thing he means | `development-manager:enable-page-comments`, on the odd port after the hub's | 2 |
| V1 | A site map exists, is under two weeks old, and has no failed pages | It is the quickest look at every page, and a before-and-after pair catches pages that broke | `make sitemap HUB=<id>` in the hubs repo with the hub running, then look at it | 3 |

## The page itself (look)

Look at the site map's shots, or open the page. Use `visual-site-review` for the screenshot
critique when it is installed. When a fix needs design work rather than a one-line change, hand it to
`design-engaging-ui`; its `PRINCIPLES.md` goes deeper on each of these rows.

| Id | Check | How to tell | Fix | ROI |
|---|---|---|---|---|
| L1 | The landing page says what the hub is for and what to do first | Someone who has never seen it knows in five seconds | One line of purpose and the main action at the top | 4 |
| L2 | Every page loads, with no errors in the console | Site map has no blank or failed shots; open a few pages with the browser tools and read the console | Fix the error at the source | 5 |
| L3 | It works at phone width (390 px) | Resize and look: no sideways scrolling, nothing cut off, buttons big enough to tap | Wrap, stack, or hide the less important columns | 3 |
| L4 | Empty, loading and error states say something useful | Open a view with no data, or while the server is slow | A line that says what is missing and how to fill it | 3 |
| L5 | One consistent look: the same colours, type, spacing and components on every page | Lay the shots side by side | Pull the values into one place (CSS variables, a theme file) and use them everywhere | 2 |
| L6 | The design is the hub's own, not the default AI look (purple gradients, glowing cards, emoji headings) | Look at the shots | Pick the hub's own small set of colours and type, and write them down in the repo | 2 |

## Accessibility (script, then look)

AI-built pages often have problems that automated checkers pass, so this takes two steps.

| Id | Check | How to tell | Fix | ROI |
|---|---|---|---|---|
| A1 | An automated scan has no serious findings | Lighthouse through the Chrome dev tools, or axe | Fix what it names | 3 |
| A2 | Image descriptions, labels and headings mean something | Read them: an image described as "image", a button labelled "click", headings that skip levels | Write them for someone who can't see the page | 3 |
| A3 | It works with the keyboard alone | Tab through the main action; focus is visible and in order | Use real buttons and links; show the focus outline | 2 |

## Adding a row

Add a row when a pass over a hub finds something this rubric missed and the same problem could
show up in another hub. Give it the next free id in its group, and say in "Why it matters" what
went wrong. If `audit_hub.py` can check it, add the check there in the same change, and add a row
to the script table in `SKILL.md` if it needs a new flag.
