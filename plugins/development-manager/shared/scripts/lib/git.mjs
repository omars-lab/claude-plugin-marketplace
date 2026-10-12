// The git stamp on a new comment: the current commit, and whether the working
// tree has changes outside `.page-comments/`. Never throws; outside git it
// returns { commit: null, dirty: null }.

import { execFileSync } from "node:child_process";

function git(repo, args) {
  return execFileSync("git", ["-C", repo, ...args], {
    encoding: "utf8",
    timeout: 3000,
    stdio: ["ignore", "pipe", "ignore"],
  }).trim();
}

export function gitStamp(repo) {
  let commit = null;
  let dirty = null;
  try {
    commit = git(repo, ["rev-parse", "--short", "HEAD"]) || null;
  } catch {
    return { commit: null, dirty: null };
  }
  try {
    dirty = git(repo, ["status", "--porcelain", "--", ".", ":(exclude).page-comments"]) !== "";
  } catch {
    dirty = null;
  }
  return { commit, dirty };
}
