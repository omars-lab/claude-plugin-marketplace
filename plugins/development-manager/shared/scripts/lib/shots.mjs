// Screenshots of a comment's element (design sections 6 and 14).
//
// A picture lives outside git. By default it goes to iCloud Drive, under
//   <shot folder>/page-comments/<repo>/<thread-id>/comment.png
//   <shot folder>/page-comments/<repo>/<thread-id>/after-<commit>.png
// and the thread file keeps only a `shot` event that points at it. The pointer
// is relative to the iCloud Drive root, so it reads the same on the Mac and
// the phone. When the shot folder is not inside iCloud Drive, or iCloud Drive
// is not on this Mac, pictures go to `.page-comments/shots/<thread-id>/`
// (ignored by git) and the pointer is `local`, relative to `.page-comments/`.
//
// Where the shot folder is, first match wins:
//   1. the repo's `.page-comments/config.json`, key `shotsDir`;
//   2. the global config, `~/.config/development-manager/config.json`, key `shotsDir`;
//   3. the design default, `CloudDesktop/data` inside iCloud Drive.
// Paths are stored with `~` and expanded when used. Two environment variables
// move the global config and the iCloud Drive root, so tests never touch the
// real ones: DEVELOPMENT_MANAGER_CONFIG and PAGE_COMMENTS_ICLOUD_ROOT.

import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, renameSync, statSync, writeFileSync } from "node:fs";
import { homedir } from "node:os";
import { basename, dirname, isAbsolute, join, relative, resolve, sep } from "node:path";
import { readConfig } from "./repo.mjs";
import { appendEvent, isThreadId } from "./store.mjs";

export const SHOT_MAX = 8 * 1024 * 1024;
export const ROLES = ["comment", "after"];
const PNG_MAGIC = Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]);
const NAME_RE = /^(comment|after-[0-9a-f]{7,12})\.png$/;
const COMMIT_RE = /^[0-9a-f]{7,40}$/;

// ---- Paths ------------------------------------------------------------------------

/** `~/x` to `/Users/<you>/x`. Anything else is returned as it is. */
export function expandHome(p) {
  if (typeof p !== "string") return p;
  if (p === "~") return homedir();
  if (p.startsWith("~/")) return join(homedir(), p.slice(2));
  return p;
}

/** `/Users/<you>/x` to `~/x`, so a stored path never names the person. */
export function contractHome(p) {
  const home = homedir();
  if (p === home) return "~";
  if (p.startsWith(home + sep)) return "~/" + p.slice(home.length + 1);
  return p;
}

/** The iCloud Drive root on this Mac. */
export function icloudRoot(env = process.env) {
  return resolve(expandHome(env.PAGE_COMMENTS_ICLOUD_ROOT || "~/Library/Mobile Documents/com~apple~CloudDocs"));
}

/** Where the global config file is. */
export function globalConfigPath(env = process.env) {
  return resolve(expandHome(env.DEVELOPMENT_MANAGER_CONFIG || "~/.config/development-manager/config.json"));
}

export function readGlobalConfig(env = process.env) {
  try {
    const c = JSON.parse(readFileSync(globalConfigPath(env), "utf8"));
    return c && typeof c === "object" ? c : {};
  } catch {
    return {};
  }
}

/** The design default, written with `~` when it sits under the home folder. */
export function defaultShotsDir(env = process.env) {
  return contractHome(join(icloudRoot(env), "CloudDesktop", "data"));
}

/**
 * The shot folder setting for a repo, with where it came from.
 * Returns { dir (as stored, maybe with ~), from: "repo" | "global" | "default" }.
 */
export function shotsSetting(store, env = process.env) {
  const repo = store ? readConfig(store).shotsDir : undefined;
  if (typeof repo === "string" && repo.trim()) return { dir: repo.trim(), from: "repo" };
  const global = readGlobalConfig(env).shotsDir;
  if (typeof global === "string" && global.trim()) return { dir: global.trim(), from: "global" };
  return { dir: defaultShotsDir(env), from: "default" };
}

function inside(child, parent) {
  const r = relative(parent, child);
  return r === "" || (!!r && !r.startsWith("..") && !isAbsolute(r));
}

function isDir(p) {
  try {
    return statSync(p).isDirectory();
  } catch {
    return false;
  }
}

/**
 * Where this repo's pictures go right now.
 * Returns { kind: "icloud" | "local", base, dir, from, reason? } where `base` is
 * the folder that holds one sub-folder per thread.
 *
 * iCloud Drive counts as "on" when its root folder exists. `brctl accounts` on
 * this Mac prints nothing whether or not an account is signed in, so it is not
 * asked (docs/issues/page-comments-stage-2-icloud-check.md).
 */
export function shotTarget(store, env = process.env) {
  const setting = shotsSetting(store, env);
  const dir = resolve(expandHome(setting.dir));
  const root = icloudRoot(env);
  const local = { kind: "local", base: join(store.dir, "shots"), dir, from: setting.from };
  if (!isDir(root)) return { ...local, reason: "iCloud Drive is not on this Mac" };
  if (!inside(dir, root)) return { ...local, reason: "the shot folder is not inside iCloud Drive" };
  return { kind: "icloud", base: join(dir, "page-comments", repoName(store.repo)), dir, from: setting.from };
}

/**
 * The repo's name for its picture folder. A git worktree is named after the
 * main checkout it belongs to, so pictures from every worktree of one repo land
 * in one folder. Its `.git` is a file reading `gitdir: <main>/.git/worktrees/<name>`.
 */
export function repoName(repo) {
  try {
    const m = /^gitdir:\s*(.+)$/m.exec(readFileSync(join(repo, ".git"), "utf8"));
    const gitdir = m && resolve(repo, m[1].trim());
    if (gitdir && basename(dirname(gitdir)) === "worktrees" && basename(dirname(dirname(gitdir))) === ".git") {
      return basename(dirname(dirname(dirname(gitdir))));
    }
  } catch {
    // `.git` is a folder (the main checkout) or is missing
  }
  return basename(repo);
}

/** The file name a shot is saved under. The server and command line pick it, never the page. */
export function shotName(role, commit) {
  if (role === "comment") return "comment.png";
  if (role === "after" && typeof commit === "string" && COMMIT_RE.test(commit)) return `after-${commit.slice(0, 12)}.png`;
  throw new Error("an after shot needs the commit it was taken against (7 to 40 hex characters)");
}

export function isShotName(name) {
  return typeof name === "string" && NAME_RE.test(name);
}

/**
 * The full path a shot pointer names on this Mac, or null when the pointer is
 * malformed. A pointer must end in `<thread-id>/<name>` and may not climb out.
 */
export function shotPath(store, shot, env = process.env) {
  if (!shot || typeof shot !== "object") return null;
  const ptr = typeof shot.icloud === "string" ? shot.icloud : typeof shot.local === "string" ? shot.local : null;
  if (!ptr || ptr.includes("\\") || ptr.includes("\0") || ptr.startsWith("/")) return null;
  const parts = ptr.split("/");
  if (parts.some((p) => p === "" || p === "." || p === "..")) return null;
  if (parts.length < 2 || !isShotName(parts[parts.length - 1]) || !isThreadId(parts[parts.length - 2])) return null;
  const root = typeof shot.icloud === "string" ? icloudRoot(env) : store.dir;
  const full = resolve(root, ...parts);
  return inside(full, root) ? full : null;
}

/** Is the picture on this Mac? "ok", "placeholder" (iCloud has not downloaded it) or "missing". */
export function shotFileState(full) {
  if (!full) return "missing";
  try {
    if (statSync(full).isFile()) return "ok";
  } catch {
    // fall through
  }
  if (existsSync(join(dirname(full), `.${basename(full)}.icloud`))) return "placeholder";
  return "missing";
}

// ---- Pictures -----------------------------------------------------------------------

export function isPng(buf) {
  return Buffer.isBuffer(buf) && buf.length > PNG_MAGIC.length && buf.subarray(0, 8).equals(PNG_MAGIC);
}

/** First 12 hex characters of the picture's sha256, so a changed file is noticed. */
export function shortSha(buf) {
  return createHash("sha256").update(buf).digest("hex").slice(0, 12);
}

/** Does the thread already have a comment shot that worked? (A failed one does not count.) */
export function hasCommentShot(thread) {
  return !!(thread && Array.isArray(thread.shots) && thread.shots.some((s) => s.role === "comment" && !s.error));
}

/**
 * Save a picture for a thread and append its `shot` event.
 * Options: { role, commit (after shots), author }. Returns the event written.
 */
export function saveShot(store, id, buf, { role, commit, author }, env = process.env) {
  if (!isThreadId(id)) throw new Error(`not a thread id: ${id}`);
  if (!ROLES.includes(role)) throw new Error(`role is comment or after, not ${role}`);
  if (!isPng(buf)) throw new Error("not a PNG picture");
  if (buf.length > SHOT_MAX) throw new Error(`the picture is over ${SHOT_MAX / 1024 / 1024} MB`);
  const name = shotName(role, commit);
  const target = shotTarget(store, env);
  const folder = join(target.base, id);
  mkdirSync(folder, { recursive: true });
  // Written under a hidden name, then renamed, so iCloud never copies half a file.
  const tmp = join(folder, `.${name}.${process.pid}.tmp`);
  writeFileSync(tmp, buf);
  renameSync(tmp, join(folder, name));
  const event = { ev: "shot", role, author };
  if (target.kind === "icloud") event.icloud = relative(icloudRoot(env), join(folder, name)).split(sep).join("/");
  else event.local = relative(store.dir, join(folder, name)).split(sep).join("/");
  event.sha = shortSha(buf);
  if (role === "after") event.commit = commit;
  return appendEvent(store, id, event);
}

/** A capture that failed: a `shot` event with the reason instead of a pointer. */
export function recordShotError(store, id, { role = "comment", reason, author }) {
  const text = typeof reason === "string" && reason.trim() ? reason.trim().slice(0, 300) : "the capture failed";
  return appendEvent(store, id, { ev: "shot", role: ROLES.includes(role) ? role : "comment", author, error: text });
}

/** The shot paths, for `--check` and the enable report. */
export function shotsSummary(store, env = process.env) {
  const t = shotTarget(store, env);
  return { kind: t.kind, folder: contractHome(t.base), from: t.from, reason: t.reason || null };
}
