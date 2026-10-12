# Bundled libraries

The comment bar draws each comment's element to a picture in the page. It uses one library,
shipped here so the page never loads code from a CDN (design section 6).

| File | Library | Version | Licence | Where it came from |
|---|---|---|---|---|
| `modern-screenshot.js` | modern-screenshot | 4.7.0 (published 2026-04-16) | MIT, in `modern-screenshot.LICENSE` | `dist/index.js` from `npm pack modern-screenshot@4.7.0`, unchanged |

- **Global name:** the file is a UMD build. Loaded as a plain script it sets
  `window.modernScreenshot`. The bar checks for that name after loading and records a failed
  shot if it is missing (a page with its own AMD `define` would take the library instead).
- **sha256 of the file:** `bb36665889124a0b6e15f16045265737449c3bdcf2712cdb08af3cfa01563e2b`.
- **Served at:** `/__page-comments/vendor/modern-screenshot.js`, by the comment server.
- **Only this file.** The package's `worker.js` is not shipped; the bar does not use workers.

To update: `npm pack modern-screenshot@<version>` into an empty scratch folder, copy
`dist/index.js` and `LICENSE` here under the names above, and update this table and the hash.
