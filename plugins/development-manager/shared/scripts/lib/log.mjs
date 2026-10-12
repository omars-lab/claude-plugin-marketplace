// One greppable line per event: `<utc> pid=<n> ev=<event> key=value … msg="…"`.
// Same shape as review-md's watch lines, so one reader understands both.

import { appendFileSync, mkdirSync } from "node:fs";
import { dirname } from "node:path";

/** How long a `msg="…"` gets on a text line before it is cut with "…". */
export const MSG_MAX = 200;

/** A value for a `key=value` line: bare when it has no spaces, quotes or `=`,
 *  else double-quoted with `\` and `"` escaped. Newlines always collapse. */
export function logValue(v, max = Infinity) {
  let s = String(v === undefined || v === null ? "" : v).replace(/\s+/g, " ").trim();
  if (s.length > max) s = `${s.slice(0, max - 1)}…`;
  return s !== "" && !/[\s"=\\]/.test(s) ? s : `"${s.replace(/\\/g, "\\\\").replace(/"/g, '\\"')}"`;
}

export function formatLogLine(ts, pid, ev, fields = {}) {
  const parts = [ts, `pid=${pid}`, `ev=${ev}`];
  for (const [k, v] of Object.entries(fields)) {
    if (k === "msg" || v === undefined) continue;
    parts.push(`${k}=${logValue(v)}`);
  }
  if (fields.msg !== undefined) parts.push(`msg=${logValue(fields.msg, MSG_MAX)}`);
  return parts.join(" ");
}

export function nowIso() {
  return new Date().toISOString().replace(/\.\d{3}Z$/, "Z");
}

/** A logger that appends to one file. Never throws: a log that cannot be
 *  written must not take the server or the watcher down with it. */
export function fileLogger(path) {
  let ready = false;
  return (ev, fields = {}) => {
    try {
      if (!ready) {
        mkdirSync(dirname(path), { recursive: true });
        ready = true;
      }
      appendFileSync(path, formatLogLine(nowIso(), process.pid, ev, fields) + "\n");
    } catch {
      /* ignore */
    }
  };
}
