// The comment server: one Node server on 127.0.0.1, in one of two modes.
//
//   --target <url>   sits in front of a server that is already running, and
//                    passes every request through to it;
//   --root <dir>     serves a folder of files itself.
//
// Either way it adds one script tag to each HTML page, and answers the comment
// API under /__page-comments/. Section 9 of the design lists the guards:
//   - every request: the Host must be this server's own (stops DNS rebinding);
//   - API calls: a per-run token, and for writes an Origin equal to this
//     server's own and a JSON content type (stops other sites and other tabs).
// Requests passed through to the target get only the Host check, so the
// target's own API (a PUT from its page, say) keeps working unchanged.

import { createServer, request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { connect } from "node:net";
import { randomBytes, timingSafeEqual } from "node:crypto";
import { createReadStream, readFileSync, rmSync, statSync, writeFileSync, mkdirSync, realpathSync } from "node:fs";
import { dirname, extname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { paths, readConfig } from "./repo.mjs";
import { addReply, cleanAnchor, cleanBody, cleanPage, cleanViewport, createThread, isThreadId, publicThread, readAll, readThread, setStatus, STATUSES } from "./store.mjs";
import { gitStamp } from "./git.mjs";
import { fileLogger, nowIso } from "./log.mjs";

const CLIENT_DIR = join(dirname(fileURLToPath(import.meta.url)), "..", "client");
export const PREFIX = "/__page-comments/";
const BODY_LIMIT = 64 * 1024;

const MIME = {
  ".html": "text/html; charset=utf-8",
  ".htm": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "text/javascript; charset=utf-8",
  ".mjs": "text/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".svg": "image/svg+xml",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".gif": "image/gif",
  ".webp": "image/webp",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
  ".md": "text/plain; charset=utf-8",
  ".woff": "font/woff",
  ".woff2": "font/woff2",
  ".pdf": "application/pdf",
  ".map": "application/json; charset=utf-8",
};

/** The tag added to every HTML page. */
export function scriptTag(token) {
  return `<script src="${PREFIX}client.js" data-token="${token}" defer></script>`;
}

/** Add the tag before the last `</body>`, or at the end when there is none. */
export function injectTag(html, token) {
  const tag = scriptTag(token);
  const i = html.toLowerCase().lastIndexOf("</body>");
  return i >= 0 ? html.slice(0, i) + tag + html.slice(i) : html + tag;
}

const isHtml = (type) => /^\s*text\/html\b/i.test(type || "");

function sendJson(res, code, body) {
  const data = Buffer.from(JSON.stringify(body));
  res.writeHead(code, { "content-type": "application/json; charset=utf-8", "content-length": data.length, "cache-control": "no-store" });
  res.end(data);
}

function sameToken(a, b) {
  if (typeof a !== "string" || a.length !== b.length) return false;
  return timingSafeEqual(Buffer.from(a), Buffer.from(b));
}

function readBody(req) {
  return new Promise((resolveBody, reject) => {
    const chunks = [];
    let size = 0;
    // Past the limit, the rest is read and thrown away, so the answer (413)
    // still reaches the page instead of a cut connection.
    req.on("data", (c) => {
      size += c.length;
      if (size <= BODY_LIMIT) chunks.push(c);
    });
    req.on("end", () => {
      if (size > BODY_LIMIT) reject(Object.assign(new Error("too large"), { status: 413 }));
      else resolveBody(Buffer.concat(chunks).toString("utf8"));
    });
    req.on("error", reject);
  });
}

/** A short fingerprint of the store, so the page can ask "anything new?" cheaply. */
function storeVersion(threads) {
  let n = 0;
  for (const t of threads) n += t.messages.length * 7 + t.history.length * 3 + t.messages.reduce((s, m) => s + m.body.length, 0);
  return `${threads.length}.${n}`;
}

/**
 * Start the server. Options: { target, root, port, host }.
 * Resolves to { url, port, token, close() }.
 */
export function startServer(store, { target, root, port = 8766, record = true } = {}) {
  const token = randomBytes(16).toString("hex");
  const log = fileLogger(paths(store).serverLog);
  const config = readConfig(store);
  const author = typeof config.author === "string" && config.author ? config.author : "me";
  const targetUrl = target ? new URL(target) : null;
  const rootDir = root ? realpathSync(resolve(store.repo, root)) : null;
  let allowedHosts = new Set();

  const hostOk = (req) => allowedHosts.has(String(req.headers.host || "").toLowerCase());

  // ---- The comment API ------------------------------------------------------------

  async function api(req, res, path) {
    if (!sameToken(req.headers["x-page-comments-token"], token)) return sendJson(res, 403, { error: "missing or wrong token" });
    const url = new URL(req.url, "http://x");
    if (req.method === "GET" && path === "threads") {
      const page = url.searchParams.get("page");
      const all = readAll(store);
      const version = storeVersion(all);
      if (url.searchParams.get("since") === version) return sendJson(res, 200, { version, changed: false });
      const threads = all.filter((t) => !page || t.page.path === page).map(publicThread);
      return sendJson(res, 200, { version, changed: true, author, threads });
    }
    if (req.method !== "POST") return sendJson(res, 405, { error: "method not allowed" });
    // Writes: the Origin must be this server's own, and the body JSON. A JSON
    // content type makes the browser ask first for any cross-site call, and this
    // server answers no such ask, so the browser never sends the write.
    if (req.headers.origin !== `http://${req.headers.host}`) return sendJson(res, 403, { error: "wrong origin" });
    if (!/^application\/json\b/i.test(req.headers["content-type"] || "")) return sendJson(res, 415, { error: "send JSON" });
    let body;
    try {
      body = JSON.parse(await readBody(req));
    } catch (err) {
      return sendJson(res, err.status || 400, { error: err.status === 413 ? "too large" : "not JSON" });
    }
    if (!body || typeof body !== "object") return sendJson(res, 400, { error: "send an object" });

    if (path === "threads") {
      const text = cleanBody(body.body);
      if (!text) return sendJson(res, 400, { error: "a comment needs text, up to 10,000 characters" });
      const bodyHash = typeof body.bodyHash === "string" && /^[0-9a-f]{12}$/.test(body.bodyHash) ? body.bodyHash : null;
      const id = createThread(store, {
        author,
        page: cleanPage(body.page),
        viewport: cleanViewport(body.viewport),
        anchor: cleanAnchor(body.anchor),
        rev: { bodyHash, ts: nowIso(), git: gitStamp(store.repo) },
        body: text,
      });
      log("thread_new", { thread: id, page: cleanPage(body.page).path });
      return sendJson(res, 201, { thread: publicThread(readThread(store, id)) });
    }
    const m = /^threads\/([^/]+)\/(replies|status)$/.exec(path);
    if (!m || !isThreadId(m[1])) return sendJson(res, 404, { error: "not found" });
    const id = m[1];
    if (!readThread(store, id)) return sendJson(res, 404, { error: `no thread ${id}` });
    if (m[2] === "replies") {
      const text = cleanBody(body.body);
      if (!text) return sendJson(res, 400, { error: "a reply needs text, up to 10,000 characters" });
      addReply(store, id, { author, body: text });
      log("reply", { thread: id });
    } else {
      if (!STATUSES.includes(body.status)) return sendJson(res, 400, { error: "status is open, resolved or dismissed" });
      const note = typeof body.note === "string" && body.note.trim() ? body.note.slice(0, 10000) : undefined;
      setStatus(store, id, { author, status: body.status, note });
      log("status", { thread: id, status: body.status });
    }
    return sendJson(res, 200, { thread: publicThread(readThread(store, id)) });
  }

  function clientFile(res, name) {
    const file = { "client.js": "comments.js", "client.css": "comments.css" }[name];
    if (!file) return sendJson(res, 404, { error: "not found" });
    let data;
    try {
      data = readFileSync(join(CLIENT_DIR, file));
    } catch {
      return sendJson(res, 404, { error: "client file missing" });
    }
    res.writeHead(200, { "content-type": MIME[extname(file)], "content-length": data.length, "cache-control": "no-store" });
    res.end(data);
  }

  // ---- Serving pages ----------------------------------------------------------------

  function sendHtml(res, status, headers, html) {
    const data = Buffer.from(injectTag(html, token));
    const h = { ...headers };
    for (const k of Object.keys(h)) {
      // The page changed size and is new on every run: drop length, encoding,
      // and cache validators, so the browser never reuses a copy with an old token.
      if (/^(content-length|transfer-encoding|etag|last-modified|content-encoding)$/i.test(k)) delete h[k];
    }
    h["content-length"] = data.length;
    h["cache-control"] = "no-store";
    res.writeHead(status, h);
    res.end(data);
  }

  function proxy(req, res) {
    const headers = { ...req.headers, host: targetUrl.host, "accept-encoding": "identity" };
    // An HTML page cached under an old token would fail every API call, so ask
    // for a fresh copy instead of a "not modified".
    delete headers["if-none-match"];
    delete headers["if-modified-since"];
    const send = targetUrl.protocol === "https:" ? httpsRequest : httpRequest;
    const up = send(
      { protocol: targetUrl.protocol, hostname: targetUrl.hostname, port: targetUrl.port, method: req.method, path: req.url, headers },
      (upRes) => {
        const type = upRes.headers["content-type"];
        const encoded = upRes.headers["content-encoding"] && upRes.headers["content-encoding"] !== "identity";
        if (isHtml(type) && !encoded && req.method !== "HEAD") {
          const chunks = [];
          upRes.on("data", (c) => chunks.push(c));
          upRes.on("end", () => sendHtml(res, upRes.statusCode, upRes.headers, Buffer.concat(chunks).toString("utf8")));
          upRes.on("error", () => res.destroy());
          return;
        }
        res.writeHead(upRes.statusCode, upRes.rawHeaders.length ? rawToObject(upRes.rawHeaders) : upRes.headers);
        upRes.pipe(res);
      },
    );
    up.on("error", (err) => {
      log("target_error", { code: err.code || "error", path: req.url.split("?")[0] });
      if (!res.headersSent) sendJson(res, 502, { error: `the page server at ${targetUrl.origin} did not answer (${err.code || err.message})` });
      else res.destroy();
    });
    req.pipe(up);
  }

  function serveFile(req, res) {
    if (req.method !== "GET" && req.method !== "HEAD") return sendJson(res, 405, { error: "method not allowed" });
    let rel;
    try {
      rel = decodeURIComponent(new URL(req.url, "http://x").pathname);
    } catch {
      return sendJson(res, 400, { error: "bad path" });
    }
    if (rel.includes("\0")) return sendJson(res, 400, { error: "bad path" });
    let file = resolve(rootDir, `.${rel}`);
    if (file !== rootDir && !file.startsWith(rootDir + sep)) return sendJson(res, 403, { error: "outside the folder" });
    let st;
    try {
      st = statSync(file);
      if (st.isDirectory()) {
        if (!rel.endsWith("/")) {
          res.writeHead(301, { location: `${rel}/` });
          return res.end();
        }
        file = join(file, "index.html");
        st = statSync(file);
      }
      // A link inside the folder that points outside it is refused too.
      const real = realpathSync(file);
      if (real !== rootDir && !real.startsWith(rootDir + sep)) return sendJson(res, 403, { error: "outside the folder" });
    } catch {
      return sendJson(res, 404, { error: "not found" });
    }
    const type = MIME[extname(file).toLowerCase()] || "application/octet-stream";
    if (isHtml(type) && req.method === "GET") return sendHtml(res, 200, { "content-type": type }, readFileSync(file, "utf8"));
    res.writeHead(200, { "content-type": type, "content-length": st.size, "cache-control": "no-cache" });
    if (req.method === "HEAD") return res.end();
    createReadStream(file).pipe(res);
  }

  // ---- The server ---------------------------------------------------------------------

  const server = createServer(async (req, res) => {
    if (!hostOk(req)) {
      log("reject", { reason: "host", host: String(req.headers.host || "") });
      return sendJson(res, 403, { error: "wrong host" });
    }
    const pathname = req.url.split("?")[0];
    try {
      if (pathname.startsWith(PREFIX)) {
        const rest = pathname.slice(PREFIX.length);
        if (rest === "client.js" || rest === "client.css") return clientFile(res, rest);
        if (rest === "health") return sendJson(res, 200, { ok: true, mode: targetUrl ? "proxy" : "folder" });
        if (rest === "threads" || rest.startsWith("threads/")) return await api(req, res, rest);
        return sendJson(res, 404, { error: "not found" });
      }
      return targetUrl ? proxy(req, res) : serveFile(req, res);
    } catch (err) {
      log("error", { msg: err && err.message });
      if (!res.headersSent) sendJson(res, 500, { error: "server error" });
      else res.destroy();
    }
  });

  // Live-reload sockets and other upgrades go straight through to the target.
  const sockets = new Set();
  server.on("upgrade", (req, socket, head) => {
    if (!hostOk(req) || !targetUrl) {
      socket.end("HTTP/1.1 403 Forbidden\r\n\r\n");
      return;
    }
    const up = connect(Number(targetUrl.port) || (targetUrl.protocol === "https:" ? 443 : 80), targetUrl.hostname, () => {
      const lines = [`${req.method} ${req.url} HTTP/${req.httpVersion}`];
      for (let i = 0; i < req.rawHeaders.length; i += 2) {
        const k = req.rawHeaders[i];
        lines.push(`${k}: ${k.toLowerCase() === "host" ? targetUrl.host : req.rawHeaders[i + 1]}`);
      }
      up.write(lines.join("\r\n") + "\r\n\r\n");
      if (head && head.length) up.write(head);
      up.pipe(socket);
      socket.pipe(up);
    });
    sockets.add(socket);
    const end = () => {
      sockets.delete(socket);
      up.destroy();
      socket.destroy();
    };
    // Either side closing ends both, so no socket is left half open.
    for (const s of [up, socket]) {
      s.on("error", end);
      s.on("end", end);
      s.on("close", end);
    }
  });

  return new Promise((resolveStart, reject) => {
    server.once("error", reject);
    server.listen(port, "127.0.0.1", () => {
      const actual = server.address().port;
      allowedHosts = new Set([`127.0.0.1:${actual}`, `localhost:${actual}`, `[::1]:${actual}`]);
      const url = `http://127.0.0.1:${actual}/`;
      const statePath = paths(store).server;
      if (record) try {
        mkdirSync(dirname(statePath), { recursive: true });
        writeFileSync(statePath, JSON.stringify({ pid: process.pid, port: actual, url, mode: targetUrl ? "proxy" : "folder", target: target || null, root: root || null, started: nowIso() }));
      } catch {
        // the state file is a convenience for --undo and --check; serving still works
      }
      log("start", { port: actual, mode: targetUrl ? "proxy" : "folder", target: target || "", root: root || "" });
      resolveStart({
        url,
        port: actual,
        token,
        close: () =>
          new Promise((done) => {
            try {
              const s = JSON.parse(readFileSync(statePath, "utf8"));
              if (s.pid === process.pid && s.port === actual) rmSync(statePath, { force: true });
            } catch {
              // already gone
            }
            log("stop", { port: actual });
            for (const s of sockets) s.destroy();
            server.close(() => done());
            if (server.closeAllConnections) server.closeAllConnections();
          }),
      });
    });
  });
}

function rawToObject(raw) {
  // Keep repeated headers (Set-Cookie) as arrays, as Node's writeHead expects.
  const out = {};
  for (let i = 0; i < raw.length; i += 2) {
    const k = raw[i];
    const v = raw[i + 1];
    if (out[k] === undefined) out[k] = v;
    else if (Array.isArray(out[k])) out[k].push(v);
    else out[k] = [out[k], v];
  }
  return out;
}
