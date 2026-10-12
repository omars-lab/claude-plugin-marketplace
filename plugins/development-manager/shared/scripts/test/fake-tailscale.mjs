#!/usr/bin/env node
// A stand-in for Tailscale's command line, for the enable --phone tests. Point
// PAGE_COMMENTS_TAILSCALE at this file. All data is invented.
//
//   FAKE_TAILSCALE_STATE  a JSON file: { status: <status --json>, serve: <serve status --json> }
//   FAKE_TAILSCALE_LOG    every call's arguments, one JSON array per line
//
// It answers `status --json`, `serve status --json`, `serve --bg --https=<port> <target>`
// and `serve --https=<port> off`, changing the serve state the way Tailscale does.
// Anything else, Funnel above all, fails loudly.

import { appendFileSync, readFileSync, writeFileSync } from "node:fs";

const args = process.argv.slice(2);
const statePath = process.env.FAKE_TAILSCALE_STATE;
if (process.env.FAKE_TAILSCALE_LOG) appendFileSync(process.env.FAKE_TAILSCALE_LOG, JSON.stringify(args) + "\n");
const state = JSON.parse(readFileSync(statePath, "utf8"));
const save = () => writeFileSync(statePath, JSON.stringify(state, null, 2));
const fail = (msg) => {
  process.stderr.write(`fake tailscale: ${msg}\n`);
  process.exit(1);
};
const said = args.join(" ");

if (/funnel/i.test(said)) fail("funnel was called");
if (said === "status --json") {
  process.stdout.write(JSON.stringify(state.status));
} else if (said === "serve status --json") {
  process.stdout.write(state.serve && Object.keys(state.serve).length ? JSON.stringify(state.serve) : "{}");
} else if (args[0] === "serve" && args[1] === "--bg" && /^--https=\d+$/.test(args[2]) && args.length === 4) {
  const port = args[2].slice("--https=".length);
  const host = state.status.Self.DNSName.replace(/\.$/, "");
  state.serve = state.serve || {};
  state.serve.TCP = { ...state.serve.TCP, [port]: { HTTPS: true } };
  state.serve.Web = { ...state.serve.Web, [`${host}:${port}`]: { Handlers: { "/": { Proxy: args[3] } } } };
  save();
  process.stdout.write(`Available within your tailnet:\n\nhttps://${host}:${port}/\n|-- proxy ${args[3]}\n\nTo disable the proxy, run: tailscale serve --https=${port} off\n`);
} else if (args[0] === "serve" && /^--https=\d+$/.test(args[1]) && args[2] === "off" && args.length === 3) {
  const port = args[1].slice("--https=".length);
  const host = state.status.Self.DNSName.replace(/\.$/, "");
  if (state.serve && state.serve.TCP) delete state.serve.TCP[port];
  if (state.serve && state.serve.Web) delete state.serve.Web[`${host}:${port}`];
  save();
} else {
  fail(`not something the fake knows: ${said}`);
}
