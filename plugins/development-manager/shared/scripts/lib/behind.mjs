// serve --behind: the comment server starts the repo's own page server on a spare
// port behind it, so one command gives the pages with the comment button.
// The command gets the port as {port} in its text and as PORT in its environment.

import { spawn } from "node:child_process";
import { connect, createServer } from "node:net";

/** A port the OS says is free on 127.0.0.1 right now. */
export function freePort() {
  return new Promise((resolve, reject) => {
    const s = createServer();
    s.once("error", reject);
    s.listen(0, "127.0.0.1", () => {
      const { port } = s.address();
      s.close(() => resolve(port));
    });
  });
}

function accepts(port) {
  return new Promise((resolve) => {
    const sock = connect(port, "127.0.0.1");
    const done = (ok) => {
      sock.destroy();
      resolve(ok);
    };
    sock.once("connect", () => done(true));
    sock.once("error", () => done(false));
    sock.setTimeout(500, () => done(false));
  });
}

/**
 * Start `command` with {port} filled in. It runs in its own process group, so
 * a stop reaches the shell and everything it started (a command may be
 * `make site && python3 serve.py`), and only this process decides when it stops.
 * Resolves once the port takes connections; rejects if the command exits
 * first or the port is still closed after `timeoutMs`.
 * Resolves to { child, port, exited } where `exited` resolves to the exit code.
 */
export async function startBehind(command, { cwd, port, timeoutMs = 30000, stdio = ["ignore", "inherit", "inherit"] } = {}) {
  const line = command.split("{port}").join(String(port));
  const child = spawn("sh", ["-c", line], { cwd, stdio, detached: true, env: { ...process.env, PORT: String(port) } });
  const kill = (signal) => {
    try {
      process.kill(-child.pid, signal);
    } catch {
      // already gone
    }
  };
  // If this process dies without stopping it, take the page server down with it.
  const onExit = () => kill("SIGTERM");
  process.once("exit", onExit);
  let code = null;
  const exited = new Promise((resolve) => {
    child.once("exit", (c, signal) => {
      // Stopped by Ctrl-C or a plain stop counts as a clean exit; another signal does not.
      code = c !== null ? c : signal === "SIGINT" || signal === "SIGTERM" ? 0 : 128;
      process.removeListener("exit", onExit);
      resolve(code);
    });
    child.once("error", () => {
      code = 127;
      resolve(code);
    });
  });
  // A stop while it is still starting: a signal ends this process without an
  // "exit" event, so stop the page server here, then let the signal end us.
  const onSignal = (signal) => {
    kill("SIGTERM");
    process.removeListener("exit", onExit);
    process.kill(process.pid, signal);
  };
  process.once("SIGINT", onSignal);
  process.once("SIGTERM", onSignal);
  const until = Date.now() + timeoutMs;
  try {
    for (;;) {
      if (code !== null) throw Object.assign(new Error(`the page server stopped before it was ready (exit ${code}): ${line}`), { exitCode: code });
      if (await accepts(port)) return { child, port, exited, line, kill };
      if (Date.now() > until) {
        kill("SIGTERM");
        throw Object.assign(new Error(`the page server did not open port ${port} within ${Math.round(timeoutMs / 1000)} s: ${line}`), { exitCode: 1 });
      }
      await new Promise((r) => setTimeout(r, 150));
    }
  } finally {
    process.removeListener("SIGINT", onSignal);
    process.removeListener("SIGTERM", onSignal);
  }
}

/** Stop the page server and wait for it, with a hard stop after `graceMs`. */
export async function stopBehind(b, graceMs = 5000) {
  if (!b || b.child.exitCode !== null || b.child.signalCode !== null) return;
  b.kill("SIGTERM");
  const t = setTimeout(() => b.kill("SIGKILL"), graceMs);
  await b.exited;
  clearTimeout(t);
}
