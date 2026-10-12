// Finding the `.page-comments/` folder for a repo, and its paths.

import { existsSync, readFileSync, statSync } from "node:fs";
import { dirname, join, resolve } from "node:path";

export const FOLDER = ".page-comments";

/**
 * Walk up from `start` looking for `.page-comments/`. Stops at the git root
 * (the first folder holding `.git`), so a stray folder above the repo is never
 * picked up. Outside any git repo, only `start` itself is checked.
 * Returns { repo, dir } or null.
 */
export function findStore(start = process.cwd()) {
  const first = resolve(start);
  if (isDir(join(first, FOLDER))) return { repo: first, dir: join(first, FOLDER) };
  if (!gitRootAbove(first)) return null; // not in a git repo: only `start` counts
  let here = first;
  for (;;) {
    const dir = join(here, FOLDER);
    if (isDir(dir)) return { repo: here, dir };
    if (existsSync(join(here, ".git"))) return null; // reached the git root
    const up = dirname(here);
    if (up === here) return null;
    here = up;
  }
}

/** Like findStore, but `--repo <path>` names the repo directly. */
export function storeFor(repoFlag) {
  if (repoFlag) {
    const repo = resolve(repoFlag);
    const dir = join(repo, FOLDER);
    return isDir(dir) ? { repo, dir } : null;
  }
  return findStore();
}

export function paths(store) {
  const { dir } = store;
  return {
    threads: join(dir, "threads"),
    config: join(dir, "config.json"),
    install: join(dir, "install.json"),
    state: join(dir, ".state"),
    server: join(dir, ".state", "server.json"),
    serverLog: join(dir, ".state", "server.log"),
    watchLog: join(dir, ".state", "watch.log"),
    waitCursor: join(dir, ".state", "wait-cursor.json"),
  };
}

export function readConfig(store) {
  try {
    return JSON.parse(readFileSync(paths(store).config, "utf8"));
  } catch {
    return {};
  }
}

function gitRootAbove(start) {
  let here = start;
  for (;;) {
    if (existsSync(join(here, ".git"))) return here;
    const up = dirname(here);
    if (up === here) return null;
    here = up;
  }
}

function isDir(p) {
  try {
    return statSync(p).isDirectory();
  } catch {
    return false;
  }
}
