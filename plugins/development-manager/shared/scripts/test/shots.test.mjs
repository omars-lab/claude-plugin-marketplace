// Stage 2: pictures of the element. Upload, serving, where the folder is, the
// command line, watch, the Files links and enable. Every picture here goes to
// the fake iCloud Drive that helpers.mjs sets up; all data is invented.

import { test } from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readFileSync, readdirSync, renameSync, rmSync, writeFileSync } from "node:fs";
import { request } from "node:http";
import { homedir, tmpdir } from "node:os";
import { basename, join } from "node:path";
import { runInNewContext } from "node:vm";
import { startServer } from "../lib/server.mjs";
import { appendEvent, createThread, publicThread, readThread } from "../lib/store.mjs";
import { diffSnapshots, takeSnapshot } from "../lib/watch.mjs";
import {
  contractHome,
  defaultShotsDir,
  expandHome,
  globalConfigPath,
  icloudRoot,
  isShotName,
  recordShotError,
  saveShot,
  shotName,
  shotPath,
  shotTarget,
  shotsSetting,
} from "../lib/shots.mjs";
import { ENABLE, FAKE, FAKE_CONFIG, FAKE_ICLOUD, SAMPLE, SCRIPTS, cli, tempRepo } from "./helpers.mjs";

// A real 1x1 PNG, and the same bytes made bigger, so the magic bytes are right.
const PNG = Buffer.from("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==", "base64");
const sha12 = (buf) => createHash("sha256").update(buf).digest("hex").slice(0, 12);

/** One raw HTTP call with a Buffer or string body. */
function call(port, { method = "GET", path = "/", headers = {}, body } = {}) {
  return new Promise((resolve, reject) => {
    const req = request({ host: "127.0.0.1", port, method, path, headers: { host: `127.0.0.1:${port}`, ...headers }, setHost: false }, (res) => {
      const chunks = [];
      res.on("data", (c) => chunks.push(c));
      res.on("end", () => {
        const buf = Buffer.concat(chunks);
        let json = null;
        try {
          json = JSON.parse(buf.toString("utf8"));
        } catch {
          json = null;
        }
        resolve({ status: res.statusCode, headers: res.headers, buf, json });
      });
    });
    // A server that answers before the whole body is sent may close the socket.
    req.on("error", (e) => (e.code === "EPIPE" || e.code === "ECONNRESET" ? resolve({ status: 413, closed: true }) : reject(e)));
    if (body !== undefined) req.write(body);
    req.end();
  });
}

const pngHeaders = (port, token, extra = {}) => ({ origin: `http://127.0.0.1:${port}`, "content-type": "image/png", "x-page-comments-token": token, ...extra });

/** A temp repo with comments on, one thread, and a server in folder mode. */
async function withServer(fn) {
  const { repo, store, cleanup } = tempRepo();
  mkdirSync(join(repo, "site"));
  writeFileSync(join(repo, "site", "index.html"), "<body>x</body>");
  writeFileSync(join(repo, ".page-comments", "config.json"), JSON.stringify({ author: "sam" }));
  const id = createThread(store, SAMPLE);
  const s = await startServer(store, { root: "site", port: 0 });
  try {
    await fn({ repo, store, id, s, port: s.port, token: s.token });
  } finally {
    await s.close();
    cleanup();
  }
}

test("the tests never point at the real iCloud Drive or the real global config", () => {
  assert.equal(icloudRoot(), FAKE_ICLOUD);
  assert.equal(globalConfigPath(), FAKE_CONFIG);
  assert.ok(FAKE.startsWith(tmpdir()) || FAKE.startsWith("/private" + tmpdir()));
  assert.ok(!icloudRoot().startsWith(join(homedir(), "Library")));
});

test("upload: a PNG is saved and pointed at; bad pictures, a second picture and bad tokens are refused", async () => {
  await withServer(async ({ repo, store, id, port, token }) => {
    const path = `/__page-comments/threads/${id}/shot`;
    const post = (headers, body = PNG) => call(port, { method: "POST", path, headers, body });

    assert.equal((await post(pngHeaders(port, "0".repeat(32)))).status, 403, "wrong token");
    assert.equal((await post(pngHeaders(port, token, { origin: "http://evil.example" }))).status, 403, "another site");
    assert.equal((await post(pngHeaders(port, token, { "content-type": "image/jpeg" }))).status, 415);
    assert.equal((await post(pngHeaders(port, token), Buffer.from("GIF89a not a png at all"))).status, 400, "bad magic bytes");
    const big = Buffer.concat([PNG, Buffer.alloc(8 * 1024 * 1024)]);
    assert.equal((await post(pngHeaders(port, token, { "content-length": String(big.length) }), big)).status, 413, "over 8 MB");
    assert.equal((await call(port, { method: "POST", path: "/__page-comments/threads/t_ffffff/shot", headers: pngHeaders(port, token), body: PNG })).status, 404);
    assert.equal((await call(port, { method: "POST", path: "/__page-comments/threads/..%2f/shot", headers: pngHeaders(port, token), body: PNG })).status, 404);
    assert.deepEqual(readThread(store, id).shots, [], "nothing was written by the refused calls");

    // A failed capture is recorded, and does not stop a later picture.
    const failed = await post(pngHeaders(port, token, { "content-type": "application/json" }), JSON.stringify({ error: "the capture took longer than 8 seconds" }));
    assert.equal(failed.status, 200);
    assert.equal(failed.json.thread.shots[0].error, "the capture took longer than 8 seconds");
    assert.equal((await post(pngHeaders(port, token, { "content-type": "application/json" }), JSON.stringify({}))).status, 400, "an error needs a reason");

    const ok = await post(pngHeaders(port, token));
    assert.equal(ok.status, 201);
    const shot = ok.json.thread.shots.find((x) => !x.error);
    const want = `CloudDesktop/data/page-comments/${basename(repo)}/${id}/comment.png`;
    assert.deepEqual({ role: shot.role, author: shot.author, icloud: shot.icloud, sha: shot.sha }, { role: "comment", author: "sam", icloud: want, sha: sha12(PNG) });
    const file = join(FAKE_ICLOUD, ...want.split("/"));
    assert.deepEqual(readFileSync(file), PNG, "the picture landed in the shot folder");
    assert.deepEqual(readdirSync(join(file, "..")), ["comment.png"], "no temp file left behind");

    const again = await post(pngHeaders(port, token));
    assert.equal(again.status, 409, "one comment picture per thread");
    assert.equal((await post(pngHeaders(port, token, { "content-type": "application/json" }), JSON.stringify({ error: "late" }))).status, 409);
    assert.equal(readThread(store, id).shots.length, 2);
    const log = readFileSync(join(repo, ".page-comments", ".state", "server.log"), "utf8");
    assert.match(log, /ev=shot /);
    assert.ok(!log.includes(token));
  });
});

test("GET shots: only a thread's own picture, with the token, and never a path outside", async () => {
  await withServer(async ({ store, id, port, token }) => {
    saveShot(store, id, PNG, { role: "comment", author: "sam" });
    const url = (rest, t = token) => `/__page-comments/shots/${rest}${t === null ? "" : `?token=${t}`}`;
    const good = await call(port, { path: url(`${id}/comment.png`) });
    assert.equal(good.status, 200);
    assert.equal(good.headers["content-type"], "image/png");
    assert.equal(good.headers["cache-control"], "no-store");
    assert.deepEqual(good.buf, PNG);
    assert.equal((await call(port, { method: "HEAD", path: url(`${id}/comment.png`) })).status, 200);
    assert.equal((await call(port, { path: url(`${id}/comment.png`, null) })).status, 403, "no token");
    assert.equal((await call(port, { path: url(`${id}/comment.png`, "0".repeat(32)) })).status, 403, "wrong token");
    assert.equal((await call(port, { method: "POST", path: url(`${id}/comment.png`) })).status, 405);
    for (const rest of [
      `${id}/../${id}/comment.png`,
      `..%2f..%2fthreads/${id}.jsonl`,
      `${id}%2fcomment.png`,
      `${id}/%2e%2e%2fcomment.png`,
      `${id}/comment.jpg`,
      `${id}/x.png`,
      `${id}/after-zzzzzzz.png`,
      `${id}/after-1234567.png`,
      `t_ffffff/comment.png`,
      `T_ABC/comment.png`,
      `${id}`,
      `${id}/comment.png/x`,
    ]) {
      const r = await call(port, { path: url(rest) });
      assert.notEqual(r.status, 200, rest);
      assert.ok(!r.buf.equals(PNG), rest);
    }
    // A pointer that climbs out is never followed, even if it is in the file.
    const id2 = createThread(store, SAMPLE);
    writeFileSync(join(FAKE, "outside.png"), PNG);
    appendEvent(store, id2, { ev: "shot", role: "comment", author: "sam", icloud: `../${id2}/comment.png`, sha: sha12(PNG) });
    appendEvent(store, id2, { ev: "shot", role: "after", author: "claude", local: `../../outside/${id2}/after-1234567.png`, sha: sha12(PNG), commit: "1234567" });
    assert.equal((await call(port, { path: url(`${id2}/comment.png`) })).status, 404);
    assert.equal((await call(port, { path: url(`${id2}/after-1234567.png`) })).status, 404);
  });
});

test("the shot folder: repo config, then the global config, then iCloud Drive's CloudDesktop/data", () => {
  const { repo, store, cleanup } = tempRepo();
  const root = mkdtempSync(join(tmpdir(), "pc-root-"));
  const cfg = join(root, "global.json");
  const env = { PAGE_COMMENTS_ICLOUD_ROOT: join(root, "drive"), DEVELOPMENT_MANAGER_CONFIG: cfg };
  try {
    mkdirSync(join(root, "drive"));
    assert.deepEqual(shotsSetting(store, env), { dir: join(root, "drive", "CloudDesktop", "data"), from: "default" });
    assert.equal(defaultShotsDir(env), join(root, "drive", "CloudDesktop", "data"));
    let t = shotTarget(store, env);
    assert.equal(t.kind, "icloud");
    assert.equal(t.base, join(root, "drive", "CloudDesktop", "data", "page-comments", basename(repo)));

    writeFileSync(cfg, JSON.stringify({ shotsDir: join(root, "drive", "Shared") }));
    assert.deepEqual(shotsSetting(store, env), { dir: join(root, "drive", "Shared"), from: "global" });
    writeFileSync(join(store.dir, "config.json"), JSON.stringify({ shotsDir: join(root, "drive", "Mine") }));
    t = shotTarget(store, env);
    assert.deepEqual([t.kind, t.from, t.base], ["icloud", "repo", join(root, "drive", "Mine", "page-comments", basename(repo))]);

    // Outside iCloud Drive, or no iCloud Drive at all: pictures stay in the repo.
    writeFileSync(join(store.dir, "config.json"), JSON.stringify({ shotsDir: join(root, "elsewhere") }));
    t = shotTarget(store, env);
    assert.deepEqual([t.kind, t.base, t.reason], ["local", join(store.dir, "shots"), "the shot folder is not inside iCloud Drive"]);
    writeFileSync(join(store.dir, "config.json"), "{}");
    t = shotTarget(store, { ...env, PAGE_COMMENTS_ICLOUD_ROOT: join(root, "no-such-drive") });
    assert.deepEqual([t.kind, t.reason], ["local", "iCloud Drive is not on this Mac"]);

    // A local picture: .page-comments/shots/<id>/, pointer relative to .page-comments/.
    const id = createThread(store, SAMPLE);
    const e = saveShot(store, id, PNG, { role: "comment", author: "sam" }, { ...env, PAGE_COMMENTS_ICLOUD_ROOT: join(root, "no-such-drive") });
    assert.equal(e.local, `shots/${id}/comment.png`);
    assert.equal(e.icloud, undefined);
    assert.deepEqual(readFileSync(join(store.dir, "shots", id, "comment.png")), PNG);
    assert.equal(shotPath(store, readThread(store, id).shots[0]), join(store.dir, "shots", id, "comment.png"));
    assert.ok(!existsSync(join(root, "drive", "CloudDesktop")), "nothing was written to the drive");
  } finally {
    rmSync(root, { recursive: true, force: true });
    cleanup();
  }
});

test("paths are stored with ~, and names and pointers are checked", () => {
  assert.equal(contractHome(join(homedir(), "Library", "x")), "~/Library/x");
  assert.equal(expandHome("~/Library/x"), join(homedir(), "Library", "x"));
  assert.equal(contractHome("/opt/x"), "/opt/x");
  assert.equal(shotName("comment"), "comment.png");
  assert.equal(shotName("after", "9c41d0e2b7d3a41c"), "after-9c41d0e2b7d3.png");
  assert.throws(() => shotName("after", "not-a-sha"));
  assert.throws(() => shotName("after"));
  for (const n of ["comment.png", "after-9c41d0e.png", "after-9c41d0e2b7d3.png"]) assert.ok(isShotName(n), n);
  for (const n of ["../comment.png", "comment.PNG", "after-.png", "after-9c41d0e2b7d3a.png", "x.png", "comment.png/"]) assert.ok(!isShotName(n), n);
  const store = { repo: "/r", dir: "/r/.page-comments" };
  for (const icloud of ["/abs/t_abc123/comment.png", "a/../t_abc123/comment.png", "a//t_abc123/comment.png", "comment.png", "a/t_abc123/evil.sh", "a/nope/comment.png", "a\\t_abc123/comment.png"]) {
    assert.equal(shotPath(store, { icloud }), null, icloud);
  }
  assert.equal(shotPath(store, { icloud: "A B/t_abc123/comment.png" }), join(FAKE_ICLOUD, "A B", "t_abc123", "comment.png"));
});

test("the command line: shot attaches an after picture, show prints where pictures are", () => {
  const { repo, store, cleanup } = tempRepo();
  const pic = join(repo, "after.png");
  try {
    const id = createThread(store, SAMPLE);
    writeFileSync(pic, PNG);
    writeFileSync(join(repo, "not.png"), "plain text");
    const base = ["--repo", repo];
    assert.equal(cli(["shot", id, "--file", pic, ...base]).code, 2, "no commit");
    assert.equal(cli(["shot", id, "--commit", "9c41d0e", ...base]).code, 2, "no file");
    assert.equal(cli(["shot", id, "--file", pic, "--commit", "main", ...base]).code, 2, "not a sha");
    assert.equal(cli(["shot", id, "--file", join(repo, "not.png"), "--commit", "9c41d0e", ...base]).code, 2, "not a PNG");
    assert.equal(cli(["shot", id, "--file", join(repo, "missing.png"), "--commit", "9c41d0e", ...base]).code, 3);
    assert.equal(cli(["shot", "t_ffffff", "--file", pic, "--commit", "9c41d0e", ...base]).code, 3);
    assert.deepEqual(readThread(store, id).shots, []);

    const r = cli(["shot", id, "--file", pic, "--commit", "9c41d0e2b7d3a41c09e2", ...base]);
    assert.equal(r.code, 0, r.stderr);
    const want = join(FAKE_ICLOUD, "CloudDesktop", "data", "page-comments", basename(repo), id, "after-9c41d0e2b7d3.png");
    assert.deepEqual(readFileSync(want), PNG);
    assert.match(r.stdout, new RegExp(`after picture attached, sha ${sha12(PNG)}`));
    const s = readThread(store, id).shots[0];
    assert.deepEqual([s.role, s.author, s.commit, s.sha], ["after", "claude", "9c41d0e2b7d3a41c09e2", sha12(PNG)]);

    recordShotError(store, id, { role: "comment", reason: "the capture library did not load", author: "sam" });
    const text = cli(["show", id, ...base]);
    assert.equal(text.code, 0);
    assert.ok(text.stdout.includes(`file:    ${want}`), text.stdout);
    assert.match(text.stdout, /pointer: icloud:CloudDesktop\/data\/page-comments\//);
    assert.match(text.stdout, /failed: the capture library did not load/);
    const json = JSON.parse(cli(["show", id, "--json", ...base]).stdout);
    const after = json.shots.find((x) => x.role === "after");
    assert.equal(after.path, want);
    assert.equal(json.shots.find((x) => x.error).path, undefined);
    assert.match(cli(["--help"]).stdout, /shot <id> --file <png> --commit <sha>/);
  } finally {
    cleanup();
  }
});

test("watch: a new picture is ev=shot; one that is not on this Mac is ev=shot_missing", () => {
  const { store, cleanup } = tempRepo();
  try {
    const id = createThread(store, SAMPLE);
    const s0 = takeSnapshot(store);
    saveShot(store, id, PNG, { role: "comment", author: "sam" });
    const s1 = takeSnapshot(store);
    const [e] = diffSnapshots(s0, s1);
    const file = shotPath(store, readThread(store, id).shots[0]);
    assert.deepEqual(e, { ev: "shot", page: SAMPLE.page.path, thread: id, author: "sam", role: "comment", sha: sha12(PNG), path: file });
    assert.deepEqual(diffSnapshots(s1, takeSnapshot(store)), [], "nothing new, nothing printed");

    // iCloud evicts the file and leaves a .<name>.icloud placeholder.
    renameSync(file, join(file, "..", ".comment.png.icloud"));
    const s2 = takeSnapshot(store);
    assert.deepEqual(diffSnapshots(s1, s2).map((x) => [x.ev, x.state]), [["shot_missing", "placeholder"]]);
    writeFileSync(file, PNG);
    assert.deepEqual(diffSnapshots(s2, takeSnapshot(store)).map((x) => x.ev), ["shot"], "it came back");

    // A thread first seen with a missing picture, and a failed capture.
    const id2 = createThread(store, SAMPLE);
    const e2 = saveShot(store, id2, PNG, { role: "after", commit: "9c41d0e", author: "claude" });
    rmSync(join(FAKE_ICLOUD, ...e2.icloud.split("/")));
    recordShotError(store, id2, { role: "comment", reason: "timed out", author: "sam" });
    const fresh = diffSnapshots({}, takeSnapshot(store)).filter((x) => x.thread === id2);
    assert.deepEqual(fresh.map((x) => x.ev), ["thread_new", "shot_missing", "shot"]);
    assert.equal(fresh[1].state, "missing");
    assert.equal(fresh[1].commit, "9c41d0e");
    assert.equal(fresh[2].msg, "the capture failed: timed out");

    const once = cli(["watch", "--once", "--state", join(store.dir, ".state", "w.json"), "--repo", store.repo]);
    assert.equal(once.code, 0, once.stderr);
    assert.match(once.stdout, /ev=shot page=\S+ thread=\S+ author=sam role=comment sha=[0-9a-f]{12} path=/);
    assert.match(once.stdout, /ev=shot_missing /);
  } finally {
    cleanup();
  }
});

test("the Files links: shareddocuments:// plus the pointer, encoded; only on an iPhone or iPad", () => {
  const ctx = {};
  runInNewContext(readFileSync(join(SCRIPTS, "client", "files-link.js"), "utf8"), { globalThis: ctx });
  const { isAppleTouch } = ctx.__pageCommentsFiles;
  // Objects made inside the vm compare by value only once they are plain JSON.
  const filesLinks = (p) => JSON.parse(JSON.stringify(ctx.__pageCommentsFiles.filesLinks(p)));
  const base = "shareddocuments:///private/var/mobile/Library/Mobile%20Documents/com~apple~CloudDocs/";
  assert.deepEqual(filesLinks("CloudDesktop/data/page-comments/my site/t_abc123/comment.png"), {
    file: base + "CloudDesktop/data/page-comments/my%20site/t_abc123/comment.png",
    folder: base + "CloudDesktop/data/page-comments/my%20site/t_abc123/",
  });
  assert.equal(filesLinks("a/t_abc123/x#y?.png").file, base + "a/t_abc123/x%23y%3F.png");
  for (const bad of [null, "", "/abs/x.png", "a/../x.png", "a//x.png", "x.png", 3]) assert.equal(filesLinks(bad), null, String(bad));
  assert.equal(isAppleTouch({ userAgent: "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X)" }), true);
  assert.equal(isAppleTouch({ userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", maxTouchPoints: 5 }), true, "an iPad asking for the desktop site");
  assert.equal(isAppleTouch({ userAgent: "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", maxTouchPoints: 0 }), false);
  assert.equal(isAppleTouch({ userAgent: "Mozilla/5.0 (Linux; Android 14)", maxTouchPoints: 5 }), false);
  assert.equal(isAppleTouch(undefined), false);
});

function enable(args, repo) {
  const r = spawnSync(process.execPath, [ENABLE, ...args, "--repo", repo], { encoding: "utf8", timeout: 60000, env: { ...process.env, PAGE_COMMENTS_SKIP_CLAUDE: "1" } });
  return { code: r.status, stdout: r.stdout, stderr: r.stderr };
}

test("enable: --shots-dir is written with ~, the iCloud note is printed once, undo keeps every picture", () => {
  const { repo, store, cleanup } = tempRepo({ comments: false });
  try {
    mkdirSync(join(repo, "site"));
    writeFileSync(join(repo, "site", "index.html"), "<body><h1>Hi</h1></body>");
    const first = enable(["--root", "site"], repo);
    assert.equal(first.code, 0, first.stderr);
    const cfg = () => JSON.parse(readFileSync(join(store.dir, "config.json"), "utf8"));
    assert.equal(cfg().shotsDir, join(FAKE_ICLOUD, "CloudDesktop", "data"), "the default, with no prompt");
    assert.equal((first.stdout.match(/Apple's servers keep a copy/g) || []).length, 1);
    assert.equal((enable(["--root", "site"], repo).stdout.match(/Apple's servers keep a copy/g) || []).length, 0, "only once");

    // A folder under home is written with ~. It is outside the (fake) iCloud
    // Drive, so pictures stay in the repo, and nothing is made under home.
    const mine = join(homedir(), "pc-test-not-created", "shots");
    const second = enable(["--root", "site", "--shots-dir", mine], repo);
    assert.equal(second.code, 0, second.stderr);
    assert.equal(cfg().shotsDir, "~/pc-test-not-created/shots");
    assert.match(second.stdout, /screenshots go to \.page-comments\/shots\//);
    assert.ok(!existsSync(join(homedir(), "pc-test-not-created")));

    // One picture in the repo (the folder above is outside iCloud Drive), one
    // in the fake iCloud Drive. Both survive undo, even --purge.
    const local = createThread(store, SAMPLE);
    assert.ok(saveShot(store, local, PNG, { role: "comment", author: "sam" }).local);
    writeFileSync(join(store.dir, "config.json"), JSON.stringify({ ...cfg(), shotsDir: join(FAKE_ICLOUD, "CloudDesktop", "data") }));
    const cloud = saveShot(store, createThread(store, SAMPLE), PNG, { role: "comment", author: "sam" });
    assert.ok(cloud.icloud);
    const undo = enable(["--undo", "--purge", "--force"], repo);
    assert.equal(undo.code, 0, undo.stderr);
    assert.deepEqual(readFileSync(join(store.dir, "shots", local, "comment.png")), PNG, "local picture kept");
    assert.ok(existsSync(join(store.dir, ".gitignore")), "and the rule that keeps it out of git");
    assert.ok(!existsSync(join(store.dir, "threads")), "--purge still removed the threads");
    assert.deepEqual(readFileSync(join(FAKE_ICLOUD, ...cloud.icloud.split("/"))), PNG, "iCloud picture kept");
    assert.match(undo.stdout, /left alone/);
  } finally {
    cleanup();
  }
});

test("a thread with pictures fits the shared schema", () => {
  const schema = JSON.parse(readFileSync(join(SCRIPTS, "schema", "thread.schema.json"), "utf8"));
  const { store, cleanup } = tempRepo();
  try {
    const id = createThread(store, SAMPLE);
    saveShot(store, id, PNG, { role: "comment", author: "sam" });
    saveShot(store, id, PNG, { role: "after", commit: "9c41d0e", author: "claude" });
    recordShotError(store, id, { role: "after", reason: "no browser", author: "claude" });
    const t = JSON.parse(JSON.stringify(publicThread(readThread(store, id))));
    assert.equal(t.shots.length, 3);
    const item = schema.properties.shots.items;
    for (const s of t.shots) {
      for (const k of item.required) assert.ok(k in s, k);
      for (const k of Object.keys(s)) assert.ok(k in item.properties, `${k} is in the schema`);
      assert.ok(item.properties.role.enum.includes(s.role));
      assert.equal(["icloud", "local", "error"].filter((k) => k in s).length, 1, "exactly one of icloud, local, error");
    }
    assert.ok(!("shots" in publicThread(readThread(store, createThread(store, SAMPLE)))), "no pictures, no key");
  } finally {
    cleanup();
  }
});
