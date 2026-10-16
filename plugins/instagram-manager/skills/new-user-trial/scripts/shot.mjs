// shot.mjs — serve a folder of pages on 127.0.0.1 and take a screenshot of one, for a trial diary.
//
//   node shot.mjs --root <dir> --page <path> --out <png> [--width 1280] [--height 800] [--full]
//                 [--playwright <playwright-core dir>] [--chrome <chrome binary>] [--wait 2500]
//                 [--fill <css selector> --text <words>] [--clip <css selector>]
//   node shot.mjs --root <dir> --list <jobs.json> [--playwright …] [--chrome …]
//
// --root   the folder to serve (the sandbox hub: <sandbox>/home/.cache/hub)
// --page   the page inside it, e.g. "/" or "/westmark/" or "/posts/DEMOa000001.html"
// --out    where the PNG goes (the sandbox's shots/ folder; never into git)
// --full   the whole page, not only the first screen
// --fill   type --text into the first box this selector finds before the picture, to see a
//          filter or search box at work (e.g. --fill "#find" --text "pasta")
// --clip   only the first element this selector finds, with 8 px around it (e.g. "#mini", the
//          small map on a place or post page: a map thumbnail)
// --list   many pictures with one browser: a JSON list of {page, out, clip?, width?, height?,
//          full?}; one ev=shot line per picture. A page that has no such element is skipped
//          with ev=shot_skip.
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
const list = opt("list");
if (!root || !(list || opt("out"))) {
  console.error("usage: node shot.mjs --root <dir> (--page <path> --out <png> | --list <jobs.json>) [--width N] [--height N] [--full] [--clip <selector>]");
  process.exit(2);
}
const jobs = list
  ? JSON.parse(await readFile(list, "utf8"))
  : [{ page: opt("page", "/"), out: opt("out"), clip: opt("clip"), full: args.includes("--full"),
       width: +opt("width", 1280), height: +opt("height", 800), fill: opt("fill"), text: opt("text", "") }];
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
const origin = `http://127.0.0.1:${server.address().port}`;

const browser = await chromium.launch({ executablePath: chrome });
let failed = 0;
try {
  for (const job of jobs) {
    const errors = [];
    let status = 0;
    const page = await browser.newPage({ viewport: { width: job.width || 1280, height: job.height || 800 } });
    page.on("pageerror", (e) => errors.push(e.message));
    page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
    try {
      const resp = await page.goto(origin + (job.page || "/"), { waitUntil: "domcontentloaded", timeout: 20000 });
      status = resp ? resp.status() : 0;
      await page.waitForTimeout(wait);
      if (job.fill) {
        await page.locator(job.fill).first().fill(job.text || "");
        await page.waitForTimeout(500);
      }
      let clip;
      if (job.clip) {
        // A thumbnail needs no zoom buttons.
        await page.addStyleTag({ content: ".leaflet-control-zoom{display:none!important}" });
        const box = await page.locator(job.clip).first().boundingBox().catch(() => null);
        if (!box) {
          console.log(`ev=shot_skip page=${job.page} clip=${job.clip} reason=no_element`);
          continue;
        }
        clip = { x: Math.max(0, box.x - 8), y: Math.max(0, box.y - 8), width: box.width + 16, height: box.height + 16 };
      }
      await page.screenshot({ path: job.out, fullPage: !!job.full && !clip, clip });
    } catch (e) {
      failed++;
      console.log(`ev=shot_fail page=${job.page} msg="${String(e.message).split("\n")[0].replace(/"/g, "'")}"`);
      continue;
    } finally {
      await page.close();
    }
    const shown = errors.slice(0, 3).map((e) => e.replace(/\s+/g, " ").slice(0, 120));
    console.log(`ev=shot out=${job.out} page=${job.page} status=${status} errors=${errors.length}` +
      (shown.length ? ` msg="${shown.join(" | ").replace(/"/g, "'")}"` : ""));
  }
} finally {
  await browser.close();
  server.close();
}
process.exit(failed ? 1 : 0);
