// Links that open a comment's picture in the Files app on an iPhone or iPad
// (design section 15). The server puts this file in front of comments.js, and
// the tests run it on its own, so it is kept free of anything page-specific.
//
// Files has no documented link scheme. It does answer `shareddocuments://`
// followed by the file's full path on the device, and iCloud Drive sits at
// /private/var/mobile/Library/Mobile Documents/com~apple~CloudDocs/ there. A
// shot's `icloud` pointer is relative to that folder, so the link is the two
// joined, with each part of the pointer URL-encoded (spaces become %20).
// Pictures kept on the Mac only (`local` pointers) get no links.

(function (root) {
  "use strict";
  var ICLOUD_ON_PHONE = "shareddocuments:///private/var/mobile/Library/Mobile%20Documents/com~apple~CloudDocs/";

  function encodePath(parts) {
    return parts.map(encodeURIComponent).join("/");
  }

  /** { file, folder } for an `icloud` pointer, or null for anything else. */
  function filesLinks(pointer) {
    if (typeof pointer !== "string" || !pointer || pointer.charAt(0) === "/") return null;
    var parts = pointer.split("/");
    for (var i = 0; i < parts.length; i++) if (!parts[i] || parts[i] === "." || parts[i] === "..") return null;
    if (parts.length < 2) return null;
    return {
      file: ICLOUD_ON_PHONE + encodePath(parts),
      folder: ICLOUD_ON_PHONE + encodePath(parts.slice(0, -1)) + "/",
    };
  }

  /** An iPhone or iPad. iPads say "Macintosh" by default, so a touch screen counts too. */
  function isAppleTouch(nav) {
    if (!nav) return false;
    var ua = String(nav.userAgent || "");
    if (/iPhone|iPad|iPod/.test(ua)) return true;
    return /Macintosh/.test(ua) && Number(nav.maxTouchPoints) > 1;
  }

  root.__pageCommentsFiles = { filesLinks: filesLinks, isAppleTouch: isAppleTouch };
})(typeof globalThis !== "undefined" ? globalThis : this);
