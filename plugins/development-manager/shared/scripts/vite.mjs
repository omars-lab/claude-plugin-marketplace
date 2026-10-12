// The dev-only Vite plugin (design section 3, phase 5): the comment bar in
// Vite's own dev server, with no second port. It does two things only:
//   - adds the same script tag the comment server adds, to each HTML page Vite
//     serves (transformIndexHtml);
//   - answers /__page-comments/ with the same request handler as the comment
//     server (lib/server.mjs createHandler), so the Host, Origin and token
//     checks are the same ones.
// `apply: "serve"` keeps it out of `vite build` and `vite preview`. It imports
// nothing from Vite. A repo's vite.config loads it through the small
// `.page-comments/vite.mjs` that `enable.mjs --vite` writes, which finds the
// installed plugin the way `.page-comments/run` does.
//
// Options: { repo } names the repo; without it `.page-comments/` is looked for
// from Vite's root up to the git root. With no `.page-comments/` the plugin
// does nothing and says so once.

import { randomBytes } from "node:crypto";
import { fileLogger } from "./lib/log.mjs";
import { findStore, paths, storeFor } from "./lib/repo.mjs";
import { createHandler, injectTag } from "./lib/server.mjs";

/** Host values the dev server answers to as itself: the port the request came in on. */
function localHostsOf(req) {
  const port = req.socket && req.socket.localPort;
  return new Set(port ? [`127.0.0.1:${port}`, `localhost:${port}`, `[::1]:${port}`] : []);
}

export default function pageComments(options = {}) {
  const token = randomBytes(16).toString("hex");
  let store = options.repo ? storeFor(options.repo) : null;
  let handler = null;
  return {
    name: "development-manager:page-comments",
    apply: "serve",
    configResolved(config) {
      if (!store && !options.repo) store = findStore(config.root);
    },
    configureServer(server) {
      if (!store) {
        server.config.logger.warn("page comments: no .page-comments/ folder for this Vite root, so there is no comment bar. Run /development-manager:enable-page-comments to turn it on.");
        return;
      }
      const log = fileLogger(paths(store).serverLog);
      handler = createHandler(store, { token, log, localHosts: localHostsOf, mode: "vite" });
      log("start", { mode: "vite", root: server.config.root });
      // Added straight away, not returned, so it runs before Vite's own
      // middleware and Vite never sees a /__page-comments/ request.
      server.middlewares.use((req, res, next) => {
        handler.handle(req, res).then((done) => {
          if (!done) next();
        }, next);
      });
    },
    transformIndexHtml(html) {
      return handler ? injectTag(html, token) : html;
    },
  };
}
