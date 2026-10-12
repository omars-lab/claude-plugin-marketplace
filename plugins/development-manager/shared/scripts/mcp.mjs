#!/usr/bin/env node
// page-comments-mcp: the page-comments command line as MCP tools (design section 3,
// phase 5), for agent hosts without a shell.
//
// A thin shell over page-comments.mjs (next to this file), shaped like review-md's
// reviews-mcp.mjs: each tool call runs one command and returns what it printed, so
// the command line stays the one place the logic lives. MCP over stdio
// (newline-delimited JSON-RPC); Node 18, no dependencies. The repo is found from the
// folder the host starts the server in, as the command line finds it, unless a tool
// call names one with `repo`.

import { execFile } from "node:child_process";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { createInterface } from "node:readline";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const CLI = join(here, "page-comments.mjs");
const PROTOCOL = "2025-06-18";

let version = "0.0.0";
try {
  version = JSON.parse(readFileSync(join(here, "..", "..", ".claude-plugin", "plugin.json"), "utf8")).version;
} catch {
  // Run from outside the plugin: the version is only informational.
}

const str = (description) => ({ type: "string", description });
const bool = (description) => ({ type: "boolean", description });
const REPO = str("The repo with .page-comments/ (default: found from the working folder)");
const ID = str("Thread id, like t_8f3a2c, as list prints it");
const AUTHOR = str('Who it is from (default "claude")');
const COMMIT = str("The commit that has the change, when there is one");

/** Each tool: what the agent sees, and how its arguments become command-line arguments. */
const TOOLS = {
  list: {
    description:
      "List the comment threads on this repo's local pages, grouped by page: where each is anchored, open/resolved/dismissed, who it waits on, and every message. Returns JSON in review-md's shape.",
    properties: {
      open: bool("Open threads only"),
      waiting: str('Only threads waiting on "claude" or on "human"'),
      page: str("Only threads on this page path, like /trips/"),
      repo: REPO,
    },
    required: [],
    argv: (a) => ["list", "--json", ...flags(a, ["open", "waiting", "page", "repo"])],
  },
  show: {
    description: "One thread in full, as JSON, with the file path of each picture on this machine.",
    properties: { id: ID, repo: REPO },
    required: ["id"],
    argv: (a) => ["show", "--json", ...flags(a, ["repo"]), "--", a.id],
  },
  stats: {
    description: "Open, waiting-on-Claude, resolved and dismissed thread counts per page.",
    properties: { repo: REPO },
    required: [],
    argv: (a) => ["stats", "--json", ...flags(a, ["repo"])],
  },
  reply: {
    description: "Reply to a thread. The page shows it straight away. Returns once the reply is written.",
    properties: { id: ID, message: str("The reply"), author: AUTHOR, commit: COMMIT, repo: REPO },
    required: ["id", "message"],
    argv: (a) => ["reply", ...flags(a, ["author", "commit", "repo"]), "--", a.id, a.message],
  },
  resolve: {
    description: "Resolve a thread once it is answered or fixed, or reopen it.",
    properties: { id: ID, note: str("A short note on what was done"), reopen: bool("Reopen instead of resolving"), author: AUTHOR, repo: REPO },
    required: ["id"],
    argv: (a) => ["resolve", ...flags(a, ["reopen", "author", "repo"]), "--", a.id, ...(a.note ? [a.note] : [])],
  },
  dismiss: {
    description: "Close a thread without a change: not an issue, or will not do.",
    properties: { id: ID, note: str("Why"), author: AUTHOR, repo: REPO },
    required: ["id"],
    argv: (a) => ["dismiss", ...flags(a, ["author", "repo"]), "--", a.id, ...(a.note ? [a.note] : [])],
  },
  shot: {
    description: "Attach an \"after\" picture (a PNG file on this machine) to a thread, taken against a commit.",
    properties: { id: ID, file: str("Path to the PNG"), commit: str("The commit the picture was taken against"), author: AUTHOR, repo: REPO },
    required: ["id", "file", "commit"],
    argv: (a) => ["shot", ...flags(a, ["file", "commit", "author", "repo"]), "--", a.id],
  },
};

/** Command-line flags for the given argument names: booleans as bare flags, the rest with a value. */
function flags(args, names) {
  const out = [];
  for (const n of names) {
    const v = args[n];
    if (v === undefined || v === null || v === false || v === "") continue;
    out.push(`--${n}`, ...(v === true ? [] : [String(v)]));
  }
  return out;
}

export function callTool(name, args = {}) {
  const tool = Object.prototype.hasOwnProperty.call(TOOLS, name) ? TOOLS[name] : null;
  if (!tool) return Promise.resolve({ content: [{ type: "text", text: `no tool "${name}"` }], isError: true });
  args = args && typeof args === "object" ? args : {};
  const missing = tool.required.filter((k) => args[k] === undefined || args[k] === "");
  if (missing.length) return Promise.resolve({ content: [{ type: "text", text: `missing: ${missing.join(", ")}` }], isError: true });
  return new Promise((done) => {
    execFile(process.execPath, [CLI, ...tool.argv(args)], { timeout: 60_000, maxBuffer: 32 * 1024 * 1024 }, (err, stdout, stderr) => {
      const text = (err ? [stderr.trim(), stdout.trim()].filter(Boolean).join("\n") || err.message : stdout).trimEnd();
      done({ content: [{ type: "text", text }], isError: !!err });
    });
  });
}

async function handle(msg) {
  switch (msg.method) {
    case "initialize":
      return {
        protocolVersion: (msg.params && msg.params.protocolVersion) || PROTOCOL,
        capabilities: { tools: {} },
        serverInfo: { name: "page-comments", version },
        instructions:
          "Comment threads left on this repo's local pages with development-manager's page comments. Read with list/show/stats; answer with reply, resolve, dismiss and shot.",
      };
    case "ping":
      return {};
    case "tools/list":
      return {
        tools: Object.entries(TOOLS).map(([name, t]) => ({
          name,
          description: t.description,
          inputSchema: { type: "object", properties: t.properties, required: t.required, additionalProperties: false },
        })),
      };
    case "tools/call":
      return callTool(msg.params && msg.params.name, msg.params && msg.params.arguments);
    default:
      throw Object.assign(new Error(`method not found: ${msg.method}`), { code: -32601 });
  }
}

const send = (obj) => process.stdout.write(JSON.stringify({ jsonrpc: "2.0", ...obj }) + "\n");

if (process.argv[1] && fileURLToPath(import.meta.url) === process.argv[1]) {
  createInterface({ input: process.stdin }).on("line", async (line) => {
    if (!line.trim()) return;
    let msg;
    try {
      msg = JSON.parse(line);
    } catch {
      return send({ id: null, error: { code: -32700, message: "parse error" } });
    }
    if (!msg || msg.id === undefined) return; // A notification (e.g. notifications/initialized): nothing to answer.
    try {
      send({ id: msg.id, result: await handle(msg) });
    } catch (err) {
      send({ id: msg.id, error: { code: typeof err.code === "number" ? err.code : -32603, message: err.message } });
    }
  });
}
