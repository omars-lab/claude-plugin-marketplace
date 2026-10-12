// The thread `show --json` prints must fit schema/thread.schema.json. A small
// checker covers the keywords the schema uses, so no library is needed.
import { test } from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { addLanded, addReply, createThread, publicThread, readThread, setAnchorState, setStatus } from "../lib/store.mjs";
import { SAMPLE, SCRIPTS, tempRepo } from "./helpers.mjs";

const schema = JSON.parse(readFileSync(join(SCRIPTS, "schema", "thread.schema.json"), "utf8"));

function typeOf(v) {
  if (v === null) return "null";
  if (Array.isArray(v)) return "array";
  return typeof v;
}

function check(s, v, at = "$") {
  const errs = [];
  if (s.type) {
    const types = [].concat(s.type);
    const t = typeOf(v);
    if (!types.includes(t) && !(t === "number" && types.includes("integer"))) errs.push(`${at}: ${t} is not ${types.join("|")}`);
  }
  if (s.enum && !s.enum.includes(v)) errs.push(`${at}: ${JSON.stringify(v)} is not one of ${JSON.stringify(s.enum)}`);
  if (typeOf(v) === "object") {
    for (const k of s.required || []) if (!(k in v)) errs.push(`${at}: missing ${k}`);
    for (const [k, sub] of Object.entries(s.properties || {})) if (k in v && v[k] !== undefined) errs.push(...check(sub, v[k], `${at}.${k}`));
  }
  if (typeOf(v) === "array") {
    if (s.minItems && v.length < s.minItems) errs.push(`${at}: fewer than ${s.minItems}`);
    if (s.items) v.forEach((x, i) => errs.push(...check(s.items, x, `${at}[${i}]`)));
  }
  if (typeof v === "string" && s.maxLength && v.length > s.maxLength) errs.push(`${at}: longer than ${s.maxLength}`);
  return errs;
}

test("threads in every state fit the shared schema", () => {
  const { store, cleanup } = tempRepo();
  try {
    const a = createThread(store, SAMPLE);
    const b = createThread(store, { ...SAMPLE, anchor: { type: "text", css: "p", tag: "p", label: "x", quote: { exact: "walk", prefix: "the ", suffix: " is" } } });
    addReply(store, b, { author: "claude", body: "Done.", commit: "9c41d0e" });
    setStatus(store, b, { author: "claude", status: "resolved", note: "fixed" });
    // Phase 4: not found on the page, and made on uncommitted work that a later commit landed.
    const c = createThread(store, { ...SAMPLE, rev: { ...SAMPLE.rev, git: { commit: "abc1234", dirty: true } } });
    setAnchorState(store, c, { author: "sam", state: "lost" });
    addLanded(store, c, { commit: "def5678", from: "abc1234" });
    for (const id of [a, b, c]) {
      const t = JSON.parse(JSON.stringify(publicThread(readThread(store, id))));
      assert.deepEqual(check(schema, t), [], id);
    }
    assert.notDeepEqual(check(schema, { id: "x" }), [], "the checker does catch a bad thread");
  } finally {
    cleanup();
  }
});
