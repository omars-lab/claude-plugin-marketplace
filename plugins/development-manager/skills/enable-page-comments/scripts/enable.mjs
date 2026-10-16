#!/usr/bin/env node
// enable-page-comments: turn page comments on in a repo, check the whole loop
// works, or take it all out again. Node 18, no dependencies.
//
//   enable.mjs --detect [--repo .] [--json]
//   enable.mjs --repo . (--target <url> | --root <dir>) [--port <first free from 8766>] [--shots-dir <path>]
//   enable.mjs --check [--repo .]
//   enable.mjs --undo [--repo .] [--purge [--force]]
//   enable.mjs --phone [--repo .] [--target <url> | --root <dir>] [--port 8766]
//   enable.mjs --phone --undo [--repo .]
//   enable.mjs --vite [--repo .] [--vite-config <file>]
//   enable.mjs --vite --undo [--repo .]
//   enable.mjs --userscript --origin <url> [--origin <url>]... [--repo .]
//   enable.mjs --userscript --undo [--repo .]
//
// Enabling writes into the target repo, and every change outside
// `.page-comments/` is listed in `.page-comments/install.json`, so --undo
// removes exactly that and nothing else:
//   - `.page-comments/` with threads/, config.json, .gitattributes, .gitignore
//     and the `run` launcher. config.json names the folder for screenshots
//     (`shotsDir`, written with ~): --shots-dir, else the global config, else
//     the design default in iCloud Drive;
//   - a make target between `# page-comments:begin` / `# page-comments:end`;
//   - the plugin turned on in the repo's committed `.claude/settings.json`, so
//     every session opened in the repo has the answering skill and the watcher;
//   - a marked block in the repo's CLAUDE.md that says to follow
//     `development-manager:answer-page-comments` when the watcher prints a comment;
//   - a post-commit git hook that notes which commit landed the uncommitted work a
//     comment was made on (`page-comments restamp`). It goes where git looks for
//     hooks, which follows core.hooksPath. A post-commit hook already there is
//     renamed to `post-commit.page-comments-prev` and run first by ours, and undo
//     renames it back, byte for byte. It is skipped, with a note, when hooks are
//     off, or when the hooks folder is shared outside the repo or committed in it;
//   - with --phone, one `tailscale serve` entry (https on the comment server's port) and
//     a `phone` block in config.json with the Mac's tailnet name and the allowed logins.
//     Undo turns off that one entry only;
//   - with --vite (phase 5), `.page-comments/vite.mjs` and two marked edits to the
//     repo's vite.config (an import line and `pageComments(), ` in `plugins: [`),
//     or a new vite.config.mjs when there is none. A config it cannot edit safely
//     (no `plugins: [`, more than one, or CommonJS) is left alone, with what to add;
//   - with --userscript (phase 5), the page origins in config.json's
//     `userscript.origins`, the repo token in `.state/token` and the Tampermonkey
//     script in `.state/page-comments.user.js`. Both files are in `.state/`, which
//     git ignores, because the script carries the token.
//
// Undo never deletes a screenshot: not in the iCloud folder, and not in
// `.page-comments/shots/`, which stays with the .gitignore that keeps it out of git.
//
// Ports: several repos on one Mac each run a site and a comment server, so a
// fixed port can be another repo's. Detect reads the port from the serve
// command (`PORT ?= n` included) and, through lsof, who listens there; enable
// takes the first free comment port from 8766 when none is given or saved, and
// warns about a busy one; check fails on a port held by another repo's server.
//
// Exit codes: 0 ok, 1 a check failed, 2 bad usage, 3 not found.

import { execFileSync, spawn, spawnSync } from "node:child_process";
import { chmodSync, existsSync, mkdirSync, readdirSync, readFileSync, realpathSync, renameSync, rmSync, rmdirSync, statSync, writeFileSync } from "node:fs";
import { request } from "node:http";
import { basename, dirname, isAbsolute, join, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { contractHome, expandHome, shotsSetting, shotTarget } from "../../../shared/scripts/lib/shots.mjs";
import { cleanOrigin, tokenPath, userscriptOrigins, userscriptPath, writeUserscript } from "../../../shared/scripts/lib/userscript.mjs";
import { firstFreePort, isCommentServer, listeners, ownerText, portFree, portOwner, whose } from "../../../shared/scripts/lib/ports.mjs";

const HERE = dirname(fileURLToPath(import.meta.url));
export const PLUGIN_ROOT = resolve(HERE, "..", "..", "..");
const CLI = join(PLUGIN_ROOT, "shared", "scripts", "page-comments.mjs");
const PLUGIN = "development-manager";
const FOLDER = ".page-comments";
const MAKE_BEGIN = "# page-comments:begin";
const MAKE_END = "# page-comments:end";
const MD_BEGIN = "<!-- page-comments:begin -->";
const MD_END = "<!-- page-comments:end -->";
const PRIVACY =
  "Screenshots go to iCloud Drive. Apple's servers keep a copy of everything there, which Apple can read unless Advanced Data Protection is on.";
const HOOK_MARK = "# page-comments:post-commit";
const HOOK_PREV = "post-commit.page-comments-prev";
const VITE_NAMES = ["vite.config.js", "vite.config.mjs", "vite.config.ts", "vite.config.mts"];
const VITE_MARK = "// page-comments";
const VITE_CALL = "pageComments(), ";
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
  const values = new Set(["repo", "target", "root", "port", "marketplace", "author", "plugin-root", "shots-dir", "vite-config", "origin"]);
  const bools = new Set(["detect", "check", "undo", "purge", "force", "json", "help", "phone", "vite", "userscript"]);
  const flags = { origin: [] };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a.startsWith("--") && /funnel/i.test(a)) throw new Exit(2, NO_FUNNEL);
    if (!a.startsWith("--")) throw new Exit(2, `unexpected argument: ${a}`);
    let [name, value] = a.slice(2).split(/=(.*)/s);
    if (bools.has(name)) flags[name] = true;
    else if (values.has(name)) {
      if (value === undefined) value = argv[++i];
      if (value === undefined) throw new Exit(2, `--${name} needs a value`);
      if (name === "origin") flags.origin.push(value);
      else flags[name] = value;
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

function gitOut(repo, args) {
  try {
    return execFileSync("git", ["-C", repo, ...args], { encoding: "utf8", timeout: 5000, stdio: ["ignore", "pipe", "ignore"] }).trim();
  } catch {
    return null;
  }
}

function real(p) {
  try {
    return realpathSync(p);
  } catch {
    return resolve(p);
  }
}

function inside(child, parent) {
  const r = relative(real(parent), real(child));
  return r === "" || (!r.startsWith("..") && !isAbsolute(r));
}

/**
 * Where the post-commit hook goes, or why it cannot: git's own answer for the
 * hooks folder, so core.hooksPath (and a worktree's shared hooks) are followed.
 * Returns { dir, hook, prev } or { skip: "<why>" }.
 */
export function hookPlace(repo) {
  const common = gitOut(repo, ["rev-parse", "--path-format=absolute", "--git-common-dir"]);
  if (!common) return { skip: "this folder is not a git repo" };
  const dir = gitOut(repo, ["rev-parse", "--path-format=absolute", "--git-path", "hooks"]);
  if (!dir || dir === "/dev/null") return { skip: "git hooks are turned off here (core.hooksPath is /dev/null)" };
  const hook = join(dir, "post-commit");
  const prev = join(dir, HOOK_PREV);
  if (inside(dir, common)) return { dir, hook, prev };
  if (inside(dir, repo)) {
    // A hooks folder in the work tree is usually committed for the whole team.
    // A file added there would show as a change in git, and every comment would
    // then be stamped "with uncommitted changes". Only an ignored path is safe.
    const rel = relative(real(repo), join(real(dir), "post-commit"));
    if (gitOut(repo, ["check-ignore", "-q", "--no-index", rel]) !== null) return { dir, hook, prev };
    return { skip: `core.hooksPath points at ${relative(real(repo), real(dir)) || "."}/, a folder in the repo, so a hook added there would show up in git` };
  }
  return { skip: "core.hooksPath points at a hooks folder outside this repo, shared with other repos" };
}

/** Is our hook in place? */
function ourHook(path) {
  return (readText(path) || "").includes(HOOK_MARK);
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
/** The port a Makefile recipe serves on: a number, `$(or $(VAR),N)`, or `$(VAR)` with `VAR ?= N`. */
export function makePort(make, recipe) {
  const or = /\$\(or \$\((\w+)\),(\d+)\)/.exec(recipe);
  if (or) return or[2];
  const plain = /--port[ =](\d{2,5})\b/.exec(recipe) || /:(\d{4,5})\b/.exec(recipe);
  if (plain) return plain[1];
  // A make variable: --port $(PORT), :$(PORT), or a bare $(PORT) after a server.
  const v = /(?:--port[ =]|:)\$[({](\w+)[)}]/.exec(recipe) || /\$[({](\w*PORT\w*)[)}]/.exec(recipe);
  if (v) {
    const def = new RegExp(`^(?:export\\s+|override\\s+)?${v[1]}\\s*(?:\\?|:|::)?=\\s*(\\d{2,5})\\s*$`, "m").exec(make);
    if (def) return def[1];
  }
  return null;
}

// Words in a serve command that name the server: a script file, or a known tool.
function serverWords(cmd) {
  return [...new Set(cmd.match(/[\w.-]+\.(?:py|js|mjs|cjs|ts|rb)\b|\b(?:vite|next|astro|nuxt|hugo|jekyll|eleventy|http\.server|http-server|live-server|serve)\b/g) || [])];
}

/**
 * Look at what is running before trusting the port read from the files. Several
 * repos on one Mac often share a default port, so the port can belong to another
 * repo's server, and this repo's server may be running on another port.
 * Adds `running` to the result and says what it found in `why`.
 */
function withRunning(repo, d, cmd) {
  const port = Number(new URL(d.target).port) || null;
  const owner = port ? portOwner(port) : { known: false };
  if (!owner.known) return d;
  const words = serverWords(cmd || "");
  // This repo's own server, running now on some port, found by its command.
  const mine = words.length
    ? listeners().filter((l) => !isCommentServer(l) && words.some((w) => (l.command || "").includes(w)) && ["same", "worktree"].includes(whose(l, repo).rel))
    : [];
  const w = owner.busy ? whose(owner, repo) : null;
  d.running = { port, busy: !!owner.busy, owner: owner.busy ? ownerText(owner) : null, from: w ? w.rel : null, mine: mine.map((l) => l.port) };
  const elsewhere = mine.filter((l) => l.port !== port);
  if (owner.busy && w.rel === "other") {
    if (elsewhere.length) {
      const alt = elsewhere[0];
      d.why += ` Right now port ${port} is held by another repo's server, ${ownerText(owner)}. This repo's server is running on port ${alt.port} (${ownerText(alt)}), so the target is that port. If it later runs on ${port} again, run enable again with --target.`;
      d.target = `http://127.0.0.1:${alt.port}`;
    } else {
      d.why += ` Careful: right now port ${port} is held by another repo's server, ${ownerText(owner)}. Pages through the comment server would be that repo's. Start this repo's server on a free port and pass it with --target.`;
      d.warning = `port ${port} belongs to another repo right now`;
    }
  } else if (owner.busy && (w.rel === "same" || w.rel === "worktree")) {
    d.why += ` It is running now${w.rel === "worktree" ? `, from another checkout of this repo (${w.where})` : ""}.`;
  } else if (!owner.busy && elsewhere.length) {
    d.why += ` Right now this repo's server is running on port ${elsewhere[0].port} instead (${ownerText(elsewhere[0])}). Use --target http://127.0.0.1:${elsewhere[0].port} while it runs there.`;
  }
  return d;
}

export function detect(repo) {
  const make = readText(join(repo, "Makefile"));
  if (make) {
    const m = /^(serve|dev|start|preview)\s*:[^\n]*\n((?:\t[^\n]*\n?)+)/m.exec(make);
    if (m) {
      const port = makePort(make, m[2]);
      return withRunning(repo, {
        mode: "target",
        target: `http://127.0.0.1:${port || "8000"}`,
        how: `make ${m[1]}`,
        why: port
          ? `The Makefile's \`${m[1]}\` target runs a server on port ${port}. The comment server sits in front of it, so the site's own API keeps working.`
          : `The Makefile's \`${m[1]}\` target runs a server, but its port could not be read, so 8000 is a guess. Check the port it prints. The comment server sits in front of it.`,
      }, m[2]);
    }
  }
  const pkg = readJson(join(repo, "package.json"));
  const scripts = (pkg && pkg.scripts) || {};
  for (const name of ["dev", "start", "serve", "preview"]) {
    const s = scripts[name];
    if (!s) continue;
    const port = (/--port[ =](\d{2,5})/.exec(s) || [])[1] || (/\bvite\b/.test(s) ? (name === "preview" ? "4173" : "5173") : /next\b/.test(s) ? "3000" : /astro\b/.test(s) ? "4321" : "3000");
    return withRunning(repo, {
      mode: "target",
      target: `http://127.0.0.1:${port}`,
      how: `npm run ${name}`,
      why: `package.json's \`${name}\` script runs a dev server, most likely on port ${port}. Check the port it prints. The comment server sits in front of it.`,
    }, s);
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
  // Where screenshots go: --shots-dir, else what this repo already has, else the
  // global config or the design default. Stored with ~ so it never names the person.
  let shotsDir = config.shotsDir;
  if (flags["shots-dir"]) shotsDir = contractHome(resolve(expandHome(flags["shots-dir"])));
  else if (typeof shotsDir !== "string" || !shotsDir.trim()) shotsDir = shotsSetting(null).dir;
  const shotsChanged = shotsDir !== config.shotsDir;
  writeJson(configPath, { v: 1, author: config.author || flags.author || defaultAuthor(repo), resolve: config.resolve || "when-fixed", ...config, serve, shotsDir });
  writeFileSync(join(dir, ".gitattributes"), "# Each thread file only ever grows, so git can keep both sides' lines.\nthreads/*.jsonl merge=union\n");
  writeFileSync(join(dir, ".gitignore"), "# Per-machine state and screenshots never go in git.\n.state/\nshots/\n");
  const launcher = readFileSync(join(HERE, "run.template"), "utf8");
  writeFileSync(join(dir, "run"), launcher);
  chmodSync(join(dir, "run"), 0o755);
  mkdirSync(join(dir, ".state"), { recursive: true });
  writeFileSync(join(dir, ".state", "plugin-root"), PLUGIN_ROOT + "\n");
  did.push(`${FOLDER}/ with threads/, config.json, the run launcher, and git settings for the thread files`);
  const shots = shotTarget({ repo, dir });
  did.push(
    shots.kind === "icloud"
      ? `screenshots go to ${contractHome(shots.base)}/ (iCloud Drive)`
      : `screenshots go to ${FOLDER}/shots/, which git ignores (${shots.reason})`,
  );

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

  // 5. The post-commit hook (phase 4): which commit landed the work a comment was made on.
  const place = hookPlace(repo);
  if (place.skip) {
    did.push(`no post-commit hook: ${place.skip}. Comments still work; they just are not linked to the commit that lands the work`);
  } else if (ourHook(place.hook)) {
    did.push("the post-commit hook was already in place");
  } else if (existsSync(place.prev)) {
    did.push(`no post-commit hook: ${HOOK_PREV} is already in the hooks folder, so the hook there now could not be kept safely`);
  } else {
    const hadPrevious = existsSync(place.hook);
    let prevMode;
    if (hadPrevious) {
      prevMode = statSync(place.hook).mode & 0o7777;
      renameSync(place.hook, place.prev);
    }
    mkdirSync(place.dir, { recursive: true });
    writeFileSync(place.hook, readFileSync(join(HERE, "post-commit.template"), "utf8"));
    chmodSync(place.hook, 0o755);
    const rel = (p) => relative(repo, p).split("\\").join("/");
    install.changes = install.changes.filter((c) => c.kind !== "post-commit-hook");
    install.changes.push({ kind: "post-commit-hook", file: rel(place.hook), prev: rel(place.prev), hadPrevious, prevMode });
    did.push(
      hadPrevious
        ? "a post-commit hook that notes which commit landed a comment's work; the post-commit hook already there still runs first"
        : "a post-commit hook that notes which commit landed a comment's work",
    );
  }

  install.updated = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  writeJson(installPath, install);

  return {
    did,
    serve,
    port,
    pluginId,
    makeTarget: (install.changes.find((c) => c.kind === "make") || {}).target || null,
    privacy: shotsChanged && shots.kind === "icloud" ? PRIVACY : null,
  };
}

function pick(o, keys) {
  const r = {};
  for (const k of keys) if (o && o[k] !== undefined) r[k] = o[k];
  return r;
}

// ---- The phone, through Tailscale -----------------------------------------------------------
//
// `--phone` turns on one `tailscale serve` entry: https on the comment server's own port,
// proxied to 127.0.0.1:<port>. Its own port, so the tailnet name's 443 (often in use for
// something else) is never touched. Never Funnel: that would put the pages on the open
// internet. Never `serve reset`: only the one entry enable added is ever turned off.

const TAILSCALE_APP = "/Applications/Tailscale.app/Contents/MacOS/Tailscale";
const NO_FUNNEL = "Tailscale Funnel would put the pages on the open internet; page comments never use it";

/**
 * Tailscale's command line: PAGE_COMMENTS_TAILSCALE, then PATH, then the Mac app. When
 * the variable is set, nothing else is looked at, so tests never reach the real one.
 */
export function findTailscale(env = process.env) {
  if (env.PAGE_COMMENTS_TAILSCALE !== undefined) return existsSync(env.PAGE_COMMENTS_TAILSCALE) ? env.PAGE_COMMENTS_TAILSCALE : null;
  for (const d of (env.PATH || "").split(":")) if (d && existsSync(join(d, "tailscale"))) return join(d, "tailscale");
  return existsSync(TAILSCALE_APP) ? TAILSCALE_APP : null;
}

function tailscale(cli, args) {
  if (args.some((a) => /funnel/i.test(a))) throw new Exit(2, NO_FUNNEL);
  // No --yes and no stdin: if Tailscale wants to ask something, it fails instead of waiting.
  const r = spawnSync(cli, args, { encoding: "utf8", stdio: ["ignore", "pipe", "pipe"], timeout: 30000 });
  if (r.error) throw new Exit(1, `could not run ${cli} ${args.join(" ")}: ${r.error.message}`);
  return r;
}

function tailscaleJson(cli, args) {
  const r = tailscale(cli, args);
  if (r.status !== 0) throw new Exit(1, `tailscale ${args.join(" ")} failed: ${(r.stderr || r.stdout).trim()}`);
  try {
    return JSON.parse(r.stdout.trim() || "{}");
  } catch {
    throw new Exit(1, `tailscale ${args.join(" ")} did not give JSON`);
  }
}

/**
 * What `tailscale serve status --json` has on <host>:<port>:
 * "none", "ours" (exactly / proxied to target, over https), or "taken" (anything else).
 */
export function servedAt(status, host, port, target) {
  const s = status || {};
  const key = `${host}:${port}`.toLowerCase();
  const funnel = Object.keys(s.AllowFunnel || {}).find((k) => k.toLowerCase() === key && s.AllowFunnel[k]);
  if (funnel) return { state: "taken", detail: "Funnel is on for it" };
  const tcp = (s.TCP || {})[String(port)];
  const webKey = Object.keys(s.Web || {}).find((k) => k.toLowerCase() === key);
  const web = webKey ? s.Web[webKey] : null;
  if (!tcp && !web) {
    const other = Object.keys(s.Web || {}).find((k) => k.endsWith(`:${port}`));
    return other ? { state: "taken", detail: `served for ${other}` } : { state: "none" };
  }
  if (!web) return { state: "taken", detail: tcp.TCPForward ? `a TCP forward to ${tcp.TCPForward}` : "a TCP entry" };
  const handlers = web.Handlers || {};
  const paths = Object.keys(handlers);
  if (tcp && tcp.HTTPS && paths.length === 1 && paths[0] === "/" && handlers["/"].Proxy === target) return { state: "ours" };
  const what = (h) => h.Proxy || h.Path || (h.Text !== undefined ? "some text" : "something");
  return { state: "taken", detail: paths.map((p) => `${p} -> ${what(handlers[p])}`).join(", ") || "an empty web entry" };
}

const serveOn = (port, target) => ["serve", "--bg", `--https=${port}`, target];
const serveOff = (port) => ["serve", `--https=${port}`, "off"];

export function enablePhone(repo) {
  const dir = join(repo, FOLDER);
  const configPath = join(dir, "config.json");
  const installPath = join(dir, "install.json");
  const config = readJson(configPath);
  const install = readJson(installPath);
  if (!config || !install || !config.serve) throw new Exit(3, "page comments are not turned on here; run enable with --target or --root first, or add one of them to this --phone run");
  const port = Number(config.serve.port || 8766);
  const target = `http://127.0.0.1:${port}`;

  const cli = findTailscale();
  if (!cli) throw new Exit(3, `Tailscale's command line was not found on PATH or at ${TAILSCALE_APP}. Install Tailscale and sign in, then run this again`);
  const st = tailscaleJson(cli, ["status", "--json"]);
  if (st.BackendState !== "Running") throw new Exit(1, `Tailscale is not connected (it says ${st.BackendState || "nothing"}); open it and sign in, then run this again`);
  const self = st.Self || {};
  const host = String(self.DNSName || "")
    .replace(/\.$/, "")
    .toLowerCase();
  if (!host) throw new Exit(1, "Tailscale did not give this Mac's name; turn on MagicDNS for the tailnet, then run this again");
  const login = String(((st.User || {})[String(self.UserID)] || {}).LoginName || "").toLowerCase();
  if (!login) throw new Exit(1, "Tailscale did not say who is signed in on this Mac");
  if (!(st.CertDomains || []).map((d) => String(d).toLowerCase()).includes(host)) {
    throw new Exit(1, "HTTPS certificates are off for this tailnet, so the phone could not open the page. Turn on HTTPS Certificates on the DNS page of the Tailscale admin console, then run this again");
  }

  const earlier = install.changes.find((c) => c.kind === "tailscale-serve");
  if (earlier && (earlier.port !== port || earlier.host !== host)) {
    throw new Exit(1, `the phone is already on for ${earlier.host}:${earlier.port}; run --phone --undo first, then this again`);
  }
  const before = servedAt(tailscaleJson(cli, ["serve", "status", "--json"]), host, port, target);
  if (before.state === "taken") {
    throw new Exit(1, `Tailscale already serves something else on https port ${port} (${before.detail}). It was left alone; pick another port with --port, or turn that entry off yourself`);
  }
  const did = [];
  let added = !!(earlier && earlier.added);
  if (before.state === "none") {
    const r = tailscale(cli, serveOn(port, target));
    if (r.status !== 0) throw new Exit(1, `tailscale ${serveOn(port, target).join(" ")} failed: ${(r.stderr || r.stdout).trim()}`);
    added = true;
    const after = servedAt(tailscaleJson(cli, ["serve", "status", "--json"]), host, port, target);
    if (after.state !== "ours") throw new Exit(1, `tailscale serve ran, but port ${port} does not point at the comment server (${after.detail || "nothing there"}); turn it off with: tailscale ${serveOff(port).join(" ")}`);
    did.push(`Tailscale: https port ${port} on this Mac's tailnet name now goes to the comment server (tailscale ${serveOn(port, target).join(" ")})`);
  } else {
    did.push(`Tailscale: https port ${port} already went to the comment server${added ? "" : "; it was there before enable, so undo leaves it on"}`);
  }

  // The allow list starts with whoever is signed in on this Mac; the author for a login
  // is the repo's author unless `authors` in config.json says otherwise.
  const prev = config.phone && typeof config.phone === "object" ? config.phone : {};
  const logins = [...new Set((Array.isArray(prev.logins) ? prev.logins : []).map((l) => String(l).toLowerCase()).concat(login))];
  config.phone = { ...prev, host, port, logins };
  writeJson(configPath, config);
  did.push(`${FOLDER}/config.json: the phone setting, allowing ${logins.join(", ")}`);

  const change = { kind: "tailscale-serve", host, port, target, added, on: serveOn(port, target), off: serveOff(port) };
  install.changes = install.changes.filter((c) => c.kind !== "tailscale-serve").concat(change);
  install.updated = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
  writeJson(installPath, install);

  return {
    did,
    url: port === 443 ? `https://${host}/` : `https://${host}:${port}/`,
    port,
    login,
    author: config.author,
    off: `tailscale ${serveOff(port).join(" ")}`,
  };
}

/** Turn the phone off: the one serve entry enable added, and the phone setting. */
export function undoPhone(repo) {
  const dir = join(repo, FOLDER);
  const installPath = join(dir, "install.json");
  const configPath = join(dir, "config.json");
  const did = [];
  const install = readJson(installPath);
  const change = install && Array.isArray(install.changes) ? install.changes.find((c) => c.kind === "tailscale-serve") : null;
  if (change) {
    // Built from the port, not read from the file, so an edited install.json cannot run
    // anything but this one "off".
    const port = Number(change.port);
    if (!Number.isInteger(port) || port < 1 || port > 65535) throw new Exit(1, "install.json's tailscale-serve entry has no usable port; turn it off by hand");
    const manual = `tailscale ${serveOff(port).join(" ")}`;
    if (!change.added) did.push(`Tailscale: left https port ${port} on, because it was there before enable`);
    else {
      const cli = findTailscale();
      if (!cli) did.push(`Tailscale's command line was not found, so https port ${port} is still on; turn it off with: ${manual}`);
      else {
        const now = servedAt(tailscaleJson(cli, ["serve", "status", "--json"]), change.host, port, change.target || `http://127.0.0.1:${port}`);
        if (now.state === "ours") {
          const r = tailscale(cli, serveOff(port));
          if (r.status !== 0) throw new Exit(1, `${manual} failed: ${(r.stderr || r.stdout).trim()}`);
          did.push(`Tailscale: turned off https port ${port} (${manual}); nothing else was touched`);
        } else if (now.state === "none") did.push(`Tailscale: https port ${port} was already off`);
        else did.push(`Tailscale: https port ${port} now serves something else (${now.detail}), so it was left alone`);
      }
    }
    install.changes = install.changes.filter((c) => c !== change);
    writeJson(installPath, install);
  }
  const config = readJson(configPath);
  if (config && config.phone) {
    delete config.phone;
    writeJson(configPath, config);
    did.push(`${FOLDER}/config.json: removed the phone setting`);
  }
  return did;
}

// ---- The Vite plugin (phase 5) -------------------------------------------------------------
//
// vite.config imports `.page-comments/vite.mjs`, a small tracked file that finds the
// installed plugin (as `run` does) and loads its shared/scripts/vite.mjs. The plugin
// is dev-only: Vite's build and preview never run it.

/** The vite.config enable makes when the repo has none. */
function newViteConfig(importLine) {
  return `${importLine}\n\n// Made by enable-page-comments --vite; add your own settings here.\nexport default {\n  plugins: [${VITE_CALL}],\n};\n`;
}

function viteHowTo(importPath) {
  return `add these two lines by hand: \`import pageComments from "${importPath}";\` at the top, and \`pageComments(),\` first in \`plugins: [ … ]\``;
}

export function enableVite(repo, flags = {}) {
  const dir = join(repo, FOLDER);
  const installPath = join(dir, "install.json");
  const install = readJson(installPath);
  if (!install || !existsSync(join(dir, "config.json"))) throw new Exit(3, "page comments are not turned on here; run enable with --target or --root first, or add one of them to this --vite run");
  writeFileSync(join(dir, "vite.mjs"), readFileSync(join(HERE, "vite.template"), "utf8"));
  mkdirSync(join(dir, ".state"), { recursive: true });
  writeFileSync(join(dir, ".state", "plugin-root"), PLUGIN_ROOT + "\n");
  const did = [`${FOLDER}/vite.mjs: loads the plugin's dev-only Vite plugin (commit it with the config)`];

  let file = flags["vite-config"] ? resolve(repo, flags["vite-config"]) : VITE_NAMES.map((n) => join(repo, n)).find((f) => existsSync(f));
  if (flags["vite-config"] && !existsSync(file)) throw new Exit(3, `no such file: ${flags["vite-config"]}`);
  const created = !file;
  if (created) file = join(repo, "vite.config.mjs");
  const rel = relative(repo, file).split("\\").join("/");
  let importPath = relative(dirname(file), join(dir, "vite.mjs")).split("\\").join("/");
  if (!importPath.startsWith("../")) importPath = `./${importPath}`; // `.page-comments/…` alone would be a package name
  const importLine = `import pageComments from "${importPath}"; ${VITE_MARK}`;
  const record = (change) => {
    install.changes = install.changes.filter((c) => c.kind !== "vite-config").concat(change);
    install.updated = new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
    writeJson(installPath, install);
  };

  if (created) {
    writeFileSync(file, newViteConfig(importLine));
    record({ kind: "vite-config", file: rel, importLine, call: VITE_CALL, createdFile: true });
    did.push(`${rel}: new, with the page-comments plugin (there was no vite.config)`);
    return { did, file: rel, edited: true };
  }
  const text = readFileSync(file, "utf8");
  if (text.includes(importPath)) {
    did.push(`${rel}: already loads the page-comments plugin`);
    return { did, file: rel, edited: false };
  }
  const plugins = text.match(/\bplugins\s*:\s*\[/g) || [];
  const why = /\.c[jt]s$/.test(file) || (/\brequire\s*\(/.test(text) && !/^\s*import\s/m.test(text))
    ? "it is CommonJS"
    : plugins.length === 0
      ? "it has no `plugins: [` list"
      : plugins.length > 1
        ? "it has more than one `plugins: [` list"
        : null;
  if (why) {
    did.push(`${rel}: left alone, because ${why}; ${viteHowTo(importPath)}`);
    return { did, file: rel, edited: false };
  }
  const out = `${importLine}\n` + text.replace(/\bplugins\s*:\s*\[/, (m) => m + VITE_CALL);
  writeFileSync(file, out);
  record({ kind: "vite-config", file: rel, importLine, call: VITE_CALL, createdFile: false });
  did.push(`${rel}: imports the plugin and puts pageComments() first in plugins (dev server only)`);
  return { did, file: rel, edited: true };
}

/** Undo one vite-config change: only the two marked edits, or the file enable made. */
function undoVite(repo, c) {
  const path = join(repo, c.file);
  const text = readText(path);
  if (text === null) return null;
  if (c.createdFile && text === newViteConfig(c.importLine)) {
    rmSync(path);
    return `${c.file}: removed (enable made it)`;
  }
  let t = text.replace(`${c.importLine}\n`, "");
  const hadImport = t !== text;
  const before = t;
  t = t.replace(c.call || VITE_CALL, "");
  const hadCall = t !== before;
  if (t !== text) writeFileSync(path, t);
  if (hadImport && hadCall) return `${c.file}: took out the page-comments plugin`;
  if (!hadImport && !hadCall) return null;
  return `${c.file}: took out what was still there; check it for a leftover \`pageComments\``;
}

/** --vite --undo: only the Vite plugin; comments stay on. */
export function undoViteOnly(repo) {
  const dir = join(repo, FOLDER);
  const installPath = join(dir, "install.json");
  const install = readJson(installPath);
  const did = [];
  if (install && Array.isArray(install.changes)) {
    for (const c of install.changes.filter((x) => x.kind === "vite-config")) {
      const d = undoVite(repo, c);
      if (d) did.push(d);
    }
    install.changes = install.changes.filter((x) => x.kind !== "vite-config");
    writeJson(installPath, install);
  }
  if (existsSync(join(dir, "vite.mjs"))) {
    rmSync(join(dir, "vite.mjs"));
    did.push(`${FOLDER}/vite.mjs: removed`);
  }
  return did;
}

// ---- The userscript (phase 5) ---------------------------------------------------------------
//
// For pages the repo's own server serves, on a port the comment server is not in front
// of. The server answers those origins only, and only with the repo token (design
// section 9). Nothing outside .page-comments/ changes, and git never sees the token.

export function enableUserscript(repo, flags = {}) {
  const dir = join(repo, FOLDER);
  const configPath = join(dir, "config.json");
  const config = readJson(configPath);
  if (!config || !existsSync(join(dir, "install.json"))) throw new Exit(3, "page comments are not turned on here; run enable with --target or --root first, or add one of them to this --userscript run");
  const given = flags.origin || [];
  const bad = given.filter((o) => !cleanOrigin(o));
  if (bad.length) throw new Exit(2, `not a page origin: ${bad.join(", ")}. Pass the page's scheme, host and port, like --origin http://127.0.0.1:8765`);
  const port = Number((config.serve && config.serve.port) || 8766);
  const origins = [...new Set(userscriptOrigins(config).concat(given.map(cleanOrigin)))];
  if (!origins.length) throw new Exit(2, "say which pages the userscript runs on: --origin http://127.0.0.1:8765 (the page's own address, not the comment server's)");
  const own = origins.filter((o) => o === `http://127.0.0.1:${port}` || o === `http://localhost:${port}`);
  if (own.length) throw new Exit(2, `${own.join(", ")} is the comment server itself, whose pages already have the bar; pass the origin of the page the userscript runs on`);
  config.userscript = { ...(config.userscript && typeof config.userscript === "object" ? config.userscript : {}), origins };
  writeJson(configPath, config);
  const u = writeUserscript({ repo, dir });
  return {
    did: [
      `${FOLDER}/config.json: the userscript may call from ${origins.join(", ")}`,
      u.madeToken ? `${FOLDER}/.state/token: a new repo token (git ignores .state/)` : `${FOLDER}/.state/token: the repo token already there`,
      `${FOLDER}/.state/page-comments.user.js: the Tampermonkey script, with that token`,
    ],
    path: u.path,
    origins,
    server: u.server,
  };
}

export function undoUserscript(repo) {
  const dir = join(repo, FOLDER);
  const configPath = join(dir, "config.json");
  const did = [];
  const config = readJson(configPath);
  if (config && config.userscript) {
    delete config.userscript;
    writeJson(configPath, config);
    did.push(`${FOLDER}/config.json: removed the userscript's origins, so the server answers no other origin`);
  }
  const store = { repo, dir };
  for (const [f, what] of [[userscriptPath(store), "the userscript"], [tokenPath(store), "the repo token"]]) {
    if (existsSync(f)) {
      rmSync(f, { force: true });
      did.push(`${FOLDER}/.state/${basename(f)}: removed ${what}`);
    }
  }
  return did;
}

function userscriptReport(repo, u) {
  out("The userscript is ready.");
  for (const d of u.did) out(`  - ${d}`);
  out("");
  out("Install it in Tampermonkey: Dashboard, Utilities, Import from file, and pick");
  out(`  ${u.path}`);
  out(`It runs on ${u.origins.join(", ")} and calls the comment server at ${u.server}.`);
  out(`Start that with:  .page-comments/run serve --api-only --port ${u.server.split(":").pop()}`);
  out("              (or the usual make target, if the comment server is also in front of a page)");
  out("New token:       .page-comments/run serve --api-only --rotate-token   (then install the script again)");
  out(`Userscript off:  node ${join(HERE, "enable.mjs")} --userscript --undo --repo ${repo}`);
  return 0;
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
  const place = hookPlace(repo);
  if (place.skip) ok(null, "no post-commit hook", place.skip);
  else ok(ourHook(place.hook), "the post-commit hook notes which commit lands a comment's work", ourHook(place.hook) ? (existsSync(place.prev) ? "the earlier post-commit hook still runs first" : "") : "not in place; run enable again");

  // The ports. The loop below runs on a spare port, so it would pass even when
  // make comments cannot start, or when the target is another repo's site.
  const cport = config.serve.port || 8766;
  if (await portFree(cport)) ok(true, `port ${cport} is free for the comment server`);
  else {
    const o = portOwner(cport);
    const w = o.busy ? whose(o, repo) : null;
    if (o.busy && isCommentServer(o) && w.rel === "same") ok(true, `this repo's comment server is running on port ${cport}`);
    else {
      const free = await firstFreePort(cport + 1);
      ok(false, `port ${cport} is free for the comment server`, `in use by ${o.busy ? ownerText(o) : "another server"}; run enable again with --port ${free || "<n>"}`);
    }
  }
  const tport = config.serve.target && localPort(config.serve.target);
  if (tport) {
    const o = portOwner(tport);
    const w = o.busy ? whose(o, repo) : null;
    if (!o.known) ok(null, `could not tell which server is on port ${tport}`, "lsof did not answer");
    else if (!o.busy) ok(false, `this repo's site is running on port ${tport}`, "nothing is listening there; start the site's server first");
    else if (w.rel === "other") ok(false, `this repo's site is running on port ${tport}`, `port ${tport} is another repo's server: ${ownerText(o)}. Start this repo's server on a free port and run enable again with --target`);
    else if (w.rel === "worktree") ok(null, `the site on port ${tport} runs from another checkout of this repo`, w.where);
    else if (w.rel === "same") ok(true, `this repo's site is running on port ${tport}`, ownerText(o));
    else ok(null, `something is running on port ${tport}`, `${ownerText(o)}; could not tell which repo it is from`);
  }

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
  // The phone first, while install.json still says which serve entry enable added.
  const did = undoPhone(repo);
  let install = readJson(join(dir, "install.json"));
  if (!install) {
    // No list of changes: find enable's blocks by their markers instead.
    const changes = [];
    if ((readText(join(repo, "Makefile")) || "").includes(MAKE_BEGIN)) changes.push({ kind: "make", file: "Makefile", begin: MAKE_BEGIN, end: MAKE_END });
    for (const f of ["CLAUDE.md", ".claude/CLAUDE.md"]) if ((readText(join(repo, f)) || "").includes(MD_BEGIN)) changes.push({ kind: "claude-md", file: f, begin: MD_BEGIN, end: MD_END });
    const mp = marketplaceName(PLUGIN_ROOT, flags.marketplace);
    if (mp) changes.push({ kind: "settings", file: ".claude/settings.json", pluginId: `${PLUGIN}@${mp}`, createdFile: false, createdObject: false, keyWasThere: false });
    const place = hookPlace(repo);
    for (const n of VITE_NAMES) {
      const line = ((readText(join(repo, n)) || "").split("\n").find((l) => l.startsWith("import pageComments from ") && l.endsWith(VITE_MARK)));
      if (line) changes.push({ kind: "vite-config", file: n, importLine: line, call: VITE_CALL });
    }
    if (!place.skip && ourHook(place.hook)) changes.push({ kind: "post-commit-hook", file: relative(repo, place.hook), prev: relative(repo, place.prev), hadPrevious: existsSync(place.prev) });
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
    } else if (c.kind === "post-commit-hook") {
      const prev = join(repo, c.prev || join(dirname(c.file), HOOK_PREV));
      const text = readText(path);
      if (text !== null && !text.includes(HOOK_MARK)) {
        did.push(`${c.file}: left alone, because it is not page comments' hook any more${existsSync(prev) ? `; the earlier hook is still at ${HOOK_PREV}` : ""}`);
        continue;
      }
      if (text !== null) rmSync(path);
      if (c.hadPrevious && existsSync(prev)) {
        renameSync(prev, path);
        if (Number.isInteger(c.prevMode)) chmodSync(path, c.prevMode);
        did.push(`${c.file}: put back the post-commit hook that was there before`);
      } else if (text !== null) {
        did.push(`${c.file}: removed the post-commit hook`);
      }
    } else if (c.kind === "vite-config") {
      const d = undoVite(repo, c);
      if (d) did.push(d);
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

  // Screenshots are never deleted. Local ones stay in shots/, with the
  // .gitignore that keeps them out of git; iCloud ones are not touched at all.
  const cloud = existsSync(dir) ? shotTarget({ repo, dir }) : null;
  const cloudShots = cloud && cloud.kind === "icloud" && existsSync(cloud.base) ? contractHome(cloud.base) : null;
  const localShots = existsSync(join(dir, "shots"));
  const keep = localShots ? ["shots", ".gitignore"] : [];
  if (existsSync(dir)) {
    const threads = threadFiles(dir);
    if (flags.purge || !threads.length) {
      if (localShots) {
        for (const f of readdirSync(dir)) if (!keep.includes(f)) rmSync(join(dir, f), { recursive: true, force: true });
      } else {
        rmSync(dir, { recursive: true, force: true });
      }
      did.push(`${FOLDER}/: removed${threads.length ? `, with its ${threads.length} thread(s)` : " (it held no comments)"}${localShots ? `, except shots/ and its .gitignore` : ""}`);
    } else {
      for (const f of ["install.json", "run", "vite.mjs", ".state"].concat(localShots ? [] : [".gitignore"])) rmSync(join(dir, f), { recursive: true, force: true });
      did.push(`${FOLDER}/: removed the launchers and machine state; kept ${threads.length} thread(s), config.json and .gitattributes${localShots ? ", and shots/ with its .gitignore" : ""}. Run with --purge to delete them too`);
    }
  }
  if (cloudShots) did.push(`screenshots in ${cloudShots}/ were left alone; delete them by hand if you want them gone`);
  return did;
}

// ---- Main -----------------------------------------------------------------------------------

const HELP = `enable-page-comments: turn page comments on in a repo, check them, or undo.

  enable.mjs --detect [--repo .] [--json]          How the repo serves pages, and the mode that fits
  enable.mjs --repo . --target <url> [--port 8766]  Put the comment server in front of a running server
  enable.mjs --repo . --root <dir> [--port 8766]    Serve a folder of pages with the comment button
  enable.mjs --check [--repo .]                     Prove the loop: setting, CLAUDE.md, a test comment the watcher sees
  enable.mjs --undo [--repo .] [--purge [--force]]  Remove what enable added, and put back a post-commit
                                                    hook it moved aside; threads stay unless --purge
  enable.mjs --phone [--repo .]                     Comment from your phone too, through Tailscale (add
                                                    --target/--root/--port to enable at the same time)
  enable.mjs --phone --undo [--repo .]              Turn the phone off; the rest stays on
  enable.mjs --vite [--repo .] [--vite-config <f>]  The bar in Vite's own dev server, no second port
  enable.mjs --vite --undo [--repo .]               Turn the Vite plugin off; the rest stays on
  enable.mjs --userscript --origin <url>... [--repo .]
                                                    A Tampermonkey script for pages on another port,
                                                    with a per-repo token kept out of git
  enable.mjs --userscript --undo [--repo .]         Turn the userscript off; the rest stays on

Other flags: --author <name> (who page comments are from; default: your git first name),
--shots-dir <path> (where screenshots go; default: the global config's shotsDir, else
~/Library/Mobile Documents/com~apple~CloudDocs/CloudDesktop/data),
--marketplace <name> (only if it cannot be worked out).

Undo never deletes a screenshot, in iCloud Drive or in .page-comments/shots/.
--phone serves only the comment server's own https port on your tailnet, never Funnel,
and undo turns off only that port.`;

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
      if (d.warning) out(`Careful: ${d.warning}.`);
      if (d.mode) out(`Enable with: --${d.mode} ${d.mode === "target" ? d.target : d.root}`);
    }
    return d.mode ? 0 : 3;
  }
  if (flags.phone && flags.undo) {
    const did = undoPhone(repo);
    out(did.length ? "Page comments from the phone are off in this repo; the rest stays on." : "The phone was not on in this repo; nothing to undo.");
    for (const d of did) out(`  - ${d}`);
    return 0;
  }
  if (flags.userscript && flags.undo) {
    const did = undoUserscript(repo);
    out(did.length ? "The userscript is off in this repo; the rest stays on. Remove it from Tampermonkey too." : "The userscript was not on in this repo; nothing to undo.");
    for (const d of did) out(`  - ${d}`);
    return 0;
  }
  if (flags.vite && flags.undo) {
    const did = undoViteOnly(repo);
    out(did.length ? "The Vite plugin is off in this repo; the rest stays on. Restart the Vite dev server." : "The Vite plugin was not on in this repo; nothing to undo.");
    for (const d of did) out(`  - ${d}`);
    return 0;
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
  const extrasOnly = !flags.target && !flags.root && !flags.port;
  if (extrasOnly && (flags.phone || flags.vite || flags.userscript)) {
    if (flags.vite) viteReport(enableVite(repo, flags));
    if (flags.userscript) userscriptReport(repo, enableUserscript(repo, flags));
    if (flags.phone) return phoneReport(repo, enablePhone(repo));
    return 0;
  }
  // The comment port: what --port says, else what a previous run chose, else the
  // first free port from 8766, so a second repo does not reuse the first one's.
  const before = readJson(join(repo, FOLDER, "config.json"));
  const kept = before && before.serve && before.serve.port;
  if (!flags.port && !kept) flags.port = String((await firstFreePort(8766)) || 8766);
  const r = enable(repo, flags);
  out(`Page comments are on in ${basename(repo)}.`);
  for (const d of r.did) out(`  - ${d}`);
  for (const w of await portWarnings(repo, r.serve)) out(`  - careful: ${w}`);
  if (r.privacy) {
    out("");
    out(r.privacy);
  }
  out("");
  out(`Start it:   ${r.makeTarget ? `make ${r.makeTarget}` : `.page-comments/run serve ${r.serve.target ? `--target ${r.serve.target}` : `--root ${r.serve.root}`} --port ${r.port}`}`);
  out(`Open:       http://127.0.0.1:${r.port}/   and press C to comment`);
  out(`Check it:   node ${join(HERE, "enable.mjs")} --check --repo ${repo}`);
  out(`Undo it:    node ${join(HERE, "enable.mjs")} --undo --repo ${repo}`);
  const toCommit = [".page-comments/", ".claude/settings.json", "CLAUDE.md"].concat(r.makeTarget ? ["the Makefile"] : []);
  out(`Commit ${toCommit.slice(0, -1).join(", ")} and ${toCommit[toCommit.length - 1]} so every session in this repo can answer comments.`);
  if (flags.vite) {
    out("");
    viteReport(enableVite(repo, flags));
  }
  if (flags.userscript) {
    out("");
    userscriptReport(repo, enableUserscript(repo, flags));
  }
  if (flags.phone) {
    out("");
    return phoneReport(repo, enablePhone(repo));
  }
  return 0;
}

/**
 * What would stop the loop working right now: the comment port held by
 * something other than this repo's comment server, or the target port held by
 * another repo's server. Each is one plain line; none means all clear.
 */
export async function portWarnings(repo, serve) {
  const warn = [];
  if (!(await portFree(serve.port))) {
    const o = portOwner(serve.port);
    const ours = o.busy && isCommentServer(o) && whose(o, repo).rel === "same";
    if (!ours) {
      const free = await firstFreePort(serve.port + 1);
      warn.push(`port ${serve.port}, for the comment server, is in use by ${o.busy ? ownerText(o) : "another server"}, so make comments will fail until it stops. Run enable again with --port ${free || "<n>"} to move it.`);
    }
  }
  const t = serve.target && localPort(serve.target);
  if (t) {
    const o = portOwner(t);
    const w = o.busy ? whose(o, repo) : null;
    if (w && w.rel === "other") warn.push(`the target, port ${t}, is served by another repo right now: ${ownerText(o)}. Pages through the comment server would be that repo's.`);
  }
  return warn;
}

/** The port of a target on this Mac, or null for any other host. */
function localPort(target) {
  try {
    const u = new URL(target);
    if (!/^(127\.0\.0\.1|localhost|\[::1\])$/.test(u.hostname)) return null;
    return Number(u.port) || (u.protocol === "https:" ? 443 : 80);
  } catch {
    return null;
  }
}

function viteReport(v) {
  out(v.edited ? "The Vite plugin is on." : "The Vite plugin:");
  for (const d of v.did) out(`  - ${d}`);
  if (v.edited) out("Restart the Vite dev server; its pages then have the bar, on Vite's own port. Builds are not changed.");
  return 0;
}

function phoneReport(repo, p) {
  out("Page comments from the phone are on.");
  for (const d of p.did) out(`  - ${d}`);
  out("");
  out("config.json and install.json now name this Mac on your tailnet and your Tailscale login.");
  out("Both are committed with the repo, so keep the phone off in a repo anyone else can read.");
  out("");
  out(`On the phone: ${p.url}   (Tailscale on, signed in as ${p.login}; comments are from ${p.author})`);
  out("              The comment server must be running on the Mac, as usual.");
  out(`Phone off:    node ${join(HERE, "enable.mjs")} --phone --undo --repo ${repo}`);
  out(`              (runs ${p.off}; the rest of Tailscale is left alone)`);
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
