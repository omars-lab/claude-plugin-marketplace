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
//
// The phone (design section 13): `tailscale serve` takes HTTPS on the Mac's
// tailnet name and passes it to this server on 127.0.0.1. config.json's
// `phone` block ({ host, port, logins, authors }) lets that name through the
// Host check, and the matching `https://` Origin through the write check.
// Tailscale keeps the Host the phone sent (`<host>:<port>`, checked
// 2026-10-12), and replaces any Tailscale-User-Login the phone sends with the
// real login. Every request that came that way (the phone Host, or any
// Tailscale-User-Login header) must carry a login on the allow list, or it is
// refused, page loads included. The login names the comment's author.
//
// Screenshots (design section 14): the page sends the picture of a thread's
// element as a PNG body, with the same token and Origin checks as any write.
// The server names the file and picks its folder. A picture is read back by an
// <img>, which cannot send a header, so that one GET takes the token in the
// query string instead.

import { createServer, request as httpRequest } from "node:http";
import { request as httpsRequest } from "node:https";
import { connect } from "node:net";
import { randomBytes, timingSafeEqual } from "node:crypto";
import { createReadStream, readFileSync, rmSync, statSync, writeFileSync, mkdirSync, realpathSync } from "node:fs";
import { dirname, extname, join, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { paths, readConfig } from "./repo.mjs";
import { addReply, ANCHOR_STATES, cleanAnchor, cleanBody, cleanPage, cleanViewport, createThread, isThreadId, publicThread, readAll, readThread, setAnchorState, setStatus, STATUSES } from "./store.mjs";
import { hasCommentShot, isPng, isShotName, recordShotError, saveShot, shotFileState, shotPath, SHOT_MAX } from "./shots.mjs";
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

/** Read a raw body of at most `limit` bytes. Past the limit the request is refused (413). */
function readRaw(req, limit) {
  return new Promise((resolveBody, reject) => {
    const tooLarge = () => Object.assign(new Error("too large"), { status: 413 });
    if (Number(req.headers["content-length"]) > limit) return reject(tooLarge());
    const chunks = [];
    let size = 0;
    let done = false;
    req.on("data", (c) => {
      if (done) return;
      size += c.length;
      if (size > limit) {
        // Stop keeping it; the answer goes out with "connection: close".
        done = true;
        chunks.length = 0;
        return reject(tooLarge());
      }
      chunks.push(c);
    });
    req.on("end", () => {
      if (!done) resolveBody(Buffer.concat(chunks));
    });
    req.on("error", reject);
  });
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

/**
 * The phone block of config.json, cleaned: { host, port, hosts, logins, authors }
 * or null when the phone is off or the block is unusable. `hosts` are the Host
 * headers accepted for it: `<host>:<port>` as Tailscale passes it on, and the
 * bare name too when the port is 443, since a browser leaves out the default port.
 */
export function phoneSetting(config) {
  const p = config && config.phone;
  if (!p || typeof p !== "object") return null;
  const host = typeof p.host === "string" ? p.host.trim().toLowerCase().replace(/\.$/, "") : "";
  const port = Number(p.port);
  if (!/^[a-z0-9-]+(\.[a-z0-9-]+)+$/.test(host) || !Number.isInteger(port) || port < 1 || port > 65535) return null;
  const logins = Array.isArray(p.logins) ? p.logins.filter((l) => typeof l === "string" && l.trim()).map((l) => l.trim().toLowerCase()) : [];
  const authors = {};
  if (p.authors && typeof p.authors === "object") {
    for (const [k, v] of Object.entries(p.authors)) if (typeof v === "string" && v.trim()) authors[k.trim().toLowerCase()] = v.trim();
  }
  const hosts = [`${host}:${port}`].concat(port === 443 ? [host] : []);
  return { host, port, hosts, logins, authors };
}

/**
 * Who is asking, and may they. `localHosts` are this server's own Host values;
 * `phone` is phoneSetting(config) or null; `author` the repo's author.
 * Returns { ok: true, via: "local"|"tailscale", origin, author } or
 * { ok: false, status, reason, error }. `origin` is the only Origin a write may carry.
 */
export function whoIsAsking(headers, { localHosts, phone, author }) {
  const host = String(headers.host || "").toLowerCase();
  const local = localHosts.has(host);
  const viaPhone = !!(phone && phone.hosts.includes(host));
  if (!local && !viaPhone) return { ok: false, status: 403, reason: "host", error: "wrong host" };
  const raw = headers["tailscale-user-login"];
  // A login header on a local request did not come from Tailscale, which sends
  // the phone's Host. It is held to the same allow list all the same, so an
  // unknown one is refused and a known one is only the author it would be anyway.
  if (!viaPhone && raw === undefined) return { ok: true, via: "local", origin: `http://${host}`, author };
  const login = typeof raw === "string" ? raw.trim().toLowerCase() : "";
  if (!login) return { ok: false, status: 403, reason: "no_login", error: "no Tailscale login on this request; only signed-in people on the allow list can comment from the phone" };
  if (!phone || !phone.logins.includes(login)) return { ok: false, status: 403, reason: "login_not_allowed", login, error: "this Tailscale login is not on the repo's allow list" };
  return { ok: true, via: "tailscale", origin: viaPhone ? `https://${host}` : `http://${host}`, author: phone.authors[login] || author, login };
}

/** A short fingerprint of the store, so the page can ask "anything new?" cheaply. */
function storeVersion(threads) {
  let n = 0;
  // `events` counts every line, so a "not found" report or a landed commit
  // changes the fingerprint too, and open pages pick it up.
  for (const t of threads) n += (t.events || 0) * 13 + t.messages.length * 7 + t.history.length * 3 + t.shots.length * 11 + t.messages.reduce((s, m) => s + m.body.length, 0);
  return `${threads.length}.${n}`;
}

/**
 * Start the server. Options: { target, root, port, host }.
 * Resolves to { url, port, token, close() }.
 */
export function startServer(store, { target, root, port = 8766, record = true } = {}) {
  const token = randomBytes(16).toString("hex");
  const log = fileLogger(paths(store).serverLog);
  const targetUrl = target ? new URL(target) : null;
  const rootDir = root ? realpathSync(resolve(store.repo, root)) : null;
  let allowedHosts = new Set();

  // config.json is read again when it changes, so `enable --phone` takes effect
  // without a restart.
  let config = { stamp: null, author: "me", phone: null };
  function settings() {
    let stamp = null;
    try {
      const st = statSync(paths(store).config);
      stamp = `${st.mtimeMs}:${st.size}`;
    } catch {
      stamp = "none";
    }
    if (stamp !== config.stamp) {
      const c = readConfig(store);
      config = { stamp, author: typeof c.author === "string" && c.author ? c.author : "me", phone: phoneSetting(c) };
    }
    return config;
  }

  /** whoIsAsking for this request, logging any refusal. */
  function ask(req) {
    const s = settings();
    const who = whoIsAsking(req.headers, { localHosts: allowedHosts, phone: s.phone, author: s.author });
    if (!who.ok) log("reject", { reason: who.reason, host: String(req.headers.host || ""), ...(who.login ? { login: who.login } : {}) });
    return who;
  }

  // ---- The comment API ------------------------------------------------------------

  async function api(req, res, path, who) {
    const author = who.author;
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
    // From the phone the page is https://<tailnet name>:<port>, so that is its Origin.
    if (req.headers.origin !== who.origin) return sendJson(res, 403, { error: "wrong origin" });
    const shot = /^threads\/([^/]+)\/shot$/.exec(path);
    if (shot) return await postShot(req, res, shot[1], author);
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
      log("thread_new", { thread: id, page: cleanPage(body.page).path, via: who.via });
      return sendJson(res, 201, { thread: publicThread(readThread(store, id)) });
    }
    const m = /^threads\/([^/]+)\/(replies|status|anchor)$/.exec(path);
    if (!m || !isThreadId(m[1])) return sendJson(res, 404, { error: "not found" });
    const id = m[1];
    if (!readThread(store, id)) return sendJson(res, 404, { error: `no thread ${id}` });
    if (m[2] === "replies") {
      const text = cleanBody(body.body);
      if (!text) return sendJson(res, 400, { error: "a reply needs text, up to 10,000 characters" });
      addReply(store, id, { author, body: text });
      log("reply", { thread: id });
    } else if (m[2] === "anchor") {
      // The page reports whether it found the element. Only a change from the
      // last report is written, so reloading the page adds nothing.
      if (!ANCHOR_STATES.includes(body.state)) return sendJson(res, 400, { error: "state is lost or found" });
      const t = readThread(store, id);
      if (!!t.lost === (body.state === "lost")) return sendJson(res, 200, { changed: false, thread: publicThread(t) });
      setAnchorState(store, id, { author, state: body.state });
      log("anchor", { thread: id, state: body.state });
    } else {
      if (!STATUSES.includes(body.status)) return sendJson(res, 400, { error: "status is open, resolved or dismissed" });
      const note = typeof body.note === "string" && body.note.trim() ? body.note.slice(0, 10000) : undefined;
      setStatus(store, id, { author, status: body.status, note });
      log("status", { thread: id, status: body.status });
    }
    return sendJson(res, 200, { thread: publicThread(readThread(store, id)) });
  }

  /**
   * The comment's own picture, sent by the page after the comment saves: a PNG
   * body, or a JSON `{ "error": "<why>" }` when the capture failed. Only the
   * thread's first message gets a picture, so a second one is refused (409).
   */
  async function postShot(req, res, id, author) {
    if (!isThreadId(id)) return sendJson(res, 404, { error: "not found" });
    if (!readThread(store, id)) return sendJson(res, 404, { error: `no thread ${id}` });
    const type = req.headers["content-type"] || "";
    const json = /^application\/json\b/i.test(type);
    if (!json && !/^image\/png\b/i.test(type)) return sendJson(res, 415, { error: "send a PNG picture, or JSON with an error" });
    let body;
    try {
      body = json ? await readBody(req) : await readRaw(req, SHOT_MAX);
    } catch (err) {
      res.setHeader("connection", "close");
      return sendJson(res, err.status || 400, { error: err.status === 413 ? `the picture is over ${SHOT_MAX / 1024 / 1024} MB` : "could not read the picture" });
    }
    if (hasCommentShot(readThread(store, id))) return sendJson(res, 409, { error: "this thread already has its picture" });
    if (json) {
      let reason;
      try {
        reason = JSON.parse(body).error;
      } catch {
        return sendJson(res, 400, { error: "not JSON" });
      }
      if (typeof reason !== "string" || !reason.trim()) return sendJson(res, 400, { error: "say why the capture failed in `error`" });
      recordShotError(store, id, { role: "comment", reason, author });
      log("shot_error", { thread: id, msg: reason.slice(0, 200) });
      return sendJson(res, 200, { thread: publicThread(readThread(store, id)) });
    }
    if (!isPng(body)) return sendJson(res, 400, { error: "not a PNG picture" });
    let e;
    try {
      e = saveShot(store, id, body, { role: "comment", author });
    } catch (err) {
      log("shot_error", { thread: id, msg: err.message });
      recordShotError(store, id, { role: "comment", reason: `the server could not save it: ${err.message}`, author });
      return sendJson(res, 500, { error: "could not save the picture" });
    }
    log("shot", { thread: id, sha: e.sha, kind: e.icloud ? "icloud" : "local" });
    return sendJson(res, 201, { thread: publicThread(readThread(store, id)) });
  }

  /**
   * GET /__page-comments/shots/<thread-id>/<name>?token=…  A picture, read only
   * from where one of that thread's own `shot` events points.
   */
  function getShot(req, res, rest, query) {
    if (req.method !== "GET" && req.method !== "HEAD") return sendJson(res, 405, { error: "method not allowed" });
    if (!sameToken(query.get("token"), token)) return sendJson(res, 403, { error: "missing or wrong token" });
    const m = /^shots\/([^/]+)\/([^/]+)$/.exec(rest);
    if (!m || !isThreadId(m[1]) || !isShotName(m[2])) return sendJson(res, 404, { error: "not found" });
    const [, id, name] = m;
    const thread = readThread(store, id);
    if (!thread) return sendJson(res, 404, { error: "not found" });
    // The newest shot with this name wins (an after shot can be retaken).
    const shot = [...thread.shots].reverse().find((s) => !s.error && (s.icloud || s.local || "").split("/").pop() === name);
    const file = shot && shotPath(store, shot);
    if (!file || shotFileState(file) !== "ok") return sendJson(res, 404, { error: "the picture is not on this Mac" });
    let data;
    try {
      data = readFileSync(file);
    } catch {
      return sendJson(res, 404, { error: "the picture is not on this Mac" });
    }
    res.writeHead(200, { "content-type": "image/png", "content-length": data.length, "cache-control": "no-store", "x-content-type-options": "nosniff" });
    res.end(req.method === "HEAD" ? undefined : data);
  }

  // What the page loads from this server. client.js is the Files link helper
  // and the text matcher, followed by the bar itself, so the bar is one request.
  const CLIENT_FILES = {
    "client.js": ["files-link.js", "text-match.js", "comments.js"],
    "client.css": ["comments.css"],
    "vendor/modern-screenshot.js": ["vendor/modern-screenshot.js"],
  };

  function clientFile(res, name) {
    const files = CLIENT_FILES[name];
    if (!files) return sendJson(res, 404, { error: "not found" });
    let data;
    try {
      data = Buffer.concat(files.map((f) => readFileSync(join(CLIENT_DIR, f))));
    } catch {
      return sendJson(res, 404, { error: "client file missing" });
    }
    res.writeHead(200, { "content-type": MIME[extname(name)], "content-length": data.length, "cache-control": "no-store" });
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
    const who = ask(req);
    if (!who.ok) return sendJson(res, who.status, { error: who.error });
    const pathname = req.url.split("?")[0];
    try {
      if (pathname.startsWith(PREFIX)) {
        const rest = pathname.slice(PREFIX.length);
        if (Object.hasOwn(CLIENT_FILES, rest)) return clientFile(res, rest);
        if (rest.startsWith("shots/")) return getShot(req, res, rest, new URL(req.url, "http://x").searchParams);
        if (rest === "health") return sendJson(res, 200, { ok: true, mode: targetUrl ? "proxy" : "folder" });
        if (rest === "threads" || rest.startsWith("threads/")) return await api(req, res, rest, who);
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
    if (!targetUrl || !ask(req).ok) {
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
