// Test helpers: a throwaway git repo with `.page-comments/`, and a way to run
// the command line as a child process. All data here is invented.

import { execFileSync, spawn, spawnSync } from "node:child_process";
import { mkdirSync, mkdtempSync, rmSync } from "node:fs";
import { tmpdir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

export const SCRIPTS = join(dirname(fileURLToPath(import.meta.url)), "..");
export const CLI = join(SCRIPTS, "page-comments.mjs");
export const PLUGIN = join(SCRIPTS, "..", "..");
export const ENABLE = join(PLUGIN, "skills", "enable-page-comments", "scripts", "enable.mjs");

/** A new git repo in the temp folder. With `comments`, `.page-comments/threads/` too. */
export function tempRepo({ comments = true, git = true } = {}) {
  const repo = mkdtempSync(join(tmpdir(), "pc-test-"));
  if (git) {
    execFileSync("git", ["init", "-q", repo]);
    execFileSync("git", ["-C", repo, "config", "user.name", "Test Person"]);
    execFileSync("git", ["-C", repo, "config", "user.email", "test@example.com"]);
    execFileSync("git", ["-C", repo, "commit", "-q", "--allow-empty", "-m", "start"]);
  }
  if (comments) mkdirSync(join(repo, ".page-comments", "threads"), { recursive: true });
  return { repo, store: { repo, dir: join(repo, ".page-comments") }, cleanup: () => rmSync(repo, { recursive: true, force: true }) };
}

/** Run the command line and wait. Returns { code, stdout, stderr }. */
export function cli(args, { cwd, env } = {}) {
  const r = spawnSync(process.execPath, [CLI, ...args], { cwd, encoding: "utf8", env: { ...process.env, ...env }, timeout: 20000 });
  return { code: r.status, stdout: r.stdout, stderr: r.stderr };
}

/** Run a script as a child that keeps running. */
export function startChild(script, args, { cwd } = {}) {
  const child = spawn(process.execPath, [script, ...args], { cwd, stdio: ["ignore", "pipe", "pipe"] });
  let stdout = "";
  let stderr = "";
  child.stdout.on("data", (d) => (stdout += d));
  child.stderr.on("data", (d) => (stderr += d));
  return {
    child,
    out: () => stdout,
    err: () => stderr,
    stop: () =>
      new Promise((res) => {
        if (child.exitCode !== null) return res(child.exitCode);
        child.once("exit", (code) => res(code));
        child.kill("SIGTERM");
      }),
  };
}

/** Poll until `fn()` is truthy, or fail after `ms`. */
export async function until(fn, ms = 8000, step = 50) {
  const end = Date.now() + ms;
  for (;;) {
    const v = await fn();
    if (v) return v;
    if (Date.now() > end) throw new Error("timed out waiting");
    await new Promise((r) => setTimeout(r, step));
  }
}

export const SAMPLE = {
  author: "sam",
  page: { url: "http://127.0.0.1:8766/trips/sample/?day=2", path: "/trips/sample/", title: "Sample trip" },
  viewport: { w: 1440, h: 900, dpr: 2, scrollX: 0, scrollY: 300, scheme: "light" },
  anchor: { type: "element", commentId: null, css: "main > section:nth-of-type(2)", tag: "section", label: "Day 2: museum and park" },
  rev: { bodyHash: "a41c09e2b7d3", ts: "2026-01-02T03:04:05Z", git: { commit: "abc1234", dirty: false } },
  body: "This card should say how long the walk is.",
};
