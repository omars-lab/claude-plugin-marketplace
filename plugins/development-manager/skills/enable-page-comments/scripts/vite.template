// Page comments in Vite's dev server, written by development-manager's
// enable-page-comments. The repo's vite.config uses it:
//   import pageComments from "./.page-comments/vite.mjs";
//   plugins: [pageComments(), …]
// It finds the installed plugin the way `.page-comments/run` does. Where the
// plugin is not installed it does nothing, with one warning in `vite dev`, so
// builds and other machines are not affected. It never runs in `vite build`.
// Remove it with the enable script's --undo.
import { existsSync, readFileSync } from "node:fs";
import { homedir } from "node:os";
import { dirname, join } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const ENTRY = join("shared", "scripts", "vite.mjs");

function pluginRoot() {
  // 1. Where the plugin was when enable ran on this machine.
  try {
    const r = readFileSync(join(here, ".state", "plugin-root"), "utf8").trim();
    if (r && existsSync(join(r, ENTRY))) return r;
  } catch {}
  // 2. Otherwise, where Claude Code installed it (a fresh clone has no .state/).
  try {
    const f = join(process.env.CLAUDE_CONFIG_DIR || join(homedir(), ".claude"), "plugins", "installed_plugins.json");
    const all = JSON.parse(readFileSync(f, "utf8")).plugins || {};
    for (const [id, list] of Object.entries(all)) {
      if (!id.startsWith("development-manager@")) continue;
      for (const p of list) if (p && p.installPath && existsSync(join(p.installPath, ENTRY))) return p.installPath;
    }
  } catch {}
  return null;
}

export default function pageComments(options = {}) {
  const root = pluginRoot();
  if (!root) {
    return {
      name: "development-manager:page-comments (not installed)",
      apply: "serve",
      configureServer(server) {
        server.config.logger.warn("page comments: the development-manager plugin is not installed on this machine, so there is no comment bar.");
      },
    };
  }
  // Vite waits for a promise in the plugins list.
  return import(pathToFileURL(join(root, ENTRY)).href).then((m) => m.default({ repo: dirname(here), ...options }));
}
