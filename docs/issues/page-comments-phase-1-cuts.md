# Page comments: what phase 1 left out, and why

**Status:** open; each item names when it comes back
**Affects:** `plugins/development-manager/`, `docs/design/localhost-comments/design.md` sections 8,
11, 12 and 17

Phase 1 ships the whole comment loop. These parts of the design were left out of it on purpose.

| Left out | Why | When it comes back |
|---|---|---|
| The test that the thread schema matches review-md's copy (section 12) | review-md has no `thread.schema.json` yet, so there is nothing to compare against. The field names and `--json` shape follow section 12. | When review-md takes the schema (phase 5). |
| A `package.json` script as the way to start the comment server | Phase 1 writes a make target only. In a repo with no Makefile, enable prints the `serve` command to run instead of editing `package.json`. | With the Vite adapter (phase 5), where `package.json` is the natural place. |
| The screenshot folder question and the phone setup in enable (section 8, step 2) | Both serve phase 2 and 3 features that are not built yet. Asking now would store answers nothing reads. | Phases 2 and 3. |
| The Vite live-reload check (section 17, phase 1) | The proof used the adventures planner through the proxy. No Vite app was tried, so the live-reload socket through the proxy is unproven. | Still to do before phase 1 is called done. |
