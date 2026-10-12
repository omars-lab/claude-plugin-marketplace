// `restamp`, run by the post-commit hook that enable installs (design section 4,
// phase 4). A comment made on uncommitted work is stamped with the commit it was
// made on and `dirty: true`. When the next commit lands that work, this appends
// one `landed` event to the thread, naming the new commit. It never rewrites a
// thread file and never amends the commit; `rev.git` keeps where the comment was
// made, and `rev.landed` says where the work went.
//
// It is a guess, kept narrow:
//   - only threads stamped dirty on the commit that is now HEAD's parent;
//   - not during a rebase, cherry-pick, revert or merge, and not for a merge
//     commit (none of those is "the work you were looking at, committed");
//   - not for a commit that only changes `.page-comments/` itself;
//   - a thread that already has a landed commit keeps it.
// An amend or a rebase afterwards leaves the landed commit pointing at the old
// commit; the comment's text and anchors still say what it was about.

import { existsSync, realpathSync } from "node:fs";
import { isAbsolute, join, relative } from "node:path";
import { execFileSync } from "node:child_process";
import { addLanded, readAll } from "./store.mjs";

function git(repo, args) {
  return execFileSync("git", ["-C", repo, ...args], {
    encoding: "utf8",
    timeout: 3000,
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
}

const BUSY = ["rebase-merge", "rebase-apply", "CHERRY_PICK_HEAD", "REVERT_HEAD", "MERGE_HEAD", "sequencer"];

/**
 * Look at HEAD and stamp the threads its commit landed.
 * Returns { landed: [{ id, from }], commit } or { skipped: "<why>" }.
 */
export function restamp(store) {
  const repo = store.repo;
  let top;
  try {
    top = git(repo, ["rev-parse", "--show-toplevel"]);
  } catch {
    return { skipped: "not a git repo" };
  }
  for (const name of BUSY) {
    let p;
    try {
      p = git(repo, ["rev-parse", "--git-path", name]);
    } catch {
      continue;
    }
    if (existsSync(isAbsolute(p) ? p : join(repo, p))) return { skipped: `a ${name.toLowerCase().replace(/_head$/, "")} is in progress` };
  }
  let line;
  try {
    line = git(repo, ["rev-list", "--parents", "-n", "1", "HEAD"]);
  } catch {
    return { skipped: "no commit yet" };
  }
  const [head, ...parents] = line.split(/\s+/).filter(Boolean);
  if (parents.length !== 1) return { skipped: parents.length ? "a merge commit" : "the first commit" };
  let changed = "";
  try {
    // Both real paths: on a Mac /tmp is /private/tmp, and git prints the real one.
    const own = relative(realpathSync(top), realpathSync(store.dir)).split("\\").join("/") || ".page-comments";
    changed = git(top, ["diff-tree", "--no-commit-id", "--name-only", "-r", "HEAD", "--", ".", `:(exclude)${own}`]);
  } catch {
    return { skipped: "could not read the commit" };
  }
  if (!changed) return { skipped: "the commit only changes .page-comments/" };
  const parent = parents[0];
  const short = git(repo, ["rev-parse", "--short", head]);
  const landed = [];
  for (const t of readAll(store)) {
    const g = (t.rev && t.rev.git) || {};
    if (g.dirty !== true || typeof g.commit !== "string" || !g.commit || t.rev.landed) continue;
    if (!parent.startsWith(g.commit.toLowerCase())) continue;
    addLanded(store, t.id, { commit: short, from: g.commit });
    landed.push({ id: t.id, from: g.commit });
  }
  return { landed, commit: short };
}
