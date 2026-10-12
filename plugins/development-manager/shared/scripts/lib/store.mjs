// One append-only file per thread: `.page-comments/threads/<id>.jsonl`.
// Each line is one event. The first line opens the thread; later lines are
// replies, edits and status changes. Nothing is ever rewritten in place, so the
// server and the command line can both append without taking turns.

import { randomBytes } from "node:crypto";
import { appendFileSync, closeSync, mkdirSync, openSync, readdirSync, readFileSync, writeSync } from "node:fs";
import { join } from "node:path";
import { paths } from "./repo.mjs";
import { nowIso } from "./log.mjs";

export const BODY_MAX = 10000;
export const STATUSES = ["open", "resolved", "dismissed"];
const ID_RE = /^t_[0-9a-f]{6,32}$/;

export function isThreadId(id) {
  return typeof id === "string" && ID_RE.test(id);
}

export function threadFile(store, id) {
  if (!isThreadId(id)) throw new Error(`not a thread id: ${id}`);
  return join(paths(store).threads, `${id}.jsonl`);
}

/** Every thread id in the store, sorted. */
export function threadIds(store) {
  let names = [];
  try {
    names = readdirSync(paths(store).threads);
  } catch {
    return [];
  }
  return names
    .filter((n) => n.endsWith(".jsonl"))
    .map((n) => n.slice(0, -6))
    .filter(isThreadId)
    .sort();
}

/**
 * Read one thread file's events. A line that does not parse is skipped and
 * counted: a half-written last line is read whole on the next pass.
 * Returns { events, bad } or null when the file is missing.
 */
export function readEvents(store, id) {
  let raw;
  try {
    raw = readFileSync(threadFile(store, id), "utf8");
  } catch {
    return null;
  }
  const events = [];
  let bad = 0;
  for (const line of raw.split("\n")) {
    if (!line.trim()) continue;
    try {
      const e = JSON.parse(line);
      if (e && typeof e === "object" && typeof e.ev === "string") events.push(e);
      else bad++;
    } catch {
      bad++;
    }
  }
  return { events, bad };
}

/**
 * Fold a thread's events into the shared thread shape (section 12 of the design):
 * { id, resolved, status, anchor, rev, messages, page, viewport, waiting, … }.
 * Events are applied in time order, the opening line first, so lines merged in
 * from two branches (git's union merge) read the same either way round.
 */
export function foldThread(id, events) {
  const open = events.find((e) => e.ev === "thread");
  if (!open) return null;
  const rest = events
    .map((e, i) => ({ e, i }))
    .filter(({ e }) => e !== open)
    .sort((a, b) => cmpTs(a.e.ts, b.e.ts) || a.i - b.i)
    .map(({ e }) => e);

  const t = {
    id,
    resolved: false,
    status: "open",
    anchor: open.anchor || { type: "element" },
    rev: open.rev || {},
    page: open.page || {},
    viewport: open.viewport || null,
    messages: [{ author: str(open.author), ts: str(open.ts), body: str(open.body) }],
    history: [],
    lost: false,
  };
  for (const e of rest) {
    if (e.ev === "reply") {
      const m = { author: str(e.author), ts: str(e.ts), body: str(e.body) };
      if (e.commit) m.commit = str(e.commit);
      t.messages.push(m);
    } else if (e.ev === "edit") {
      const m = t.messages[e.index];
      if (m && Number.isInteger(e.index)) {
        m.body = str(e.body);
        m.edited = str(e.ts);
      }
    } else if (e.ev === "status" && STATUSES.includes(e.status)) {
      t.status = e.status;
      t.history.push({ status: e.status, author: str(e.author), ts: str(e.ts), note: e.note ? str(e.note) : undefined });
    } else if (e.ev === "anchor") {
      t.lost = e.state === "lost";
    }
  }
  t.resolved = t.status !== "open";
  const last = t.messages[t.messages.length - 1];
  t.waiting = t.status === "open" ? (last && last.author === "claude" ? "human" : "claude") : null;
  return t;
}

export function readThread(store, id) {
  const r = readEvents(store, id);
  return r ? foldThread(id, r.events) : null;
}

export function readAll(store) {
  const out = [];
  for (const id of threadIds(store)) {
    const t = readThread(store, id);
    if (t) out.push(t);
  }
  return out;
}

/** The shared thread shape, as `show --json` prints it. */
export function publicThread(t) {
  const out = {
    id: t.id,
    resolved: t.resolved,
    status: t.status,
    anchor: t.anchor,
    rev: t.rev,
    page: t.page,
    viewport: t.viewport,
    messages: t.messages,
    waiting: t.waiting,
  };
  if (t.history.length) out.history = t.history;
  if (t.lost) out.lost = true;
  return out;
}

function newId(store) {
  return `t_${randomBytes(3).toString("hex")}`;
}

/**
 * Open a new thread. The id is chosen here, never by the caller, and the file
 * is created with `wx` so two threads can never share one.
 */
export function createThread(store, { author, page, viewport, anchor, rev, body }) {
  mkdirSync(paths(store).threads, { recursive: true });
  for (let tries = 0; tries < 20; tries++) {
    const id = newId(store);
    let fd;
    try {
      fd = openSync(threadFile(store, id), "wx");
    } catch (err) {
      if (err.code === "EEXIST") continue;
      throw err;
    }
    const line = { v: 1, ev: "thread", id, ts: nowIso(), author, page, viewport, anchor, rev, body };
    try {
      writeSync(fd, JSON.stringify(line) + "\n");
    } finally {
      closeSync(fd);
    }
    return id;
  }
  throw new Error("could not pick a free thread id");
}

/** Append one event to an existing thread. One write per line, so an append is whole. */
export function appendEvent(store, id, event) {
  const line = { v: 1, ts: nowIso(), ...event };
  appendFileSync(threadFile(store, id), JSON.stringify(line) + "\n");
  return line;
}

export function addReply(store, id, { author, body, commit }) {
  const e = { ev: "reply", author, body };
  if (commit) e.commit = commit;
  return appendEvent(store, id, e);
}

export function setStatus(store, id, { author, status, note }) {
  if (!STATUSES.includes(status)) throw new Error(`unknown status: ${status}`);
  const e = { ev: "status", author, status };
  if (note) e.note = note;
  return appendEvent(store, id, e);
}

// ---- Checking what the page sends -------------------------------------------------

/** Cut a value to a string of at most `max` characters, or undefined. */
function cut(v, max) {
  if (typeof v !== "string") return undefined;
  return v.length > max ? v.slice(0, max) : v;
}

function num(v) {
  return typeof v === "number" && Number.isFinite(v) ? v : undefined;
}

/** Keep only the anchor fields the design names, with types checked and lengths capped. */
export function cleanAnchor(a) {
  a = a && typeof a === "object" ? a : {};
  const out = {
    type: a.type === "text" ? "text" : "element",
    commentId: cut(a.commentId, 200) || null,
    css: cut(a.css, 2000) || "",
    tag: cut(a.tag, 40) || "",
    label: cut(a.label, 80) || "",
  };
  if (a.quote && typeof a.quote === "object" && typeof a.quote.exact === "string") {
    out.quote = { exact: cut(a.quote.exact, 2000), prefix: cut(a.quote.prefix, 64) || "", suffix: cut(a.quote.suffix, 64) || "" };
  }
  if (a.box && typeof a.box === "object") {
    out.box = { fx: num(a.box.fx), fy: num(a.box.fy) };
  }
  return out;
}

export function cleanPage(p) {
  p = p && typeof p === "object" ? p : {};
  return { url: cut(p.url, 4000) || "", path: cut(p.path, 2000) || "/", title: cut(p.title, 300) || "" };
}

export function cleanViewport(v) {
  if (!v || typeof v !== "object") return null;
  return {
    w: num(v.w),
    h: num(v.h),
    dpr: num(v.dpr),
    scrollX: num(v.scrollX),
    scrollY: num(v.scrollY),
    scheme: v.scheme === "dark" ? "dark" : "light",
  };
}

/** A comment body: a non-empty string of at most BODY_MAX characters, or null. */
export function cleanBody(b) {
  if (typeof b !== "string") return null;
  const s = b.replace(/\r\n/g, "\n");
  if (!s.trim() || s.length > BODY_MAX) return null;
  return s;
}

function str(v) {
  return v === undefined || v === null ? "" : String(v);
}

function cmpTs(a, b) {
  const x = str(a);
  const y = str(b);
  return x < y ? -1 : x > y ? 1 : 0;
}
