---
name: find-design-references
description: Find the sites and open-source repos a page should look like, keep them in a shared list, screenshot them at desktop and phone width, and lay our page beside them to list what to change. Use when asked to "find references", "what should this look like", "compare it to good sites", "make it feel premium", "why does ours look worse", "find a GitHub repo with a nice board/sidebar/calendar", or as the first step of design-engaging-ui, before any direction is picked.
---

# Find design references

Without references, "looks right" is a guess, and pages built with AI slide into the same default
look. This skill gives a page two or three real things to aim at, and then measures the gap.
A reference is either:

- **a site**: a live page whose look fits the brief; or
- **a repo**: an open-source app or design system on GitHub. A repo is often the better reference,
  because its source holds the exact colours, type sizes and spacing. We read those values instead
  of guessing them from a picture.

All references go into one shared list, so the next page can reuse a pick instead of searching again.

## Rules

- **Two researchers, then a checker.** Picking references decides the look, so one pass is not
  trusted. Start two fresh agents (not forks) on the same question, each in its own worktree and on
  its own branch. A third agent then reads both and writes the picks. Agreement between the two is
  evidence. A pick only one of them found, or one that rests on a search snippet, is flagged.
- **Read repos, don't run them.** Read a repo's token files on GitHub. Never clone, install or run
  a stranger's code to get a screenshot. Shoot its live demo if it has one, otherwise its GitHub
  page.
- **The shots stay local.** Reference shots go in the list's ignored `.cache/`. Our own shots show
  real data, so they stay there too. Neither is committed or sent anywhere.
- **Borrow named things, not a whole look.** Every pick lists concrete things to borrow, such as
  "sidebar items 32px tall, the current one marked by a 2px bar". "Clean and modern" is not a
  thing to borrow.
- **Compare every page, at both widths.** The comparison covers each of our pages that a reference
  is meant for, at 1280 and 390, not just the landing page.

## Where the list lives

`references.yaml` sits at the root of the catalog repo: `$HUBS_REPO`, else `~/Workspace/git/hubs`.
For a page outside that catalog, keep the same file in the page's own repo and pass `--list`.

```yaml
references:
  - id: short-kebab-id
    name: Readable Name
    kind: repo                  # site or repo
    url: https://...            # what to screenshot: the page, or a repo's demo, else its GitHub page
    repo: https://github.com/owner/name   # repos only
    license: MIT                          # repos only
    tokens: src/styles/tokens.css         # repos only: the file the values come from
    good_for: [sidebar, board]  # sidebar calendar board table filing stats review landing forms type
    borrow:
      - one concrete thing to copy
    checked: 2026-10-16         # when someone last looked at it
    found_by: both              # both, a, b: which researcher found it
```

Each page records the ids it was compared with in its own `docs/design.md`, under "References".
That way the choice travels with the page.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/references.py check` | Says what is wrong with the list: missing fields, unknown `good_for` words, a repo with no license or tokens file, an id listed twice. Exit 1 on any problem | After every edit to the list | `uv run "${CLAUDE_PLUGIN_ROOT}/skills/find-design-references/scripts/references.py" check` |
| `scripts/references.py shoot` | Screenshots listed references, or any one page, at 1280×820 and 390×844 into `.cache/references/<name>/`. Only reads, so nothing gets submitted or bought | After adding picks; and once for each of our pages, with `--url` and `--name ours-<page>` | `... references.py shoot --ids a,b` / `... references.py shoot --url <address> --name ours-<page> [--full]` |
| `scripts/references.py sheet` | One HTML page with our shot beside each reference, desktop row then phone row, at the same scale, with each reference's "borrow" notes under it | To compare one of our pages with its references | `... references.py sheet --ours ours-<page> --ids a,b --title "<Page>"` |

Every command takes `--list <file>` and `--out <folder>` to work outside the hubs repo. Each run
logs to `<out>/references.log`.

## Task management

```javascript
TaskCreate({ subject: "Check the list first", description: "Picks already in references.yaml that fit this page's brief and kinds of page", activeForm: "Checking the reference list" })
TaskCreate({ subject: "Two researchers", description: "Two fresh agents, own worktrees and branches: sites and GitHub repos, findings plus picks", activeForm: "Researching references" })
TaskCreate({ subject: "Checker picks", description: "Read both, re-open the sources behind each pick, write the consolidated picks into references.yaml", activeForm: "Checking the picks" })
TaskCreate({ subject: "Shoot and compare", description: "Shoot the picks and each of our pages; a sheet per page; ranked list of what to change", activeForm: "Comparing with references" })
```

## Steps

1. **Start from the brief.** Read the page's brief in `docs/design.md`: who opens it, its one job,
   and three words for how it should feel. If there is none, write it first (see
   `design-engaging-ui` step 2). Then list the kinds of page it has, using the `good_for` words.
2. **Check the list.** Run `check`, then read `references.yaml` for picks whose `good_for` covers
   this page's kinds and that fit its three words. If they cover every kind, skip to step 5.
3. **Two researchers.** Start two fresh `general-purpose` agents in parallel with the same prompt.
   Give each its own worktree of the catalog repo
   (`git -C <catalog> worktree add ../<catalog>-refs-a -b design-refs-a`, and `-b` for the other).
   The prompt holds:
   - the brief;
   - the kinds of page that need a reference;
   - the look to avoid (purple gradients, glassy cards, everything in a rounded box);
   - both sources: live sites, and GitHub repos with their demo, license and token file;
   - the output. That is `research/design-references/<page>/<a|b>/findings.md`, which covers 10 to 14
     candidates and marks each claim as fetched or snippet-only. Plus `picks.md`, which names 3 to 5
     picks in the YAML shape above.
   - Each researcher commits on its own branch and does not read the other's folder.
4. **One checker.** After both finish, start a third fresh agent with both branches' files. It:
   - re-opens the sources behind each proposed pick, and for repos the token file itself;
   - marks where the two agree and where they disagree, and which side the source supports;
   - flags anything only one found or that rests on a snippet;
   - writes `research/design-references/<page>/picks.md` (the one to act on), and adds the final
     3 to 5 picks to `references.yaml`, with `found_by` set;
   - runs `check`, and commits on its own branch.

   Sometimes the two researchers point the look in different directions, and the sources don't
   settle it. One example is an editorial site against a dense tool. Then shoot both candidates
   (step 5) and ask Omar with `AskUserQuestion`. Each option is one candidate, with its shot path
   in the preview. Each also says what it does well, what it gives up, and which pages it would
   change. Recommend one.
5. **Shoot.**
   - Run `shoot --ids <picks>`.
   - Shoot each of our pages that a pick is meant for, with `--url` and `--name ours-<page>`.
     Add `--full` for long pages.
   - Look at every shot. A cookie banner, a sign-in wall or a blank page means the shot can't be
     used: pick the demo page, or drop the reference and say why.
6. **Compare, page by page.**
   - For each of our pages, run `sheet` with the picks meant for it.
   - Open the sheet and read it at both widths.
   - List each difference that matters, as one line each: what the reference does, what ours does,
     and the concrete change. For example, "Their board columns have no border and a 12px gap.
     Ours have a 1px border and a coloured top rule. Drop both."
   - Rank the list by what most raises the page toward the reference, for the effort it takes.
7. **Hand over.**
   - Write the ranked list into the page's `docs/design.md` under "References", with the ids
     compared.
   - Then go on in `design-engaging-ui` step 3, which renders directions, or step 5, which builds
     and checks if the direction is already chosen. The references are now what each round is
     compared against.

## Output

```
References for <page>: 3 picks (2 found by both researchers, 1 by one, flagged)
  linear-sidebar   site  sidebar          borrow: 32px rows, 2px current bar, muted group labels
  plane-board      repo  board, table     borrow: column header 13px/600 + count, no column borders
  cal-calendar     repo  calendar         borrow: today ring, 11px weekday caps, event dots
List:     references.yaml (check: 0 problems), branch design-refs-check
Compared: 6 pages at 1280 and 390; sheets in .cache/references/sheet-ours-*.html
Top changes: 1. ... 2. ... 3. ...
Next:     design-engaging-ui step 5, comparing each round against these sheets
```
