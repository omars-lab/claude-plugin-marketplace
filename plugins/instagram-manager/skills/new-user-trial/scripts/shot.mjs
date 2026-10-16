// shot.mjs — serve a folder of pages on 127.0.0.1 and take a screenshot of one, for a trial diary.
//
//   node shot.mjs --root <dir> --page <path> --out <png> [--width 1280] [--height 800] [--full]
//                 [--playwright <playwright-core dir>] [--chrome <chrome binary>] [--wait 2500]
//
// --root   the folder to serve (the sandbox hub: <sandbox>/home/.cache/hub)
// --page   the page inside it, e.g. "/" or "/westmark/" or "/posts/DEMOa000001.html"
// --out    where the PNG goes (the sandbox's shots/ folder; never into git)
// --full   the whole page, not only the first screen
//
// It serves on a free port it picks itself, so it never clashes with a server already running,
// and stops the server when the picture is taken. Map tiles and Leaflet come from the internet in
// the page itself; with no network the map is grey but the pins and lists still show.
// playwright-core is found through --playwright, else $PLAYWRIGHT_CORE, else a normal import.
// Prints one line: ev=shot out=<png> page=<path> status=<http status> errors=<console errors>.

import { createServer } from "node:http";
import { createRequire } from "node:module";
import { readFile, stat } from "node:fs/promises";
import { extname, join, normalize, resolve } from "node:path";

const args = process.argv.slice(2);
const opt = (name, dflt) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && i + 1 < args.length ? args[i + 1] : dflt;
};
const root = opt("root");
const pagePath = opt("page", "/");
const out = opt("out");
if (!root || !out) {
  console.error("usage: node shot.mjs --root <dir> --page <path> --out <png> [--width N] [--height N] [--full]");
  process.exit(2);
}
const width = +opt("width", 1280);
const height = +opt("height", 800);
const wait = +opt("wait", 2500);
const chrome = opt("chrome", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome");
const pwDir = opt("playwright", process.env.PLAYWRIGHT_CORE);

const require = createRequire(import.meta.url);
let chromium;
try {
  ({ chromium } = pwDir ? require(pwDir) : await import("playwright-core"));
} catch {
  console.error("shot: playwright-core not found; pass --playwright <dir> or set PLAYWRIGHT_CORE");
  process.exit(2);
}

const TYPES = { ".html": "text/html; charset=utf-8", ".css": "text/css", ".js": "text/javascript",
  ".json": "application/json", ".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg",
  ".gif": "image/gif", ".svg": "image/svg+xml", ".webp": "image/webp", ".mp4": "video/mp4" };
const base = resolve(root);

const server = createServer(async (req, res) => {
  let p = decodeURIComponent(new URL(req.url, "http://x").pathname);
  let file = normalize(join(base, p));
  if (!file.startsWith(base)) { res.writeHead(403).end(); return; }
  try {
    if ((await stat(file)).isDirectory()) file = join(file, "index.html");
    res.writeHead(200, { "content-type": TYPES[extname(file)] || "application/octet-stream" });
    res.end(await readFile(file));
  } catch {
    res.writeHead(404, { "content-type": "text/plain" }).end("not found");
  }
});
await new Promise((ok) => server.listen(0, "127.0.0.1", ok));
const url = `http://127.0.0.1:${server.address().port}${pagePath}`;

const browser = await chromium.launch({ executablePath: chrome });
const errors = [];
let status = 0;
try {
  const page = await browser.newPage({ viewport: { width, height } });
  page.on("pageerror", (e) => errors.push(e.message));
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  const resp = await page.goto(url, { waitUntil: "domcontentloaded", timeout: 20000 });
  status = resp ? resp.status() : 0;
  await page.waitForTimeout(wait);
  await page.screenshot({ path: out, fullPage: args.includes("--full") });
} finally {
  await browser.close();
  server.close();
}
const shown = errors.slice(0, 3).map((e) => e.replace(/\s+/g, " ").slice(0, 120));
console.log(`ev=shot out=${out} page=${pagePath} status=${status} errors=${errors.length}` +
  (shown.length ? ` msg="${shown.join(" | ").replace(/"/g, "'")}"` : ""));
