// Local ports: which are free, who holds one, and which repo that process runs
// from. Several repos on one Mac each run a site server and a comment server,
// so a fixed port can belong to another repo's server. enable, check and serve
// use this to say so in plain words instead of testing the wrong site or
// failing with EADDRINUSE.
//
// Who holds a port comes from lsof (macOS and most Linux). Without lsof the
// answer is { known: false } and callers fall back to what a bind tells them.

import { spawnSync } from "node:child_process";
import { realpathSync } from "node:fs";
import { createServer } from "node:net";
import { contractHome } from "./shots.mjs";

function run(cmd, args) {
  const r = spawnSync(cmd, args, { encoding: "utf8", timeout: 5000, stdio: ["ignore", "pipe", "ignore"] });
  return r.error ? null : r.stdout || "";
}

// A listener the comment server would clash with on 127.0.0.1: the loopback
// address itself, or every address. A port held only on another address (a
// tailnet address, say) does not stop a server binding 127.0.0.1.
function onLoopback(name) {
  return /^(127\.0\.0\.1|\*|localhost|0\.0\.0\.0|\[::\]|\[::1\]):\d+$/.test(name);
}

/** Can a server bind 127.0.0.1:port right now? */
export function portFree(port) {
  return new Promise((done) => {
    const s = createServer();
    s.once("error", () => done(false));
    s.listen(port, "127.0.0.1", () => s.close(() => done(true)));
  });
}

/** The first port from `start` up that binds, or null after `tries` ports. */
export async function firstFreePort(start, { tries = 50, skip = [] } = {}) {
  for (let p = start; p < start + tries && p <= 65535; p++) {
    if (skip.includes(p)) continue;
    if (await portFree(p)) return p;
  }
  return null;
}

/** The git folder shared by every worktree of the repo at `dir`, or null. */
export function repoKey(dir) {
  const common = run("git", ["-C", dir, "rev-parse", "--path-format=absolute", "--git-common-dir"]);
  if (!common || !common.trim()) return null;
  const top = run("git", ["-C", dir, "rev-parse", "--show-toplevel"]);
  // Compare real paths: a temp folder can be reached through a link (/var and /private/var).
  const real = (p) => {
    try {
      return realpathSync(p);
    } catch {
      return p;
    }
  };
  return { common: real(common.trim()), top: top && top.trim() ? real(top.trim()) : null };
}

function describeProcess(pid) {
  const command = (run("ps", ["-p", String(pid), "-o", "command="]) || "").trim() || null;
  const cwdOut = run("lsof", ["-a", "-p", String(pid), "-d", "cwd", "-Fn"]) || "";
  const cwd = (/^n(.+)$/m.exec(cwdOut) || [])[1] || null;
  return { pid, command, cwd };
}

/**
 * Who listens on 127.0.0.1:port. Returns { known: false } without lsof,
 * { known: true, busy: false } when nothing does, else
 * { known: true, busy: true, pid, command, cwd }.
 */
export function portOwner(port) {
  const outp = run("lsof", ["-nP", `-iTCP:${port}`, "-sTCP:LISTEN", "-Fpn"]);
  if (outp === null) return { known: false };
  let pid = null;
  let found = null;
  for (const line of outp.split("\n")) {
    if (line[0] === "p") pid = Number(line.slice(1));
    else if (line[0] === "n" && onLoopback(line.slice(1)) && pid) {
      found = pid;
      break;
    }
  }
  if (!found) return { known: true, busy: false };
  return { known: true, busy: true, ...describeProcess(found) };
}

/** Every process listening on loopback, as [{ port, pid, command, cwd }]. */
export function listeners() {
  const outp = run("lsof", ["-nP", "-iTCP", "-sTCP:LISTEN", "-Fpn"]);
  if (!outp) return [];
  const seen = new Map();
  let pid = null;
  for (const line of outp.split("\n")) {
    if (line[0] === "p") pid = Number(line.slice(1));
    else if (line[0] === "n" && pid && onLoopback(line.slice(1))) {
      const port = Number(line.slice(line.lastIndexOf(":") + 1));
      if (!seen.has(`${pid}:${port}`)) seen.set(`${pid}:${port}`, { pid, port });
    }
  }
  const procs = new Map();
  return [...seen.values()].map(({ pid: p, port }) => {
    if (!procs.has(p)) procs.set(p, describeProcess(p));
    return { port, ...procs.get(p) };
  });
}

/**
 * Where a process runs from, compared with `repo`: "same" (this checkout),
 * "worktree" (another checkout of the same repo), "other" (a different repo,
 * named by `where`), or "unknown".
 */
export function whose(owner, repo) {
  if (!owner || !owner.cwd) return { rel: "unknown" };
  const theirs = repoKey(owner.cwd);
  const mine = repoKey(repo);
  if (!theirs || !mine) return { rel: "unknown", where: contractHome(owner.cwd) };
  if (theirs.common !== mine.common) return { rel: "other", where: contractHome(theirs.top || owner.cwd) };
  if (theirs.top && mine.top && theirs.top !== mine.top) return { rel: "worktree", where: contractHome(theirs.top) };
  return { rel: "same", where: contractHome(theirs.top || owner.cwd) };
}

/** "python3 serve.py (pid 123) from ~/x", short enough for one report line. */
export function ownerText(owner) {
  // A portOwner() result says busy; a listeners() entry is busy by being listed.
  if (!owner || (!owner.busy && !owner.pid)) return "nothing";
  // The program and its first arguments, each path cut to its last part, so a
  // line names the script without a long (and personal) folder path.
  const words = owner.command ? owner.command.split(/\s+/).slice(0, 3).map((w) => (w.includes("/") ? w.slice(w.replace(/\/+$/, "").lastIndexOf("/") + 1) : w)) : [];
  const prog = words.length ? words.join(" ") : "a process";
  const short = prog.length > 60 ? prog.slice(0, 57) + "..." : prog;
  return `${short} (pid ${owner.pid})${owner.cwd ? ` from ${contractHome(owner.cwd)}` : ""}`;
}

/** Is this the comment server (page-comments.mjs serve)? */
export function isCommentServer(owner) {
  return !!(owner && owner.command && owner.command.includes("page-comments.mjs") && /\bserve\b/.test(owner.command));
}
