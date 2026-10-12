#!/usr/bin/env node
// page-comments: the one command line for comments on localhost pages.
// Both page-comment skills, the plugin monitor and the repo launcher
// (`.page-comments/run`) call it. Node 18, no dependencies.
//
// Exit codes (review-md's agent contract): 0 ok, 2 bad usage, 3 not found,
// 4 the write did not land.

import { readFileSync } from "node:fs";
import { storeFor } from "./lib/repo.mjs";
import { addReply, isThreadId, publicThread, readAll, readThread, setStatus, cleanBody } from "./lib/store.mjs";
import { runWait, runWatch } from "./lib/watch.mjs";
import { restamp } from "./lib/restamp.mjs";
import { isPng, saveShot, shotFileState, shotPath, SHOT_MAX } from "./lib/shots.mjs";

const HELP = `page-comments: comments on pages served on this machine.

Commands:
  serve --target <url> | --root <dir> | --api-only [--port n] [--rotate-token]
                                                   Run the comment server on 127.0.0.1.
                                                   --api-only answers only the comment API,
                                                   for the userscript; --rotate-token makes
                                                   a new repo token and writes the userscript again
  watch [--exclude-author name]... [--replay] [--once --state <file>] [--json]
        [--heartbeat s] [--interval s]             Print one ev= line per change
  wait [--exclude-author name] [--timeout s] [--json]
                                                   Block until something new for Claude
  list [--open] [--waiting <name>] [--page <path>] [--json]
  show <id> [--json]                               The thread, with where its pictures are
  reply <id> [--author claude] [--commit sha] "<text>"
  shot <id> --file <png> --commit <sha> [--author claude]
                                                   Attach an "after" picture, taken
                                                   against that commit
  resolve <id> [--reopen] [--author claude] ["note"]
  dismiss <id> [--author claude] ["note"]
  stats [--json]
  restamp                                          After a commit: note which commit
                                                   landed the uncommitted work a comment
                                                   was made on (the post-commit hook runs it)
  notice                                           One line when threads wait on Claude;
                                                   nothing otherwise (the session-start hook)

Every command takes --repo <path>; without it the repo is found by walking up
from the current folder to the git root, looking for .page-comments/.

Exit codes: 0 ok, 2 bad usage, 3 not found, 4 the write did not land.`;

const VALUE_FLAGS = new Set(["repo", "target", "root", "port", "state", "page", "waiting", "author", "commit", "exclude-author", "heartbeat", "interval", "timeout", "host", "file"]);
const BOOL_FLAGS = new Set(["open", "json", "replay", "once", "reopen", "help", "throwaway", "api-only", "rotate-token"]);

export function parseArgs(argv) {
  const flags = { "exclude-author": [] };
  const pos = [];
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === "--") {
      pos.push(...argv.slice(i + 1));
      break;
    }
    if (a.startsWith("--")) {
      let name = a.slice(2);
      let value;
      const eq = name.indexOf("=");
      if (eq >= 0) {
        value = name.slice(eq + 1);
        name = name.slice(0, eq);
      }
      if (BOOL_FLAGS.has(name)) {
        flags[name] = true;
      } else if (VALUE_FLAGS.has(name)) {
        if (value === undefined) {
          value = argv[++i];
          if (value === undefined) throw usage(`--${name} needs a value`);
        }
        if (name === "exclude-author") flags[name].push(value);
        else flags[name] = value;
      } else {
        throw usage(`unknown flag --${name}`);
      }
    } else {
      pos.push(a);
    }
  }
  return { flags, pos };
}

class CliError extends Error {
  constructor(code, message) {
    super(message);
    this.code = code;
  }
}
const usage = (m) => new CliError(2, m);
const notFound = (m) => new CliError(3, m);
const notLanded = (m) => new CliError(4, m);

function needStore(flags) {
  const store = storeFor(flags.repo);
  if (!store) {
    throw notFound(
      "no .page-comments/ folder here. Comments are not turned on in this repo; run /development-manager:enable-page-comments.",
    );
  }
  return store;
}

function needThread(store, id) {
  if (!id) throw usage("which thread? Pass its id, like t_8f3a2c");
  if (!isThreadId(id)) throw usage(`not a thread id: ${id}`);
  const t = readThread(store, id);
  if (!t) throw notFound(`no thread ${id}`);
  return t;
}

const out = (s) => process.stdout.write(s + "\n");
const oneLine = (s, max = 100) => {
  const x = String(s || "").replace(/\s+/g, " ").trim();
  return x.length > max ? `${x.slice(0, max - 1)}…` : x;
};

function filterThreads(threads, flags) {
  return threads.filter(
    (t) =>
      (!flags.open || t.status === "open") &&
      (!flags.waiting || t.waiting === (flags.waiting === "claude" ? "claude" : "human")) &&
      (!flags.page || (t.page && t.page.path) === flags.page),
  );
}

function groupByPage(threads) {
  const pages = new Map();
  for (const t of threads) {
    const p = (t.page && t.page.path) || "/";
    if (!pages.has(p)) pages.set(p, []);
    pages.get(p).push(t);
  }
  return [...pages.entries()].sort((a, b) => (a[0] < b[0] ? -1 : 1));
}

function cmdList(flags) {
  const store = needStore(flags);
  const threads = filterThreads(readAll(store), flags);
  if (flags.json) {
    // review-md's shapes: one page gives { uid, file, vaultPath, threads };
    // all pages give { root, files: [{ file, vaultPath, uid, threads }] }.
    // `file` is the page path and `vaultPath` the repo root (design section 12).
    if (flags.page) {
      out(JSON.stringify({ uid: null, file: flags.page, vaultPath: store.repo, threads: threads.map(publicThread) }, null, 2));
    } else {
      const files = groupByPage(threads).map(([file, ts]) => ({ file, vaultPath: store.repo, uid: null, threads: ts.map(publicThread) }));
      out(JSON.stringify({ root: store.repo, files }, null, 2));
    }
    return 0;
  }
  if (!threads.length) {
    out("No threads match.");
    return 0;
  }
  for (const [page, ts] of groupByPage(threads)) {
    out(`${page}`);
    for (const t of ts) {
      const first = t.messages[0];
      const last = t.messages[t.messages.length - 1];
      const waiting = t.waiting ? ` waiting on ${t.waiting}` : "";
      const where = t.anchor.label ? ` on <${t.anchor.tag}> "${oneLine(t.anchor.label, 40)}"` : t.anchor.tag ? ` on <${t.anchor.tag}>` : "";
      out(`  ${t.id}  ${t.status}${waiting}${t.lost ? ", not found on the page" : ""}${where}`);
      out(`    ${first.author}: ${oneLine(first.body)}`);
      if (last !== first) out(`    last, ${last.author}: ${oneLine(last.body)}`);
    }
  }
  return 0;
}

/** Each shot with `path`: where its picture is on this Mac, so Claude can open it. */
function shotsWithPaths(store, t) {
  return t.shots.map((s) => {
    if (s.error) return s;
    const path = shotPath(store, s);
    return path ? { ...s, path } : s;
  });
}

function cmdShow(flags, pos) {
  const store = needStore(flags);
  const t = needThread(store, pos[0]);
  const shots = shotsWithPaths(store, t);
  if (flags.json) {
    const pub = publicThread(t);
    if (shots.length) pub.shots = shots;
    out(JSON.stringify(pub, null, 2));
    return 0;
  }
  const a = t.anchor || {};
  out(`${t.id}  ${t.status}${t.waiting ? `, waiting on ${t.waiting}` : ""}`);
  if (t.lost) out("Not found: the page last reported it could not find this comment's element.");
  out(`Page:      ${t.page.url || t.page.path}${t.page.title ? `  (${t.page.title})` : ""}`);
  if (t.viewport) {
    const v = t.viewport;
    out(`Viewport:  ${v.w}x${v.h} at ${v.dpr}x, scrolled to ${v.scrollX},${v.scrollY}, ${v.scheme} scheme`);
  }
  out(`Anchor:    ${a.type}${a.commentId ? `  data-comment-id=${a.commentId}` : ""}`);
  if (a.css) out(`  css:     ${a.css}`);
  if (a.tag) out(`  tag:     <${a.tag}>`);
  if (a.label) out(`  label:   ${a.label}`);
  if (a.quote) out(`  quote:   "${a.quote.exact}"${a.quote.prefix ? ` after "${a.quote.prefix}"` : ""}${a.quote.suffix ? ` before "${a.quote.suffix}"` : ""}`);
  const g = (t.rev && t.rev.git) || {};
  if (g.commit) out(`Made at:   commit ${g.commit}${g.dirty ? ", with uncommitted changes" : ""}`);
  if (t.rev && t.rev.landed) out(`Landed in: commit ${t.rev.landed.commit} (the commit that took in those changes)`);
  for (const s of shots) {
    const what = s.role === "comment" ? "the comment's picture" : `after picture, commit ${s.commit || "?"}`;
    if (s.error) {
      out(`Shot:      ${what} failed: ${s.error}`);
      continue;
    }
    const state = s.path ? shotFileState(s.path) : "missing";
    const note = state === "ok" ? "" : state === "placeholder" ? "  (in iCloud, not downloaded to this Mac yet)" : "  (not on this Mac)";
    out(`Shot:      ${what}, sha ${s.sha || "?"}${note}`);
    out(`  pointer: ${s.icloud ? `icloud:${s.icloud}` : `local:${s.local}`}`);
    if (s.path) out(`  file:    ${s.path}`);
  }
  out("");
  for (const m of t.messages) {
    out(`${m.author}, ${m.ts}${m.commit ? `, commit ${m.commit}` : ""}${m.edited ? " (edited)" : ""}:`);
    for (const line of m.body.split("\n")) out(`  ${line}`);
  }
  for (const h of t.history) out(`[${h.status} by ${h.author}, ${h.ts}${h.note ? `: ${h.note}` : ""}]`);
  return 0;
}

function textArg(pos, from) {
  const body = pos.slice(from).join(" ");
  return body;
}

function cmdReply(flags, pos) {
  const store = needStore(flags);
  const t = needThread(store, pos[0]);
  const body = cleanBody(textArg(pos, 1));
  if (!body) throw usage('reply needs text: reply <id> "…" (up to 10,000 characters)');
  const author = flags.author || "claude";
  try {
    addReply(store, t.id, { author, body, commit: flags.commit });
  } catch (err) {
    throw notLanded(`the reply to ${t.id} did not land: ${err.code || err.message}`);
  }
  const after = readThread(store, t.id);
  const last = after && after.messages[after.messages.length - 1];
  if (!last || last.body !== body || last.author !== author) throw notLanded(`the reply to ${t.id} did not land`);
  out(`${t.id} replied`);
  return 0;
}

function cmdShot(flags, pos) {
  const store = needStore(flags);
  const t = needThread(store, pos[0]);
  if (!flags.file) throw usage("shot needs --file <png>: the picture to attach");
  const commit = String(flags.commit || "").toLowerCase();
  if (!/^[0-9a-f]{7,40}$/.test(commit)) throw usage("shot needs --commit <sha>: the commit the picture was taken against");
  let buf;
  try {
    buf = readFileSync(flags.file);
  } catch (err) {
    throw notFound(`cannot read ${flags.file}: ${err.code || err.message}`);
  }
  if (!isPng(buf)) throw usage(`${flags.file} is not a PNG picture`);
  if (buf.length > SHOT_MAX) throw usage(`${flags.file} is over ${SHOT_MAX / 1024 / 1024} MB`);
  let e;
  try {
    e = saveShot(store, t.id, buf, { role: "after", commit, author: flags.author || "claude" });
  } catch (err) {
    throw notLanded(`the picture for ${t.id} did not land: ${err.code || err.message}`);
  }
  const s = readThread(store, t.id).shots.find((x) => x.sha === e.sha && x.ts === e.ts);
  const path = s && shotPath(store, s);
  if (!path || shotFileState(path) !== "ok") throw notLanded(`the picture for ${t.id} did not land`);
  out(`${t.id} after picture attached, sha ${e.sha}`);
  out(`  pointer: ${e.icloud ? `icloud:${e.icloud}` : `local:${e.local}`}`);
  out(`  file:    ${path}`);
  return 0;
}

function cmdStatus(flags, pos, status) {
  const store = needStore(flags);
  const t = needThread(store, pos[0]);
  const note = textArg(pos, 1) || undefined;
  if (note && note.length > 10000) throw usage("the note is longer than 10,000 characters");
  try {
    setStatus(store, t.id, { author: flags.author || "claude", status, note });
  } catch (err) {
    throw notLanded(`${t.id} did not change to ${status}: ${err.code || err.message}`);
  }
  const after = readThread(store, t.id);
  if (!after || after.status !== status) throw notLanded(`${t.id} did not change to ${status}`);
  out(`${t.id} ${status === "open" ? "reopened" : status}`);
  return 0;
}

function cmdStats(flags) {
  const store = needStore(flags);
  const rows = groupByPage(readAll(store)).map(([page, ts]) => ({
    page,
    open: ts.filter((t) => t.status === "open").length,
    waiting: ts.filter((t) => t.waiting === "claude").length,
    resolved: ts.filter((t) => t.status === "resolved").length,
    dismissed: ts.filter((t) => t.status === "dismissed").length,
  }));
  const total = rows.reduce(
    (s, r) => ({ open: s.open + r.open, waiting: s.waiting + r.waiting, resolved: s.resolved + r.resolved, dismissed: s.dismissed + r.dismissed }),
    { open: 0, waiting: 0, resolved: 0, dismissed: 0 },
  );
  if (flags.json) {
    out(JSON.stringify({ root: store.repo, pages: rows, total }, null, 2));
    return 0;
  }
  out("| page | open | waiting on Claude | resolved | dismissed |");
  out("|---|---|---|---|---|");
  for (const r of rows) out(`| ${r.page} | ${r.open} | ${r.waiting} | ${r.resolved} | ${r.dismissed} |`);
  out(`| **total** | ${total.open} | ${total.waiting} | ${total.resolved} | ${total.dismissed} |`);
  return 0;
}

/** The post-commit hook. Silent unless it stamped something, and never fails a commit. */
function cmdRestamp(flags) {
  const store = storeFor(flags.repo);
  if (!store) return 0;
  let r;
  try {
    r = restamp(store);
  } catch (err) {
    process.stderr.write(`page-comments restamp: ${err.message}\n`);
    return 0;
  }
  if (r.landed && r.landed.length) {
    const n = r.landed.length;
    out(`page-comments: ${n} comment${n === 1 ? "" : "s"} made on uncommitted work now point${n === 1 ? "s" : ""} at commit ${r.commit}.`);
  }
  return 0;
}

/** The session-start hook: one line when open threads wait on Claude, nothing otherwise. */
function cmdNotice(flags) {
  const store = storeFor(flags.repo);
  if (!store) return 0;
  const open = readAll(store).filter((t) => t.status === "open");
  const waiting = open.filter((t) => t.waiting === "claude");
  if (!waiting.length) return 0;
  const lost = waiting.filter((t) => t.lost).length;
  const n = waiting.length;
  out(
    `Page comments: ${n} comment thread${n === 1 ? " is" : "s are"} waiting on Claude in this repo` +
      `${lost ? ` (${lost} not found on ${lost === 1 ? "its" : "their"} page)` : ""}. ` +
      "List them with: .page-comments/run list --open --waiting claude",
  );
  return 0;
}

function seconds(v, name) {
  if (v === undefined) return undefined;
  const n = Number(v);
  if (!Number.isFinite(n) || n < 0) throw usage(`--${name} takes a number of seconds`);
  return n;
}

async function cmdWatch(flags) {
  const store = storeFor(flags.repo);
  // Silent where comments are off: no output, no log, exit 0. The plugin
  // monitor runs in every repo, and a stray line would wake Claude for nothing.
  if (!store) return 0;
  if (flags.once && !flags.state) throw usage("--once needs --state <file>");
  const interval = seconds(flags.interval, "interval");
  return runWatch(store, {
    exclude: flags["exclude-author"],
    replay: !!flags.replay,
    once: !!flags.once,
    state: flags.state,
    json: !!flags.json,
    heartbeatS: seconds(flags.heartbeat, "heartbeat"),
    intervalMs: interval ? interval * 1000 : undefined,
  });
}

async function cmdWait(flags) {
  const store = needStore(flags);
  const interval = seconds(flags.interval, "interval");
  return runWait(store, {
    exclude: flags["exclude-author"],
    json: !!flags.json,
    timeoutS: seconds(flags.timeout, "timeout"),
    intervalMs: interval ? interval * 1000 : undefined,
  });
}

async function cmdServe(flags) {
  const store = needStore(flags);
  if ([flags.target, flags.root, flags["api-only"]].filter(Boolean).length !== 1) throw usage("serve needs exactly one of --target <url>, --root <dir> or --api-only");
  const port = flags.port === undefined ? 8766 : Number(flags.port);
  if (!Number.isInteger(port) || port < 0 || port > 65535) throw usage("--port takes a port number");
  if (flags.target && !/^https?:\/\//.test(flags.target)) throw usage("--target takes a URL, like http://127.0.0.1:8765");
  // The userscript (design section 9): --rotate-token makes a new repo token;
  // either way a listed origin with no token yet (a fresh clone) gets one.
  const { readRepoToken, rotateToken, userscriptOrigins, writeUserscript } = await import("./lib/userscript.mjs");
  const { readConfig } = await import("./lib/repo.mjs");
  const listed = userscriptOrigins(readConfig(store)).length > 0;
  if (flags["rotate-token"] || (listed && !readRepoToken(store))) {
    const u = flags["rotate-token"] ? rotateToken(store) : writeUserscript(store);
    if (u) {
      out(`New repo token. The userscript for ${u.origins.join(", ")} is written again:`);
      out(`  ${u.path}`);
      out("  Install it in Tampermonkey again (Dashboard, Utilities, Import from file); the old one stops working.");
    } else {
      out("New repo token. No userscript: config.json lists no origins for it (enable.mjs --userscript --origin <url> adds one).");
    }
  }
  const { startServer } = await import("./lib/server.mjs");
  const srv = await startServer(store, { target: flags.target, root: flags.root, port, record: !flags.throwaway });
  out(`Comment server on ${srv.url}  (${flags.target ? `in front of ${flags.target}` : flags.root ? `serving ${flags.root}` : "the comment API only, for the userscript"})`);
  out(`Press C on a page${flags["api-only"] ? " the userscript runs on" : ""} to comment. Stop with Ctrl-C.`);
  return new Promise((resolveDone) => {
    const quit = () => srv.close().then(() => resolveDone(0));
    process.once("SIGTERM", quit);
    process.once("SIGINT", quit);
  });
}

export async function main(argv) {
  const { flags, pos } = parseArgs(argv);
  const cmd = pos.shift();
  if (!cmd || flags.help || cmd === "help") {
    out(HELP);
    return cmd || flags.help ? 0 : 2;
  }
  switch (cmd) {
    case "serve":
      return cmdServe(flags);
    case "watch":
      return cmdWatch(flags);
    case "wait":
      return cmdWait(flags);
    case "list":
      return cmdList(flags);
    case "show":
      return cmdShow(flags, pos);
    case "reply":
      return cmdReply(flags, pos);
    case "shot":
      return cmdShot(flags, pos);
    case "resolve":
      return cmdStatus(flags, pos, flags.reopen ? "open" : "resolved");
    case "dismiss":
      return cmdStatus(flags, pos, "dismissed");
    case "stats":
      return cmdStats(flags);
    case "restamp":
      return cmdRestamp(flags);
    case "notice":
      return cmdNotice(flags);
    default:
      throw usage(`unknown command: ${cmd}. Run page-comments help.`);
  }
}

const isMain = process.argv[1] && import.meta.url === new URL(`file://${process.argv[1]}`).href;
if (isMain) {
  process.stdout.on("error", (err) => {
    if (err.code === "EPIPE") process.exit(0);
  });
  main(process.argv.slice(2)).then(
    (code) => {
      process.exitCode = code || 0;
    },
    (err) => {
      if (err instanceof CliError) {
        process.stderr.write(`page-comments: ${err.message}\n`);
        process.exitCode = err.code;
      } else {
        process.stderr.write(`page-comments: ${err && err.stack ? err.stack : err}\n`);
        process.exitCode = 1;
      }
    },
  );
}
