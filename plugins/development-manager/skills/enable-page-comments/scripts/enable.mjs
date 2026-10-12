#!/usr/bin/env node
// enable-page-comments: turn page comments on in a repo, check the whole loop
// works, or take it all out again. Node 18, no dependencies.
//
//   enable.mjs --detect [--repo .] [--json]
//   enable.mjs --repo . (--target <url> | --root <dir>) [--port 8766]
//   enable.mjs --check [--repo .]
//   enable.mjs --undo [--repo .] [--purge [--force]]
//
// Enabling writes into the target repo, and every change outside
// `.page-comments/` is listed in `.page-comments/install.json`, so --undo
// removes exactly that and nothing else:
//   - `.page-comments/` with threads/, config.json, .gitattributes, .gitignore
//     and the `run` launcher;
//   - a make target between `# page-comments:begin` / `# page-comments:end`;
//   - the plugin turned on in the repo's committed `.claude/settings.json`, so
//     every session opened in the repo has the answering skill and the watcher;
//   - a marked block in the repo's CLAUDE.md that says to follow
//     `development-manager:answer-page-comments` when the watcher prints a comment.
//
// Exit codes: 0 ok, 1 a check failed, 2 bad usage, 3 not found.

import { execFileSync, spawn, spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, readdirSync, readFileSync, rmSync, rmdirSync, writeFileSync } from "node:fs";
import { request } from "node:http";
import { basename, dirname, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const HERE = dirname(fileURLToPath(import.meta.url));
export const PLUGIN_ROOT = resolve(HERE, "..", "..", "..");
const CLI = join(PLUGIN_ROOT, "shared", "scripts", "page-comments.mjs");
const PLUGIN = "development-manager";
const FOLDER = ".page-comments";
const MAKE_BEGIN = "# page-comments:begin";
const MAKE_END = "# page-comments:end";
const MD_BEGIN = "<!-- page-comments:begin -->";
const MD_END = "<!-- page-comments:end -->";
const CHECK_TEXT = "[enable check] A test comment from enable-page-comments. It is removed right away; ignore it.";

// ---- Small helpers ---------------------------------------------------------------------

class Exit extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}
const out = (s = "") => process.stdout.write(s + "\n");

function parseArgs(argv) {
  const values = new Set(["repo", "target", "root", "port", "marketplace", "author", "plugin-root"]);
  const bools = new Set(["detect", "check", "undo", "purge", "force", "json", "help"]);
  const flags = {};
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (!a.startsWith("--")) throw new Exit(2, `unexpected argument: ${a}`);
    let [name, value] = a.slice(2).split(/=(.*)/s);
    if (bools.has(name)) flags[name] = true;
    else if (values.has(name)) {
      if (value === undefined) value = argv[++i];
      if (value === undefined) throw new Exit(2, `--${name} needs a value`);
      flags[name] = value;
    } else throw new Exit(2, `unknown flag --${name}`);
  }
  return flags;
}

function readText(path) {
  try {
    return readFileSync(path, "utf8");
  } catch {
    return null;
  }
}

function readJson(path) {
  const t = readText(path);
  if (t === null) return null;
  try {
    return JSON.parse(t);
  } catch {
    throw new Exit(1, `${path} is not valid JSON; fix it by hand first, then run this again`);
  }
}

function writeJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  writeFileSync(path, JSON.stringify(value, null, 2) + "\n");
}

function gitRoot(dir) {
  try {
    return execFileSync("git", ["-C", dir, "rev-parse", "--show-toplevel"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return null;
  }
}

function repoOf(flags) {
  const start = resolve(flags.repo || process.cwd());
  if (!existsSync(start)) throw new Exit(3, `no such folder: ${start}`);
  return gitRoot(start) || start;
}

/** The marketplace this plugin came from, for the `enabledPlugins` key. */
export function marketplaceName(pluginRoot = PLUGIN_ROOT, flag) {
  if (flag) return flag;
  // Running from a marketplace checkout: plugins/<name>/ under the marketplace root.
  const mp = readText(join(pluginRoot, "..", "..", ".claude-plugin", "marketplace.json"));
  if (mp) {
    try {
      const name = JSON.parse(mp).name;
      if (name) return name;
    } catch {
      // fall through
    }
  }
  // Installed: ~/.claude/plugins/cache/<marketplace>/<plugin>/<version>/
  const parts = pluginRoot.split("/");
  const at = parts.lastIndexOf(PLUGIN);
  if (at >= 1 && parts[at - 2] === "cache") return parts[at - 1];
  return null;
}

function defaultAuthor(repo) {
  try {
    const name = execFileSync("git", ["-C", repo, "config", "user.name"], { encoding: "utf8", stdio: ["ignore", "pipe", "ignore"] }).trim();
    const first = name.split(/\s+/)[0].toLowerCase().replace(/[^a-z0-9._-]/g, "");
    if (first && first !== "claude") return first;
  } catch {
    // no git name
  }
  return "me";
}

// ---- Detect -------------------------------------------------------------------------------

/** How the repo serves its pages, and which mode fits. */
export function detect(repo) {
  const make = readText(join(repo, "Makefile"));
  if (make) {
    const m = /^(serve|dev|start|preview)\s*:[^\n]*\n((?:\t[^\n]*\n?)+)/m.exec(make);
    if (m) {
      const port = (/--port[ =]\$\(or \$\(PORT\),(\d+)\)/.exec(m[2]) || /--port[ =](\d{2,5})\b/.exec(m[2]) || /:(\d{4,5})\b/.exec(m[2]) || [])[1] || "8000";
      return {
        mode: "target",
        target: `http://127.0.0.1:${port}`,
        how: `make ${m[1]}`,
        why: `The Makefile's \`${m[1]}\` target runs a server on port ${port}. The comment server sits in front of it, so the site's own API keeps working.`,
      };
    }
  }
  const pkg = readJson(join(repo, "package.json"));
  const scripts = (pkg && pkg.scripts) || {};
  for (const name of ["dev", "start", "serve", "preview"]) {
    const s = scripts[name];
    if (!s) continue;
    const port = (/--port[ =](\d{2,5})/.exec(s) || [])[1] || (/\bvite\b/.test(s) ? (name === "preview" ? "4173" : "5173") : /next\b/.test(s) ? "3000" : /astro\b/.test(s) ? "4321" : "3000");
    return {
      mode: "target",
      target: `http://127.0.0.1:${port}`,
      how: `npm run ${name}`,
      why: `package.json's \`${name}\` script runs a dev server, most likely on port ${port}. Check the port it prints. The comment server sits in front of it.`,
    };
  }
  for (const dir of [".", "site", "public", "docs", "dist", "build", "_site"]) {
    if (existsSync(join(repo, dir, "index.html"))) {
      return { mode: "root", root: dir, how: "none", why: `No server found, but ${dir === "." ? "the repo root" : `${dir}/`} has an index.html. The comment server serves that folder itself.` };
    }
  }
  return { mode: null, why: "No server and no index.html found. Say which URL or folder to use with --target or --root." };
}

// ---- The marked blocks ----------------------------------------------------------------------

function stripBlock(text, begin, end) {
  const i = text.indexOf(begin);
  if (i < 0) return { text, found: false };
  const j = text.indexOf(end, i);
  if (j < 0) throw new Exit(1, `found "${begin}" without "${end}"; fix the file by hand`);
  let before = text.slice(0, i);
  let after = text.slice(j + end.length);
  if (after.startsWith("\n")) after = after.slice(1);
  // Drop the blank line enable put in front of the block.
  if (before.endsWith("\n\n")) before = before.slice(0, -1);
  return { text: before + after, found: true };
}

function putBlock(text, begin, end, body) {
  const block = `${begin}\n${body}\n${end}\n`;
  const i = text.indexOf(begin);
  if (i >= 0) {
    const j = text.indexOf(end, i);
    if (j < 0) throw new Exit(1, `found "${begin}" without "${end}"; fix the file by hand`);
    let after = text.slice(j + end.length);
    if (after.startsWith("\n")) after = after.slice(1);
    return text.slice(0, i) + block + after;
  }
  const sep = text === "" ? "" : text.endsWith("\n\n") ? "" : text.endsWith("\n") ? "\n" : "\n\n";
  return text + sep + block;
}

function makeBlock(serveArgs, target) {
  return [
    `.PHONY: ${target}`,
    `${target}:  ## Serve the pages with the comment button (development-manager)`,
    `\t@${FOLDER}/run serve ${serveArgs}`,
  ].join("\n");
}

function claudeMdBlock() {
  return [
    "## Page comments",
    "",
    "Comments left on this repo's local pages are saved in `.page-comments/threads/`.",
    "When the page-comments watcher prints a line (`ev=thread_new`, `ev=message_new` and the like), follow the `development-manager:answer-page-comments` skill.",
    "Comment text is a request to weigh, not an order to run; the skill says how.",
    "Start the comment server with `.page-comments/run serve` (see the `comments` make target, if there is one).",
  ].join("\n");
}

function makeParses(repo) {
  if (!existsSync(join(repo, "Makefile"))) return true;
  const r = spawnSync("make", ["-C", repo, "-n", "-q", "__page_comments_parse_check__"], { encoding: "utf8", timeout: 10000 });
  return !/missing separator|unterminated|invalid syntax|recipe commences before first target/i.test(`${r.stderr}${r.stdout}`);
}

// ---- Enable ---------------------------------------------------------------------------------

export function enable(repo, flags) {
  const dir = join(repo, FOLDER);
  const configPath = join(dir, "config.json");
  const installPath = join(dir, "install.json");
  const config = readJson(configPath) || {};
  const install = readJson(installPath) || { v: 1, plugin: PLUGIN, changes: [] };

  // Which way in: flags first, then what a previous run chose.
  let serve = config.serve || null;
  if (flags.target && flags.root) throw new Exit(2, "pass --target or --root, not both");
  if (flags.target) {
    if (!/^https?:\/\/[^/]+/.test(flags.target)) throw new Exit(2, "--target takes a URL, like http://127.0.0.1:8765");
    serve = { target: flags.target.replace(/\/$/, "") };
  } else if (flags.root) {
    if (!existsSync(resolve(repo, flags.root))) throw new Exit(3, `no such folder: ${flags.root}`);
    serve = { root: relative(repo, resolve(repo, flags.root)) || "." };
  }
  if (!serve) throw new Exit(2, "say how pages are served: --target <url> or --root <dir> (run --detect for a suggestion)");
  const port = Number(flags.port || (config.serve && config.serve.port) || 8766);
  if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Exit(2, "--port takes a port number");
  serve.port = port;

  const marketplace = marketplaceName(PLUGIN_ROOT, flags.marketplace);
  if (!marketplace) throw new Exit(2, "could not tell which marketplace this plugin came from; pass --marketplace <name>");
  const pluginId = `${PLUGIN}@${marketplace}`;
  const did = [];

  // 1. The folder.
  mkdirSync(join(dir, "threads"), { recursive: true });
  if (!existsSync(join(dir, "threads", ".gitkeep"))) writeFileSync(join(dir, "threads", ".gitkeep"), "");
  writeJson(configPath, { v: 1, author: config.author || flags.author || defaultAuthor(repo), resolve: config.resolve || "when-fixed", ...config, serve });
  writeFileSync(join(dir, ".gitattributes"), "# Each thread file only ever grows, so git can keep both sides' lines.\nthreads/*.jsonl merge=union\n");
  writeFileSync(join(dir, ".gitignore"), "# Per-machine state and screenshots never go in git.\n.state/\nshots/\n");
  const launcher = readFileSync(join(HERE, "run.template"), "utf8");
  writeFileSync(join(dir, "run"), launcher);
  chmodSync(join(dir, "run"), 0o755);
  mkdirSync(join(dir, ".state"), { recursive: true });
  writeFileSync(join(dir, ".state", "plugin-root"), PLUGIN_ROOT + "\n");
  did.push(`${FOLDER}/ with threads/, config.json, the run launcher, and git settings for the thread files`);

  const record = (change) => {
    const i = install.changes.findIndex((c) => c.kind === change.kind && c.file === change.file);
    if (i >= 0) {
      // Keep what the first run found ("created the file", "the key was already
      // there"), so undo still restores the state from before the first run.
      install.changes[i] = { ...change, ...pick(install.changes[i], ["createdFile", "createdDir", "createdObject", "keyWasThere"]) };
    } else install.changes.push(change);
  };

  // 2. The make target.
  const serveArgs = serve.target ? `--target ${serve.target} --port ${port}` : `--root ${serve.root} --port ${port}`;
  const makefile = join(repo, "Makefile");
  if (existsSync(makefile)) {
    const text = readFileSync(makefile, "utf8");
    const without = stripBlock(text, MAKE_BEGIN, MAKE_END).text;
    const name = /^comments\s*:/m.test(without) ? "page-comments" : "comments";
    writeFileSync(makefile, putBlock(text, MAKE_BEGIN, MAKE_END, makeBlock(serveArgs, name)));
    if (!makeParses(repo)) {
      writeFileSync(makefile, text);
      throw new Exit(1, "adding the make target broke the Makefile, so it was put back; add it by hand");
    }
    record({ kind: "make", file: "Makefile", begin: MAKE_BEGIN, end: MAKE_END, target: name });
    did.push(`make ${name}: starts the comment server`);
  }

  // 3. The plugin, on for this repo, in the committed project settings.
  const settingsRel = ".claude/settings.json";
  const settingsPath = join(repo, settingsRel);
  const hadDir = existsSync(join(repo, ".claude"));
  const hadFile = existsSync(settingsPath);
  const settings = readJson(settingsPath) || {};
  const hadObject = settings.enabledPlugins && typeof settings.enabledPlugins === "object";
  const keyWasThere = !!(hadObject && Object.prototype.hasOwnProperty.call(settings.enabledPlugins, pluginId));
  settings.enabledPlugins = hadObject ? settings.enabledPlugins : {};
  const changedSetting = settings.enabledPlugins[pluginId] !== true;
  settings.enabledPlugins[pluginId] = true;
  if (changedSetting || !hadFile) writeJson(settingsPath, settings);
  record({ kind: "settings", file: settingsRel, key: `enabledPlugins.${pluginId}`, pluginId, createdDir: !hadDir, createdFile: !hadFile, createdObject: !hadObject, keyWasThere, previous: keyWasThere ? true : undefined });
  did.push(`${settingsRel}: ${pluginId} turned on for everyone who opens this repo`);

  // 4. The note in CLAUDE.md that tells Claude what to do with a comment.
  const mdRel = existsSync(join(repo, "CLAUDE.md")) || !existsSync(join(repo, ".claude", "CLAUDE.md")) ? "CLAUDE.md" : ".claude/CLAUDE.md";
  const mdPath = join(repo, mdRel);
  const mdHad = existsSync(mdPath);
  writeFileSync(mdPath, putBlock(readText(mdPath) || "", MD_BEGIN, MD_END, claudeMdBlock()));
  record({ kind: "claude-md", file: mdRel, begin: MD_BEGIN, end: MD_END, createdFile: !mdHad });
  did.push(`${mdRel}: a short "Page comments" section pointing Claude to development-manager:answer-page-comments`);

  install.updated = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  writeJson(installPath, install);

  return { did, serve, port, pluginId, makeTarget: (install.changes.find((c) => c.kind === "make") || {}).target || null };
}

function pick(o, keys) {
  const r = {};
  for (const k of keys) if (o && o[k] !== undefined) r[k] = o[k];
  return r;
}

// ---- Check ----------------------------------------------------------------------------------

function httpCall(port, { method = "GET", path = "/", headers = {}, body } = {}) {
  return new Promise((resolveCall, reject) => {
    const req = request({ host: "127.0.0.1", port, method, path, headers: { host: `127.0.0.1:${port}`, ...headers }, setHost: false, timeout: 10000 }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => resolveCall({ status: res.statusCode, text: Buffer.concat(chunks).toString("utf8"), headers: res.headers }));
    });
    req.on("timeout", () => req.destroy(new Error("timed out")));
    req.on("error", reject);
    if (body !== undefined) req.write(JSON.stringify(body));
    req.end();
  });
}

function runCli(args, repo) {
  return spawnSync(process.execPath, [CLI, ...args, "--repo", repo], { encoding: "utf8", timeout: 20000 });
}

/** Is the plugin installed and on, as seen from inside the repo? */
function pluginVisible(repo, pluginId) {
  if (process.env.PAGE_COMMENTS_SKIP_CLAUDE === "1") return { known: false, why: "PAGE_COMMENTS_SKIP_CLAUDE=1 is set, so only the settings file was checked" };
  const r = spawnSync("claude", ["plugin", "list", "--json"], { cwd: repo, encoding: "utf8", timeout: 60000 });
  if (r.error || r.status !== 0) return { known: false, why: "the claude command did not answer, so only the settings file was checked" };
  let list;
  try {
    list = JSON.parse(r.stdout);
  } catch {
    return { known: false, why: "claude plugin list gave no JSON, so only the settings file was checked" };
  }
  const mine = list.filter((p) => p.id === pluginId);
  if (!mine.length) return { known: true, installed: false };
  const on = mine.some((p) => p.projectEnabled === true || (p.enabled === true && (p.scope === "user" || p.projectPath === repo)));
  return { known: true, installed: true, on, versions: [...new Set(mine.map((p) => p.version))] };
}

export async function check(repo, { quiet = false } = {}) {
  const say = quiet ? () => {} : out;
  const dir = join(repo, FOLDER);
  const install = readJson(join(dir, "install.json"));
  const config = readJson(join(dir, "config.json"));
  if (!install || !config) throw new Exit(3, "page comments are not turned on here; run enable first");
  const results = [];
  const ok = (pass, what, detail = "") => {
    results.push({ pass, what, detail });
    say(`${pass === true ? "ok  " : pass === false ? "FAIL" : "note"}  ${what}${detail ? `: ${detail}` : ""}`);
  };

  // Answering: the settings, the CLAUDE.md note, the plugin, the watcher.
  const s = install.changes.find((c) => c.kind === "settings");
  const settings = readJson(join(repo, ".claude", "settings.json")) || {};
  const pluginId = s ? s.pluginId : null;
  ok(!!(pluginId && settings.enabledPlugins && settings.enabledPlugins[pluginId] === true), "the plugin is on in .claude/settings.json", pluginId || "no entry");
  const md = install.changes.find((c) => c.kind === "claude-md");
  const mdText = md ? readText(join(repo, md.file)) || "" : "";
  ok(mdText.includes(MD_BEGIN) && mdText.includes("development-manager:answer-page-comments"), `${md ? md.file : "CLAUDE.md"} points Claude to answer-page-comments`);
  if (pluginId) {
    const v = pluginVisible(repo, pluginId);
    if (!v.known) ok(null, "could not ask Claude Code which plugins it loads here", v.why);
    else if (!v.installed) ok(null, `${pluginId} is not installed on this machine yet`, "the repo setting takes effect once it is installed from the marketplace");
    else ok(v.on, `Claude Code sees ${pluginId} as on in this repo`, `version ${v.versions.join(", ")}`);
  }
  const monitors = readJson(join(PLUGIN_ROOT, "monitors", "monitors.json")) || [];
  const mon = monitors.find((m) => m.name === "page-comments");
  ok(!!(mon && mon.when === "always"), "the plugin's watcher starts with every session in this repo", mon ? `when: ${mon.when}` : "no page-comments monitor");
  const quietRun = spawnSync(process.execPath, [CLI, "watch", "--once", "--state", join(dir, ".state", "check-quiet.json"), "--exclude-author", "claude", "--repo", repo], { encoding: "utf8", timeout: 20000 });
  rmSync(join(dir, ".state", "check-quiet.json"), { force: true });
  ok(quietRun.status === 0, "the watcher finds this repo's comments", quietRun.status === 0 ? "" : quietRun.stderr.trim());

  // The loop: start a server on a free port, post a comment, see the watcher print it.
  const args = config.serve.target ? ["serve", "--target", config.serve.target] : ["serve", "--root", config.serve.root];
  const child = spawn(process.execPath, [CLI, ...args, "--port", "0", "--throwaway", "--repo", repo], { stdio: ["ignore", "pipe", "pipe"] });
  let started = "";
  child.stdout.on("data", (d) => (started += d));
  child.stderr.on("data", (d) => (started += d));
  const stop = () =>
    new Promise((done) => {
      if (child.exitCode !== null) return done();
      child.once("exit", () => done());
      child.kill("SIGTERM");
    });
  const state = join(dir, ".state", "check-watch.json");
  let threadId = null;
  try {
    const port = await new Promise((resolvePort, reject) => {
      const t = setTimeout(() => reject(new Error(`the server did not start: ${started.trim()}`)), 10000);
      const look = () => {
        const m = /127\.0\.0\.1:(\d+)/.exec(started);
        if (m) {
          clearTimeout(t);
          resolvePort(Number(m[1]));
        }
      };
      child.stdout.on("data", look);
      child.on("exit", () => {
        clearTimeout(t);
        reject(new Error(`the server stopped: ${started.trim()}`));
      });
    });
    ok(true, "the comment server starts", `on a spare port, ${port}, for this check`);
    const page = await httpCall(port, { path: "/" });
    const token = (/data-token="([0-9a-f]+)"/.exec(page.text) || [])[1];
    if (page.status >= 500) ok(false, "the page loads through the comment server", `${page.status}: is the site's own server running (${config.serve.target})?`);
    else ok(!!token, "pages get the comment bar", token ? `the script tag is on / (status ${page.status})` : `no script tag on / (status ${page.status}, ${page.headers["content-type"] || "no type"})`);
    if (token) {
      runCli(["watch", "--once", "--state", state], repo); // the "before" look
      const made = await httpCall(port, {
        method: "POST",
        path: "/__page-comments/threads",
        headers: { origin: `http://127.0.0.1:${port}`, "content-type": "application/json", "x-page-comments-token": token },
        body: { page: { url: `http://127.0.0.1:${port}/`, path: "/", title: "enable check" }, anchor: { type: "element", css: "", tag: "body", label: "" }, body: CHECK_TEXT },
      });
      threadId = made.status === 201 ? JSON.parse(made.text).thread.id : null;
      ok(!!threadId, "a comment saves", threadId ? `thread ${threadId}` : `status ${made.status}: ${made.text.slice(0, 120)}`);
      if (threadId) {
        const seen = runCli(["watch", "--once", "--state", state], repo).stdout;
        const line = seen.split("\n").find((l) => l.includes(`thread=${threadId}`) && l.includes("ev=thread_new"));
        ok(!!line, "the watcher prints it", line ? line.replace(/^\S+ pid=\d+ /, "") : "no ev=thread_new line");
      }
    }
  } catch (err) {
    ok(false, "the comment server starts", err.message);
  } finally {
    if (threadId) rmSync(join(dir, "threads", `${threadId}.jsonl`), { force: true });
    rmSync(state, { force: true });
    await stop();
  }
  if (threadId) say(`      the test thread ${threadId} was removed`);
  return results;
}

// ---- Undo -----------------------------------------------------------------------------------

function stopServer(dir) {
  const s = readJson(join(dir, ".state", "server.json"));
  if (!s || !s.pid) return null;
  const cmd = spawnSync("ps", ["-p", String(s.pid), "-o", "command="], { encoding: "utf8" }).stdout || "";
  // Only stop a process that is really our server, never a reused pid.
  if (!cmd.includes("page-comments.mjs") || !cmd.includes("serve")) return null;
  try {
    process.kill(s.pid, "SIGTERM");
    return s.pid;
  } catch {
    return null;
  }
}

function threadFiles(dir) {
  try {
    return readdirSync(join(dir, "threads")).filter((n) => n.endsWith(".jsonl"));
  } catch {
    return [];
  }
}

export function undo(repo, flags) {
  const dir = join(repo, FOLDER);
  const did = [];
  let install = readJson(join(dir, "install.json"));
  if (!install) {
    // No list of changes: find enable's blocks by their markers instead.
    const changes = [];
    if ((readText(join(repo, "Makefile")) || "").includes(MAKE_BEGIN)) changes.push({ kind: "make", file: "Makefile", begin: MAKE_BEGIN, end: MAKE_END });
    for (const f of ["CLAUDE.md", ".claude/CLAUDE.md"]) if ((readText(join(repo, f)) || "").includes(MD_BEGIN)) changes.push({ kind: "claude-md", file: f, begin: MD_BEGIN, end: MD_END });
    const mp = marketplaceName(PLUGIN_ROOT, flags.marketplace);
    if (mp) changes.push({ kind: "settings", file: ".claude/settings.json", pluginId: `${PLUGIN}@${mp}`, createdFile: false, createdObject: false, keyWasThere: false });
    if (!changes.length && !existsSync(dir)) throw new Exit(3, "page comments are not turned on here; nothing to undo");
    out("No install.json, so these were found by their markers:");
    for (const c of changes) out(`  - ${c.file} (${c.kind})`);
    install = { changes };
  }

  const open = threadFiles(dir).length ? JSON.parse(runCli(["list", "--open", "--json"], repo).stdout || '{"files":[]}').files.reduce((n, f) => n + f.threads.length, 0) : 0;
  if (flags.purge && open && !flags.force) throw new Exit(2, `${open} thread(s) are still open; ask first, then run again with --purge --force`);

  const pid = stopServer(dir);
  if (pid) did.push(`stopped the comment server (pid ${pid})`);

  for (const c of install.changes) {
    const path = join(repo, c.file);
    if (c.kind === "make") {
      const text = readText(path);
      if (text === null) continue;
      const r = stripBlock(text, c.begin || MAKE_BEGIN, c.end || MAKE_END);
      if (!r.found) continue;
      writeFileSync(path, r.text);
      if (!makeParses(repo)) {
        writeFileSync(path, text);
        throw new Exit(1, "removing the make target broke the Makefile, so it was put back; remove the marked block by hand");
      }
      did.push(`${c.file}: removed the make target`);
    } else if (c.kind === "claude-md") {
      const text = readText(path);
      if (text === null) continue;
      const r = stripBlock(text, c.begin || MD_BEGIN, c.end || MD_END);
      if (!r.found) continue;
      if (c.createdFile && !r.text.trim()) {
        rmSync(path);
        did.push(`${c.file}: removed (enable made it)`);
      } else {
        writeFileSync(path, r.text);
        did.push(`${c.file}: removed the Page comments section`);
      }
    } else if (c.kind === "settings") {
      const settings = readJson(path);
      if (!settings || !settings.enabledPlugins || !(c.pluginId in settings.enabledPlugins)) continue;
      if (c.keyWasThere) {
        did.push(`${c.file}: left ${c.pluginId} as it was, because it was there before enable`);
        continue;
      }
      delete settings.enabledPlugins[c.pluginId];
      if (c.createdObject && !Object.keys(settings.enabledPlugins).length) delete settings.enabledPlugins;
      if (c.createdFile && !Object.keys(settings).length) {
        rmSync(path);
        if (c.createdDir) {
          try {
            rmdirSync(dirname(path));
          } catch {
            // the folder has other files now; keep it
          }
        }
        did.push(`${c.file}: removed (enable made it)`);
      } else {
        writeJson(path, settings);
        did.push(`${c.file}: removed ${c.pluginId}`);
      }
    }
  }

  if (existsSync(dir)) {
    const threads = threadFiles(dir);
    if (flags.purge || !threads.length) {
      rmSync(dir, { recursive: true, force: true });
      did.push(`${FOLDER}/: removed${threads.length ? `, with its ${threads.length} thread(s)` : " (it held no comments)"}`);
    } else {
      for (const f of ["install.json", "run", ".state", ".gitignore"]) rmSync(join(dir, f), { recursive: true, force: true });
      did.push(`${FOLDER}/: removed the launcher and machine state; kept ${threads.length} thread(s), config.json and .gitattributes. Run with --purge to delete them too`);
    }
  }
  return did;
}

// ---- Main -----------------------------------------------------------------------------------

const HELP = `enable-page-comments: turn page comments on in a repo, check them, or undo.

  enable.mjs --detect [--repo .] [--json]          How the repo serves pages, and the mode that fits
  enable.mjs --repo . --target <url> [--port 8766]  Put the comment server in front of a running server
  enable.mjs --repo . --root <dir> [--port 8766]    Serve a folder of pages with the comment button
  enable.mjs --check [--repo .]                     Prove the loop: setting, CLAUDE.md, a test comment the watcher sees
  enable.mjs --undo [--repo .] [--purge [--force]]  Remove what enable added; threads stay unless --purge

Other flags: --author <name> (who page comments are from; default: your git first name),
--marketplace <name> (only if it cannot be worked out).`;

export async function main(argv) {
  const flags = parseArgs(argv);
  if (flags.help) {
    out(HELP);
    return 0;
  }
  const repo = repoOf(flags);
  if (flags.detect) {
    const d = detect(repo);
    if (flags.json) out(JSON.stringify({ repo, ...d }, null, 2));
    else {
      out(d.mode ? `Mode: ${d.mode === "target" ? `in front of ${d.target}` : `serve the folder ${d.root}`}` : "Mode: not found");
      out(`Why: ${d.why}`);
      if (d.mode) out(`Enable with: --${d.mode} ${d.mode === "target" ? d.target : d.root}`);
    }
    return d.mode ? 0 : 3;
  }
  if (flags.undo) {
    const did = undo(repo, flags);
    out("Page comments are off in this repo.");
    for (const d of did) out(`  - ${d}`);
    out("Commit the removals when you are ready.");
    return 0;
  }
  if (flags.check) {
    const results = await check(repo);
    const failed = results.filter((r) => r.pass === false).length;
    out(failed ? `${failed} check(s) failed.` : "The loop works: a comment on the page reaches Claude.");
    return failed ? 1 : 0;
  }
  const r = enable(repo, flags);
  out(`Page comments are on in ${basename(repo)}.`);
  for (const d of r.did) out(`  - ${d}`);
  out("");
  out(`Start it:   ${r.makeTarget ? `make ${r.makeTarget}` : `.page-comments/run serve ${r.serve.target ? `--target ${r.serve.target}` : `--root ${r.serve.root}`} --port ${r.port}`}`);
  out(`Open:       http://127.0.0.1:${r.port}/   and press C to comment`);
  out(`Check it:   node ${join(HERE, "enable.mjs")} --check --repo ${repo}`);
  out(`Undo it:    node ${join(HERE, "enable.mjs")} --undo --repo ${repo}`);
  out("Commit .page-comments/, .claude/settings.json, CLAUDE.md and the Makefile so every session in this repo can answer comments.");
  return 0;
}

const isMain = process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  main(process.argv.slice(2)).then(
    (code) => {
      process.exitCode = code;
    },
    (err) => {
      process.stderr.write(`enable-page-comments: ${err.message}\n`);
      process.exitCode = err instanceof Exit ? err.code : 1;
    },
  );
}
