// The MCP server (shared/scripts/mcp.mjs): a real stdio round trip, the way an
// agent host talks to it, over a throwaway repo. All data here is invented.

import assert from "node:assert/strict";
import { spawn } from "node:child_process";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { createInterface } from "node:readline";
import { test } from "node:test";
import { createThread, readThread } from "../lib/store.mjs";
import { PLUGIN, SAMPLE, SCRIPTS, tempRepo } from "./helpers.mjs";

const MCP = join(SCRIPTS, "mcp.mjs");

/** Start the server in `cwd`; `rpc(method, params)` sends one request and waits for its answer. */
function startMcp(cwd) {
  const child = spawn(process.execPath, [MCP], { cwd, stdio: ["pipe", "pipe", "pipe"] });
  const waiting = new Map();
  const extra = [];
  createInterface({ input: child.stdout }).on("line", (line) => {
    const msg = JSON.parse(line);
    if (waiting.has(msg.id)) {
      waiting.get(msg.id)(msg);
      waiting.delete(msg.id);
    } else extra.push(msg);
  });
  let next = 1;
  return {
    extra,
    raw: (text) => child.stdin.write(text + "\n"),
    rpc: (method, params) =>
      new Promise((resolve, reject) => {
        const id = next++;
        const timer = setTimeout(() => reject(new Error(`no answer to ${method}`)), 20000);
        waiting.set(id, (m) => {
          clearTimeout(timer);
          resolve(m);
        });
        child.stdin.write(JSON.stringify({ jsonrpc: "2.0", id, method, params }) + "\n");
      }),
    stop: () =>
      new Promise((res) => {
        child.once("exit", res);
        child.stdin.end();
      }),
  };
}

const text = (r) => r.result.content[0].text;

test("initialize, tools/list, and each tool runs the command line", async () => {
  const { repo, store, cleanup } = tempRepo();
  const t = { id: createThread(store, { ...SAMPLE, body: "The walk time is missing." }) };
  const m = startMcp(repo);
  try {
    const init = await m.rpc("initialize", { protocolVersion: "2025-03-26", capabilities: {}, clientInfo: { name: "test", version: "0" } });
    assert.equal(init.result.protocolVersion, "2025-03-26", "it answers in the client's version");
    assert.equal(init.result.serverInfo.name, "page-comments");
    assert.equal(init.result.serverInfo.version, JSON.parse(readFileSync(join(PLUGIN, ".claude-plugin", "plugin.json"), "utf8")).version);
    assert.deepEqual(init.result.capabilities, { tools: {} });
    m.raw(JSON.stringify({ jsonrpc: "2.0", method: "notifications/initialized" }));
    assert.deepEqual((await m.rpc("ping")).result, {});

    const tools = (await m.rpc("tools/list")).result.tools;
    assert.deepEqual(tools.map((x) => x.name).sort(), ["dismiss", "list", "reply", "resolve", "shot", "show", "stats"]);
    for (const x of tools) assert.equal(x.inputSchema.additionalProperties, false, x.name);

    const list = await m.rpc("tools/call", { name: "list", arguments: { open: true } });
    assert.equal(list.result.isError, false);
    const listed = JSON.parse(text(list));
    assert.equal(listed.files[0].threads[0].id, t.id);

    const show = JSON.parse(text(await m.rpc("tools/call", { name: "show", arguments: { id: t.id } })));
    assert.equal(show.messages[0].body, "The walk time is missing.");

    const reply = await m.rpc("tools/call", { name: "reply", arguments: { id: t.id, message: "--not a flag: the walk is 20 minutes." } });
    assert.equal(reply.result.isError, false, text(reply));
    assert.equal(readThread(store, t.id).messages[1].body, "--not a flag: the walk is 20 minutes.", "a message that looks like a flag is still the message");
    assert.equal(readThread(store, t.id).messages[1].author, "claude");

    assert.equal((await m.rpc("tools/call", { name: "resolve", arguments: { id: t.id, note: "Added the time." } })).result.isError, false);
    assert.equal(readThread(store, t.id).status, "resolved");
    assert.equal((await m.rpc("tools/call", { name: "resolve", arguments: { id: t.id, reopen: true } })).result.isError, false);
    assert.equal(readThread(store, t.id).status, "open");
    assert.equal((await m.rpc("tools/call", { name: "dismiss", arguments: { id: t.id, author: "sam" } })).result.isError, false);
    assert.equal(readThread(store, t.id).status, "dismissed");

    const stats = JSON.parse(text(await m.rpc("tools/call", { name: "stats", arguments: {} })));
    assert.equal(stats.total.dismissed, 1);
  } finally {
    await m.stop();
    cleanup();
  }
});

test("errors come back as errors: a bad thread, a missing argument, no tool, no method, bad JSON", async () => {
  const { repo, cleanup } = tempRepo();
  const elsewhere = tempRepo({ comments: false });
  const m = startMcp(elsewhere.repo);
  try {
    const none = await m.rpc("tools/call", { name: "list", arguments: {} });
    assert.equal(none.result.isError, true, "no .page-comments/ where the host started it");
    assert.match(text(none), /not turned on/);
    const there = await m.rpc("tools/call", { name: "list", arguments: { repo } });
    assert.equal(there.result.isError, false, "repo names one");

    const bad = await m.rpc("tools/call", { name: "show", arguments: { id: "t_ffffff", repo } });
    assert.equal(bad.result.isError, true);
    assert.match(text(bad), /no thread t_ffffff/);
    const evil = await m.rpc("tools/call", { name: "show", arguments: { id: "../../etc/passwd", repo } });
    assert.equal(evil.result.isError, true);
    assert.match(text(evil), /not a thread id/);

    assert.match(text(await m.rpc("tools/call", { name: "reply", arguments: { id: "t_ffffff" } })), /missing: message/);
    assert.equal((await m.rpc("tools/call", { name: "delete", arguments: {} })).result.isError, true);
    assert.equal((await m.rpc("tools/call", { name: "toString", arguments: {} })).result.isError, true, "only its own tools");
    assert.equal((await m.rpc("resources/list")).error.code, -32601);

    m.raw("{not json");
    await new Promise((r) => setTimeout(r, 200));
    assert.equal(m.extra.length, 1);
    assert.equal(m.extra[0].id, null);
    assert.equal(m.extra[0].error.code, -32700);
  } finally {
    await m.stop();
    cleanup();
    elsewhere.cleanup();
  }
});

test(".mcp.json starts the server with node and the plugin's path as one argument", () => {
  const cfg = JSON.parse(readFileSync(join(PLUGIN, ".mcp.json"), "utf8"));
  assert.deepEqual(cfg.mcpServers["page-comments"], { command: "node", args: ["${CLAUDE_PLUGIN_ROOT}/shared/scripts/mcp.mjs"] });
});
