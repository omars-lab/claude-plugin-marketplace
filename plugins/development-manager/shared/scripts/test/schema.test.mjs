// The thread `show --json` prints must fit schema/thread.schema.json. A small
// checker covers the keywords the schema uses, so no library is needed.
//
// The schema's source is review-md's schema/thread.schema.json (review-md PR #28);
// this is a pinned copy. Set REVIEW_MD_SCHEMA to that file's path to check the two
// are still the same; without it, that one test is skipped.
import { test } from "node:test";
import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";
import { addLanded, addReply, createThread, publicThread, readThread, setAnchorState, setStatus } from "../lib/store.mjs";
import { SAMPLE, SCRIPTS, tempRepo } from "./helpers.mjs";

const SCHEMA = join(SCRIPTS, "schema", "thread.schema.json");
const schema = JSON.parse(readFileSync(SCHEMA, "utf8"));

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
      // The shared schema leaves these optional for review-md; page comments always set them.
      assert.ok(["open", "resolved", "dismissed"].includes(t.status), `${id} has a status`);
      assert.equal(typeof t.rev, "object", `${id} has a rev`);
      assert.ok(t.rev && "bodyHash" in t.rev && t.rev.git, `${id}'s rev has the hash and the commit`);
      assert.ok(["element", "text"].includes(t.anchor.type), `${id}'s anchor is an element or text`);
      if (t.anchor.quote !== undefined) assert.equal(typeof t.anchor.quote.exact, "string", `${id}'s quote is an object`);
    }
    assert.notDeepEqual(check(schema, { id: "x" }), [], "the checker does catch a bad thread");
  } finally {
    cleanup();
  }
});

test("the pinned schema is byte for byte review-md's (set REVIEW_MD_SCHEMA to check)", (t) => {
  const source = process.env.REVIEW_MD_SCHEMA;
  if (!source) return t.skip("REVIEW_MD_SCHEMA is not set: point it at review-md's schema/thread.schema.json to check the pinned copy");
  assert.ok(existsSync(source), `REVIEW_MD_SCHEMA points at nothing: ${source}`);
  assert.ok(readFileSync(source).equals(readFileSync(SCHEMA)), "shared/scripts/schema/thread.schema.json differs from review-md's; copy review-md's over it");
});
