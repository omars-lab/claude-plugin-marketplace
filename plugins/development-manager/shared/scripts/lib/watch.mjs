// `watch` and `wait`: what changed between two looks at the thread files, and
// one line per change, in review-md's format:
//   <utc> pid=<n> ev=<event> page=<path> thread=<id> author=<name> msg="…"
//
// stdout is only ever event lines: every stdout line wakes Claude. Start-up and
// heartbeat lines go to `.page-comments/.state/watch.log`.
//
// Pictures: a new `shot` event prints `ev=shot` with the file's path, or, when
// the picture is not on this Mac (gone, or only an iCloud `.<name>.icloud`
// placeholder), `ev=shot_missing`. A picture that goes missing later, or turns
// up later, prints the same two lines.

import { existsSync, mkdirSync, readFileSync, renameSync, watch as fsWatch, writeFileSync } from "node:fs";
import { dirname } from "node:path";
import { readAll } from "./store.mjs";
import { paths } from "./repo.mjs";
import { shotFileState, shotPath } from "./shots.mjs";
import { fileLogger, formatLogLine, nowIso } from "./log.mjs";

/** What one look at the store saw, per thread id. */
export function takeSnapshot(store) {
  const snap = {};
  for (const t of readAll(store)) {
    snap[t.id] = {
      page: t.page && t.page.path ? t.page.path : "",
      status: t.status,
      lost: !!t.lost,
      messages: t.messages.map((m) => ({ author: m.author, ts: m.ts, body: m.body, edited: m.edited || "" })),
      lastStatusBy: t.history.length ? t.history[t.history.length - 1].author : "",
      waiting: t.waiting,
      shots: t.shots.map((x) => shotLook(store, x)),
    };
  }
  return snap;
}

function shotLook(store, x) {
  const s = { role: x.role, ts: x.ts, author: x.author || "" };
  if (x.error) return { ...s, error: x.error };
  const path = shotPath(store, x);
  return { ...s, sha: x.sha || "", commit: x.commit || "", path: path || "", state: shotFileState(path) };
}

const shotKey = (s) => `${s.role}\u0000${s.ts}\u0000${s.sha || ""}\u0000${s.error || ""}`;

/** One line for a shot: `shot` when the picture is here, `shot_missing` when not. */
function shotEvent(page, thread, s) {
  if (s.error) return { ev: "shot", page, thread, author: s.author, role: s.role, msg: `the capture failed: ${s.error}` };
  const e = { ev: s.state === "ok" ? "shot" : "shot_missing", page, thread, author: s.author, role: s.role, sha: s.sha };
  if (s.commit) e.commit = s.commit;
  if (s.state !== "ok") e.state = s.state;
  e.path = s.path;
  return e;
}

const msgKey = (m) => `${m.author}\u0000${m.ts}\u0000${m.body}`;
const whoKey = (m) => `${m.author}\u0000${m.ts}`;
const STATUS_EV = { resolved: "thread_resolved", dismissed: "thread_dismissed", open: "thread_reopened" };

/** Events between two snapshots, in a stable order (by thread id). */
export function diffSnapshots(prev, next, { exclude = [] } = {}) {
  const ex = new Set(exclude.map((a) => a.toLowerCase()));
  const out = [];
  for (const id of Object.keys(next).sort()) {
    const t = next[id];
    const old = prev[id];
    const last = t.messages[t.messages.length - 1] || { author: "", body: "" };
    if (!old) {
      const first = t.messages[0] || { author: "", body: "" };
      out.push({ ev: "thread_new", page: t.page, thread: id, author: first.author, msg: first.body });
      for (const m of t.messages.slice(1)) out.push({ ev: "message_new", page: t.page, thread: id, author: m.author, msg: m.body });
      if (t.status !== "open") out.push({ ev: STATUS_EV[t.status], page: t.page, thread: id, author: t.lastStatusBy, msg: last.body });
      for (const s of t.shots || []) out.push(shotEvent(t.page, id, s));
      continue;
    }
    const seen = new Set(old.messages.map(msgKey));
    const who = new Set(old.messages.map(whoKey));
    for (const m of t.messages) {
      if (seen.has(msgKey(m))) continue;
      // An edit keeps the author and time of the message it changes and marks
      // it `edited`. Two new messages can share an author and a second, so the
      // mark, not the time, is what tells an edit from a new message.
      const edited = !!m.edited && who.has(whoKey(m));
      out.push({ ev: edited ? "message_edited" : "message_new", page: t.page, thread: id, author: m.author, msg: m.body });
    }
    if (old.status !== t.status) {
      out.push({ ev: STATUS_EV[t.status], page: t.page, thread: id, author: t.lastStatusBy, msg: last.body });
    }
    if (t.status === "open" && t.lost && !old.lost) {
      out.push({ ev: "anchor_lost", page: t.page, thread: id, author: "", msg: last.body });
    }
    const before = new Map((old.shots || []).map((s) => [shotKey(s), s]));
    for (const s of t.shots || []) {
      const was = before.get(shotKey(s));
      if (!was || (!s.error && was.state !== s.state && (s.state === "ok" || was.state === "ok"))) out.push(shotEvent(t.page, id, s));
    }
  }
  return out.filter((e) => !(e.author && ex.has(e.author.toLowerCase())));
}

/** `--replay`: one `thread_open` per open thread that is waiting on Claude. */
export function replayEvents(snap, { exclude = [] } = {}) {
  const ex = new Set(exclude.map((a) => a.toLowerCase()));
  const out = [];
  for (const id of Object.keys(snap).sort()) {
    const t = snap[id];
    if (t.status !== "open" || t.waiting !== "claude") continue;
    const last = t.messages[t.messages.length - 1] || { author: "", body: "" };
    if (last.author && ex.has(last.author.toLowerCase())) continue;
    out.push({ ev: "thread_open", page: t.page, thread: id, author: last.author, msg: last.body });
    if (t.lost) out.push({ ev: "anchor_lost", page: t.page, thread: id, author: "", msg: last.body });
  }
  return out;
}

export function formatEvent(e, json) {
  if (json) return JSON.stringify({ ts: nowIso(), pid: process.pid, ...e });
  const { ev, ...rest } = e;
  return formatLogLine(nowIso(), process.pid, ev, rest);
}

function readJson(path) {
  try {
    return JSON.parse(readFileSync(path, "utf8"));
  } catch {
    return null;
  }
}

function writeJson(path, value) {
  mkdirSync(dirname(path), { recursive: true });
  const tmp = `${path}.${process.pid}.tmp`;
  writeFileSync(tmp, JSON.stringify(value));
  renameSync(tmp, path);
}

/**
 * Call `onPass` whenever the threads folder may have changed: on fs.watch
 * events (debounced) and on a poll as a backstop. Returns a stop function.
 */
function onChanges(store, onPass, intervalMs) {
  const dir = paths(store).threads;
  mkdirSync(dir, { recursive: true });
  let timer = null;
  const kick = () => {
    if (timer) return;
    timer = setTimeout(() => {
      timer = null;
      onPass();
    }, 150);
  };
  let watcher = null;
  try {
    watcher = fsWatch(dir, kick);
    watcher.on("error", () => {});
  } catch {
    watcher = null;
  }
  const poll = setInterval(onPass, intervalMs);
  return () => {
    clearInterval(poll);
    if (timer) clearTimeout(timer);
    if (watcher) watcher.close();
  };
}

/**
 * `watch`: print one line per change until stopped.
 * Options: exclude (names), replay, once, state (file), json, intervalMs, heartbeatS.
 */
export function runWatch(store, opts, write = (s) => process.stdout.write(s + "\n")) {
  const log = fileLogger(paths(store).watchLog);
  const exclude = opts.exclude || [];
  const emit = (events) => events.forEach((e) => write(formatEvent(e, opts.json)));

  if (opts.once) {
    const prev = (opts.state && readJson(opts.state)) || null;
    const now = takeSnapshot(store);
    const events = prev ? diffSnapshots(prev, now, { exclude }) : opts.replay ? replayEvents(now, { exclude }) : diffSnapshots({}, now, { exclude });
    emit(events);
    if (opts.state) writeJson(opts.state, now);
    log("once", { events: events.length });
    return Promise.resolve(0);
  }

  let snap = takeSnapshot(store);
  if (opts.replay) emit(replayEvents(snap, { exclude }));
  const counts = () => {
    const all = Object.values(snap);
    return { threads: all.length, open: all.filter((t) => t.status === "open").length, waiting: all.filter((t) => t.waiting === "claude").length };
  };
  log("start", { repo: store.repo, ...counts() });

  return new Promise((resolveDone) => {
    const pass = () => {
      if (!existsSync(store.dir)) {
        // Comments were turned off under us: leave quietly.
        stop();
        log("stop", { reason: "folder_gone" });
        resolveDone(0);
        return;
      }
      const next = takeSnapshot(store);
      emit(diffSnapshots(snap, next, { exclude }));
      snap = next;
    };
    const stopWatching = onChanges(store, pass, opts.intervalMs || 2000);
    const hbMs = (opts.heartbeatS === undefined ? 60 : opts.heartbeatS) * 1000;
    const hb = hbMs > 0 ? setInterval(() => log("heartbeat", counts()), hbMs) : null;
    const stop = () => {
      stopWatching();
      if (hb) clearInterval(hb);
    };
    const quit = () => {
      stop();
      log("stop", { reason: "signal" });
      resolveDone(0);
    };
    process.once("SIGTERM", quit);
    process.once("SIGINT", quit);
  });
}

/**
 * `wait`: block until something new for Claude, print it, exit. A cursor in
 * `.state/wait-cursor.json` remembers what was already reported, so nothing is
 * missed between runs. The first run reports threads already waiting on Claude.
 */
export function runWait(store, opts, write = (s) => process.stdout.write(s + "\n")) {
  const cursorPath = paths(store).waitCursor;
  const exclude = opts.exclude && opts.exclude.length ? opts.exclude : ["claude"];
  const log = fileLogger(paths(store).watchLog);
  const cursor = readJson(cursorPath);

  const finish = (events, now) => {
    events.forEach((e) => write(formatEvent(e, opts.json)));
    writeJson(cursorPath, now);
    log("wait_done", { events: events.length });
  };

  const now = takeSnapshot(store);
  const first = cursor ? diffSnapshots(cursor, now, { exclude }) : replayEvents(now, { exclude });
  if (first.length) {
    finish(first, now);
    return Promise.resolve(0);
  }
  writeJson(cursorPath, now);
  let base = now;

  return new Promise((resolveDone) => {
    let timeout = null;
    const pass = () => {
      const next = takeSnapshot(store);
      const events = diffSnapshots(base, next, { exclude });
      base = next;
      if (!events.length) {
        writeJson(cursorPath, next);
        return;
      }
      stop();
      finish(events, next);
      resolveDone(0);
    };
    const stopWatching = onChanges(store, pass, opts.intervalMs || 2000);
    const stop = () => {
      stopWatching();
      if (timeout) clearTimeout(timeout);
    };
    if (opts.timeoutS > 0) {
      timeout = setTimeout(() => {
        stop();
        log("wait_timeout", { seconds: opts.timeoutS });
        resolveDone(0);
      }, opts.timeoutS * 1000);
    }
  });
}
