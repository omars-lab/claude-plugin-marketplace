// The comment bar the comment server adds to every page it serves.
// A classic script (not a module), loaded with `defer`, so that
// document.currentScript can read the per-run token from its own tag.
// Everything it draws lives in a shadow root, and all comment text is set with
// textContent, never as HTML.
//
// Pictures (design section 6): the click that picks an element also starts
// drawing it to a PNG with the bundled modern-screenshot, and the picture is
// sent after the comment saves. A slow or failed picture never holds up or
// fails the comment; after 8 seconds it is given up and the reason is sent
// instead. The server's served client.js starts with files-link.js, which
// defines window.__pageCommentsFiles (the Files app links on an iPhone).
(function () {
  "use strict";
  if (window.__pageComments) return;
  window.__pageComments = true;

  var me = document.currentScript;
  var TOKEN = (me && me.dataset.token) || "";
  var BASE = "/__page-comments/";
  var POLL_MS = 4000;
  var PATH = location.pathname;
  var DRAFT_KEY = "page-comments:draft:" + PATH;
  var SHOT_MS = 8000; // give up on a picture after this long
  var SHOT_PAD = 16; // CSS pixels of background around the element
  var SHOT_MAX_W = 600; // CSS pixels: wider elements are scaled down
  var FILES = window.__pageCommentsFiles || null;
  // A phone or tablet: no hover, no C key. Comment mode then picks on a tap and waits
  // for "Comment here", so a stray tap never opens a comment (design section 13).
  var TOUCH = !!(window.matchMedia && matchMedia("(pointer: coarse)").matches);
  var COMMENT_LABEL = TOUCH ? "Comment" : "Comment (C)";

  // ---- State ---------------------------------------------------------------------------
  var threads = [];
  var version = "";
  var mode = false; // comment mode: hovering outlines elements, a click pins a comment
  var showResolved = false;
  var hidden = false;
  var panelOpen = false;
  var openThreadId = null;
  var composer = null; // { anchor, el, rect }
  var hashes = {}; // thread id -> the element's current hash, when found

  // ---- Shadow root and bar ---------------------------------------------------------------
  var host = document.createElement("div");
  host.id = "__page-comments";
  host.setAttribute("data-page-comments", "");
  host.style.cssText = "position:absolute;top:0;left:0;width:0;height:0;z-index:2147483647;";
  var root = host.attachShadow({ mode: "open" });
  var css = document.createElement("link");
  css.rel = "stylesheet";
  css.href = BASE + "client.css";
  root.appendChild(css);

  function h(tag, attrs, kids) {
    var el = document.createElement(tag);
    if (attrs) {
      for (var k in attrs) {
        if (k === "text") el.textContent = attrs[k];
        else if (k === "on") for (var ev in attrs.on) el.addEventListener(ev, attrs.on[ev]);
        else el.setAttribute(k, attrs[k]);
      }
    }
    (kids || []).forEach(function (c) {
      if (c) el.appendChild(c);
    });
    return el;
  }

  var pins = h("div", { class: "pins" });
  var outline = h("div", { class: "outline", hidden: "" });
  var chip = h("div", { class: "chip", hidden: "" });
  var pop = h("div", { class: "pop", hidden: "", role: "dialog" });
  var panel = h("div", { class: "panel", hidden: "" });
  var btnComment = h("button", { type: "button", class: "primary", title: TOUCH ? "Comment on part of the page: tap Comment, tap the part, then Comment here" : "Comment on an element (C). Select text first to comment on the text.", text: COMMENT_LABEL });
  var btnSelection = h("button", { type: "button", class: "primary", hidden: "", text: "Comment on selection" });
  var btnHere = h("button", { type: "button", class: "primary here", hidden: "", text: "Comment here" });
  var btnOpen = h("button", { type: "button", text: "0 open" });
  var btnResolved = h("button", { type: "button", "aria-pressed": "false", text: "Show resolved" });
  var btnHide = h("button", { type: "button", title: "Hide the bar and pins", text: "Hide" });
  var status = h("span", { class: "status", role: "status" });
  var bar = h("div", { class: "bar" }, [btnComment, btnSelection, btnOpen, btnResolved, btnHide, status]);
  var tab = h("button", { type: "button", class: "tab", hidden: "", title: "Show page comments", text: "Comments" });
  root.appendChild(pins);
  root.appendChild(outline);
  root.appendChild(chip);
  root.appendChild(btnHere);
  root.appendChild(pop);
  root.appendChild(panel);
  root.appendChild(bar);
  root.appendChild(tab);

  btnComment.addEventListener("click", function () {
    // On touch the button only turns comment mode on and off; selected text has its own button.
    if (TOUCH || !startTextComment()) setMode(!mode);
  });
  // Keep the page's selection when the button is pressed with a mouse; a tap may still
  // clear it, so the click uses the range saved when the selection was made.
  btnSelection.addEventListener("mousedown", function (e) {
    e.preventDefault();
  });
  btnSelection.addEventListener("click", function () {
    var range = lastRange;
    hideSelectionButton();
    if (range) {
      setMode(false);
      startTextComment(range);
    }
  });
  btnHere.addEventListener("click", function () {
    var p = picked;
    setMode(false);
    if (p) openComposer(p.anchor, p.el);
  });
  btnOpen.addEventListener("click", function () {
    panelOpen = !panelOpen;
    render();
  });
  btnResolved.addEventListener("click", function () {
    showResolved = !showResolved;
    render();
  });
  btnHide.addEventListener("click", function () {
    hidden = true;
    setMode(false);
    closePop();
    render();
  });
  tab.addEventListener("click", function () {
    hidden = false;
    render();
  });

  // ---- Talking to the server -------------------------------------------------------------
  function call(method, path, body) {
    var opts = { method: method, headers: { "X-Page-Comments-Token": TOKEN }, credentials: "same-origin" };
    if (body !== undefined) {
      opts.headers["Content-Type"] = "application/json";
      opts.body = JSON.stringify(body);
    }
    return fetch(BASE + path, opts).then(function (r) {
      return r.json().then(function (j) {
        if (!r.ok) throw new Error(j.error || "HTTP " + r.status);
        return j;
      });
    });
  }

  function say(text) {
    status.textContent = text || "";
  }

  function poll() {
    return call("GET", "threads?page=" + encodeURIComponent(PATH) + "&since=" + encodeURIComponent(version))
      .then(function (r) {
        if (r.changed) {
          threads = r.threads || [];
          version = r.version;
        }
        say("");
        // Rebuild only when something changed. Rebuilding every poll swaps the pins
        // out from under the pointer, so a click can miss and a scrolled list resets.
        if (!drawn || r.changed || layoutKey() !== lastLayout) render();
      })
      .catch(function (e) {
        say("Comments are offline: " + e.message);
      });
  }

  function upsert(t) {
    var i = threads.findIndex(function (x) {
      return x.id === t.id;
    });
    if (i >= 0) threads[i] = t;
    else threads.push(t);
    version = "";
  }

  // ---- Anchors: several ways to find the element again -------------------------------
  var clean = function (s) {
    return String(s || "").replace(/\s+/g, " ").trim();
  };

  function labelOf(el) {
    var a = el.getAttribute && el.getAttribute("aria-label");
    var s = clean(a || el.innerText || el.textContent || "");
    return s.length > 80 ? s.slice(0, 80) : s;
  }

  function stableId(id) {
    // Ids that look generated (long numbers, framework prefixes) change between builds.
    return id && !/\d{4,}|^[0-9]|[:]|^(ember|react|radix|mui|headlessui)/i.test(id) && document.querySelectorAll("#" + CSS.escape(id)).length === 1;
  }

  /** CSS path from <body>: a stable id ends it; otherwise tag:nth-of-type(n). */
  function cssPath(el) {
    var parts = [];
    while (el && el !== document.body && el.nodeType === 1) {
      if (stableId(el.id)) {
        parts.unshift("#" + CSS.escape(el.id));
        return parts.join(" > ");
      }
      var tag = el.tagName.toLowerCase();
      var n = 1;
      for (var s = el.previousElementSibling; s; s = s.previousElementSibling) if (s.tagName === el.tagName) n++;
      parts.unshift(tag + ":nth-of-type(" + n + ")");
      el = el.parentElement;
    }
    return parts.join(" > ");
  }

  function byCss(css) {
    if (!css) return document.body;
    try {
      return css.charAt(0) === "#" ? document.querySelector(css) : document.body.querySelector(":scope > " + css);
    } catch (e) {
      return null;
    }
  }

  function textIndex() {
    var nodes = [];
    var text = "";
    var w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, {
      acceptNode: function (n) {
        var p = n.parentElement;
        if (!p || host.contains(p) || /^(SCRIPT|STYLE|NOSCRIPT|TEMPLATE)$/.test(p.tagName)) return NodeFilter.FILTER_REJECT;
        return NodeFilter.FILTER_ACCEPT;
      },
    });
    for (var n = w.nextNode(); n; n = w.nextNode()) {
      nodes.push({ node: n, start: text.length });
      text += n.data;
    }
    return { nodes: nodes, text: text };
  }

  function elementAt(idx, pos) {
    var hit = null;
    for (var i = 0; i < idx.nodes.length && idx.nodes[i].start <= pos; i++) hit = idx.nodes[i];
    return hit ? hit.node.parentElement : null;
  }

  function byQuote(q) {
    if (!q || !q.exact) return null;
    var idx = textIndex();
    var full = (q.prefix || "") + q.exact + (q.suffix || "");
    var at = idx.text.indexOf(full);
    if (at >= 0) return elementAt(idx, at + (q.prefix || "").length);
    at = idx.text.indexOf(q.exact);
    if (at >= 0 && idx.text.indexOf(q.exact, at + 1) < 0) return elementAt(idx, at);
    return null;
  }

  function byLabel(tag, label) {
    if (!tag || !label) return null;
    var hits = Array.prototype.filter.call(document.querySelectorAll(tag), function (el) {
      return !host.contains(el) && labelOf(el) === label;
    });
    return hits.length === 1 ? hits[0] : null;
  }

  /** Try each anchor in order. Never guess: no match means "not found on this page". */
  function locate(a) {
    if (!a) return null;
    if (a.commentId) {
      try {
        var byId = document.querySelector('[data-comment-id="' + CSS.escape(a.commentId) + '"]');
        if (byId) return byId;
      } catch (e) {
        /* fall through */
      }
    }
    var el = byCss(a.css);
    if (el && el.tagName.toLowerCase() === (a.tag || el.tagName.toLowerCase()) && (!a.label || labelOf(el) === a.label)) return el;
    el = byQuote(a.quote);
    if (el) return a.type === "text" ? el : el.closest(a.tag || "*") || el;
    return byLabel(a.tag, a.label);
  }

  function quoteFor(range) {
    var exact = range.toString();
    var idx = textIndex();
    var start = -1;
    for (var i = 0; i < idx.nodes.length; i++) {
      if (idx.nodes[i].node === range.startContainer) {
        start = idx.nodes[i].start + range.startOffset;
        break;
      }
    }
    if (start < 0) start = idx.text.indexOf(exact);
    return {
      exact: exact.slice(0, 2000),
      prefix: start > 0 ? idx.text.slice(Math.max(0, start - 32), start) : "",
      suffix: start >= 0 ? idx.text.slice(start + exact.length, start + exact.length + 32) : "",
    };
  }

  function anchorFor(el, type, quote, evt) {
    var r = el.getBoundingClientRect();
    var a = {
      type: type,
      commentId: el.getAttribute("data-comment-id") || null,
      css: cssPath(el),
      tag: el.tagName.toLowerCase(),
      label: labelOf(el),
    };
    if (quote) a.quote = quote;
    if (evt && r.width && r.height) a.box = { fx: round((evt.clientX - r.left) / r.width), fy: round((evt.clientY - r.top) / r.height) };
    return a;
  }

  var round = function (x) {
    return Math.max(0, Math.min(1, Math.round(x * 100) / 100));
  };

  /** First 12 hex of sha256 over the element's text and tag outline (design section 4). */
  function hashOf(el) {
    if (!window.crypto || !crypto.subtle || !el) return Promise.resolve(null);
    var outlineTags = [];
    var all = el.getElementsByTagName("*");
    for (var i = 0; i < all.length && i < 2000; i++) outlineTags.push(all[i].tagName.toLowerCase());
    var data = new TextEncoder().encode(clean(el.textContent) + "\n" + el.tagName.toLowerCase() + ">" + outlineTags.join(","));
    return crypto.subtle.digest("SHA-256", data).then(
      function (buf) {
        return Array.prototype.map
          .call(new Uint8Array(buf), function (b) {
            return ("0" + b.toString(16)).slice(-2);
          })
          .join("")
          .slice(0, 12);
      },
      function () {
        return null;
      },
    );
  }

  // ---- Comment mode ------------------------------------------------------------------------
  var hoverEl = null;
  var picked = null; // touch: { el, anchor } chosen by a tap, waiting for "Comment here"
  var lastPointer = ""; // "mouse", "touch" or "pen": what the last press was made with

  function setMode(on) {
    mode = on;
    btnComment.classList.toggle("on", on);
    btnComment.textContent = on ? (TOUCH ? "Cancel" : "Click an element (Esc)") : COMMENT_LABEL;
    if (TOUCH) say(on ? "Tap the part to comment on." : "");
    if (!on) {
      outline.hidden = true;
      chip.hidden = true;
      btnHere.hidden = true;
      hoverEl = null;
      picked = null;
    }
  }

  function pageTarget(e) {
    var path = e.composedPath ? e.composedPath() : [];
    if (path.indexOf(host) >= 0) return null;
    var el = e.target;
    return el && el.nodeType === 1 && el !== document.documentElement ? el : null;
  }

  function place(box, rect) {
    box.style.left = rect.left + scrollX + "px";
    box.style.top = rect.top + scrollY + "px";
    box.style.width = rect.width + "px";
    box.style.height = rect.height + "px";
  }

  function showOutline(el) {
    var r = el.getBoundingClientRect();
    place(outline, r);
    outline.hidden = false;
    var label = labelOf(el);
    chip.textContent = "<" + el.tagName.toLowerCase() + ">" + (label ? " " + (label.length > 40 ? label.slice(0, 39) + "…" : label) : "");
    chip.style.left = r.left + scrollX + "px";
    chip.style.top = Math.max(0, r.top + scrollY - 24) + "px";
    chip.hidden = false;
  }

  document.addEventListener(
    "mousemove",
    function (e) {
      // No outline that follows the finger: on touch the outline shows what a tap picked.
      if (!mode || TOUCH || lastPointer === "touch") return;
      var el = pageTarget(e);
      if (!el || el === hoverEl) return;
      hoverEl = el;
      showOutline(el);
    },
    true,
  );

  /** Touch: a tap only picks. "Comment here", next to where the finger was, opens it. */
  function pick(el, e) {
    picked = { el: el, anchor: anchorFor(el, "element", null, e) };
    showOutline(el);
    btnHere.hidden = false;
    var w = btnHere.offsetWidth || 140;
    var hgt = btnHere.offsetHeight || 44;
    var x = Math.min(Math.max(8, e.clientX - w / 2), innerWidth - w - 8);
    var y = e.clientY + 16;
    if (y + hgt > innerHeight - 80) y = Math.max(8, e.clientY - hgt - 16);
    btnHere.style.left = x + scrollX + "px";
    btnHere.style.top = y + scrollY + "px";
    say("Tap Comment here, or tap another part.");
  }

  function swallow(e) {
    if (!mode || !pageTarget(e)) return;
    e.preventDefault();
    e.stopPropagation();
  }
  document.addEventListener(
    "pointerdown",
    function (e) {
      lastPointer = e.pointerType || "";
    },
    true,
  );
  ["mousedown", "mouseup", "pointerdown", "pointerup"].forEach(function (t) {
    document.addEventListener(t, swallow, true);
  });
  document.addEventListener(
    "click",
    function (e) {
      if (!mode) return;
      var el = pageTarget(e);
      if (!el) return;
      e.preventDefault();
      e.stopPropagation();
      if (lastPointer === "touch" || lastPointer === "pen" || (TOUCH && lastPointer !== "mouse")) return pick(el, e);
      setMode(false);
      openComposer(anchorFor(el, "element", null, e), el);
    },
    true,
  );

  // Touch: selected text gets its own button in the bar, since there is no C key.
  var lastRange = null;
  var selectionTimer = null;
  function selectedRange() {
    var sel = window.getSelection && window.getSelection();
    if (!sel || sel.isCollapsed || !sel.rangeCount || !clean(sel.toString())) return null;
    var range = sel.getRangeAt(0);
    var n = range.commonAncestorContainer;
    if (n.nodeType !== 1) n = n.parentElement;
    return n && !host.contains(n) ? range : null;
  }
  function hideSelectionButton() {
    clearTimeout(selectionTimer);
    lastRange = null;
    btnSelection.hidden = true;
  }
  if (TOUCH) {
    document.addEventListener("selectionchange", function () {
      var range = selectedRange();
      clearTimeout(selectionTimer);
      if (range) {
        lastRange = range.cloneRange();
        btnSelection.hidden = false;
      } else if (lastRange) {
        // The tap on the button can clear the selection before its click arrives.
        selectionTimer = setTimeout(hideSelectionButton, 800);
      }
    });
  }

  function startTextComment(given) {
    var range = given || selectedRange();
    if (!range || range.collapsed || !clean(range.toString())) return false;
    var el = range.commonAncestorContainer;
    if (el.nodeType !== 1) el = el.parentElement;
    if (!el || host.contains(el)) return false;
    openComposer(anchorFor(el, "text", quoteFor(range)), el, range.getBoundingClientRect());
    return true;
  }

  function typing(e) {
    var path = e.composedPath ? e.composedPath() : [e.target];
    for (var i = 0; i < path.length; i++) {
      var n = path[i];
      if (!n || n.nodeType !== 1) continue;
      if (/^(INPUT|TEXTAREA|SELECT)$/.test(n.tagName) || n.isContentEditable) return true;
    }
    return false;
  }

  document.addEventListener(
    "keydown",
    function (e) {
      if (e.key === "Escape") {
        if (mode) setMode(false);
        else if (!pop.hidden) closePop();
        else if (panelOpen) {
          panelOpen = false;
          render();
        }
        return;
      }
      if ((e.key === "c" || e.key === "C") && !e.ctrlKey && !e.metaKey && !e.altKey && !typing(e)) {
        if (hidden) {
          hidden = false;
          render();
        }
        e.preventDefault();
        if (!startTextComment()) setMode(!mode);
      }
    },
    true,
  );

  // ---- Pictures of the element -------------------------------------------------------------
  var libLoad = null;

  /** The bundled capture library, loaded once, the first time it is needed. */
  function loadLib() {
    if (libLoad) return libLoad;
    libLoad = new Promise(function (resolve, reject) {
      if (window.modernScreenshot) return resolve(window.modernScreenshot);
      var s = document.createElement("script");
      s.src = BASE + "vendor/modern-screenshot.js";
      s.onload = function () {
        // A page with its own AMD loader takes the library instead of window.
        if (window.modernScreenshot) resolve(window.modernScreenshot);
        else reject(new Error("the capture library loaded but did not start (the page may have its own module loader)"));
      };
      s.onerror = function () {
        reject(new Error("the capture library did not load"));
      };
      (document.head || document.documentElement).appendChild(s);
    });
    libLoad.catch(function () {
      libLoad = null; // try again next time
    });
    return libLoad;
  }

  /** The element's own background, or the nearest ancestor's that has one. */
  function backgroundOf(el) {
    for (var n = el; n && n.nodeType === 1; n = n.parentElement) {
      var c = getComputedStyle(n).backgroundColor;
      if (c && c !== "transparent" && !/^rgba\(.*,\s*0\)$/.test(c)) return c;
    }
    return "#ffffff";
  }

  function timeout(ms, what) {
    return new Promise(function (_, reject) {
      setTimeout(function () {
        reject(new Error(what + " took longer than " + ms / 1000 + " seconds"));
      }, ms);
    });
  }

  /**
   * Draw `el` to a PNG Blob: 16 px of background around it, at most 600 CSS px
   * wide, at up to twice the pixel density. Iframes and this bar are left out.
   * A node inside an SVG is drawn with its whole diagram, then cropped to it.
   */
  function capture(el) {
    var target = el;
    while (target.ownerSVGElement) target = target.ownerSVGElement;
    var box = el.getBoundingClientRect();
    var tBox = target.getBoundingClientRect();
    if (!box.width || !box.height) return Promise.reject(new Error("the element has no size on screen"));
    var scale = Math.min(devicePixelRatio || 1, 2) * Math.min(1, SHOT_MAX_W / (box.width + 2 * SHOT_PAD));
    var bg = backgroundOf(el);
    return loadLib()
      .then(function (lib) {
        return lib.domToCanvas(target, {
          scale: scale,
          backgroundColor: bg,
          // The library drops the element's own margin, which lets the browser's
          // default (an h1's 0.67em) come back in the copy and push it down.
          style: { margin: "0" },
          timeout: SHOT_MS,
          filter: function (n) {
            return n !== host && n.nodeName !== "IFRAME";
          },
        });
      })
      .then(function (drawn) {
        var pad = Math.round(SHOT_PAD * scale);
        var sx = Math.max(0, Math.round((box.left - tBox.left) * scale));
        var sy = Math.max(0, Math.round((box.top - tBox.top) * scale));
        var sw = Math.min(drawn.width - sx, Math.round(box.width * scale));
        var sh = Math.min(drawn.height - sy, Math.round(box.height * scale));
        var out = document.createElement("canvas");
        out.width = sw + 2 * pad;
        out.height = sh + 2 * pad;
        var ctx = out.getContext("2d");
        ctx.fillStyle = bg;
        ctx.fillRect(0, 0, out.width, out.height);
        ctx.drawImage(drawn, sx, sy, sw, sh, pad, pad, sw, sh);
        return new Promise(function (resolve, reject) {
          out.toBlob(function (b) {
            if (b) resolve(b);
            else reject(new Error("the picture could not be made"));
          }, "image/png");
        });
      });
  }

  /** Start a picture now; it settles within 8 seconds, with a Blob or a reason. */
  function startShot(el) {
    var p;
    try {
      p = capture(el);
    } catch (e) {
      p = Promise.reject(e);
    }
    var raced = Promise.race([p, timeout(SHOT_MS, "the picture")]);
    raced.catch(function () {}); // looked at after the comment saves
    return raced;
  }

  /** Send a thread's picture, or why there is none. Never shown as a comment error. */
  function sendShot(id, shot) {
    var path = "threads/" + id + "/shot";
    function sendError(e) {
      return call("POST", path, { error: (e && e.message) || "the capture failed" });
    }
    shot
      .then(
        function (blob) {
          return fetch(BASE + path, { method: "POST", headers: { "X-Page-Comments-Token": TOKEN, "Content-Type": "image/png" }, body: blob, credentials: "same-origin" }).then(function (r) {
            return r.json().then(function (j) {
              if (r.ok) return j;
              if (r.status === 409) return j; // a picture is already there
              return sendError(new Error("the server refused the picture: " + (j.error || "HTTP " + r.status)));
            });
          });
        },
        sendError,
      )
      .then(function (r) {
        if (r && r.thread) {
          upsert(r.thread);
          render(); // also refreshes the thread if it is open and nobody is typing
        }
      })
      .catch(function (e) {
        say("The picture was not saved: " + e.message);
      });
  }

  function shotName(s) {
    var p = s.icloud || s.local || "";
    return p.slice(p.lastIndexOf("/") + 1);
  }

  /** One picture, inline, with the Files app links on an iPhone or iPad. */
  function shotView(t, s, label) {
    if (s.error) return h("div", { class: "shot-none", text: "No picture: " + s.error });
    var src = BASE + "shots/" + t.id + "/" + encodeURIComponent(shotName(s)) + "?token=" + encodeURIComponent(TOKEN) + "&sha=" + encodeURIComponent(s.sha || "");
    var fig = h("figure", { class: "shot" }, [h("img", { src: src, alt: label, loading: "lazy" }), h("figcaption", { text: label })]);
    var links = FILES && s.icloud && FILES.isAppleTouch(navigator) ? FILES.filesLinks(s.icloud) : null;
    if (links) {
      fig.appendChild(
        h("div", { class: "shot-links" }, [h("a", { href: links.file, text: "Open in Files" }), h("a", { href: links.folder, text: "Open the folder" })]),
      );
    }
    return fig;
  }

  // ---- The popover: a new comment, or one thread -------------------------------------
  function closePop() {
    pop.hidden = true;
    pop.textContent = "";
    openThreadId = null;
    composer = null;
  }

  function placePop(rect) {
    var w = Math.min(360, innerWidth - 24);
    var left = Math.min(Math.max(12, rect.left), innerWidth - w - 12);
    var top = rect.bottom + 8;
    if (top + 220 > innerHeight) top = Math.max(12, rect.top - 228);
    pop.style.width = w + "px";
    pop.style.left = left + scrollX + "px";
    pop.style.top = top + scrollY + "px";
  }

  function saveDraft(anchor, text) {
    try {
      if (text) sessionStorage.setItem(DRAFT_KEY, JSON.stringify({ anchor: anchor, text: text }));
      else sessionStorage.removeItem(DRAFT_KEY);
    } catch (e) {
      /* private mode: drafts just do not survive a reload */
    }
  }

  function openComposer(anchor, el, rect, text) {
    closePop();
    composer = { anchor: anchor, el: el };
    // The picture starts now, from the click, so it shows the page as it was.
    var shot = startShot(el);
    var where = anchor.type === "text" ? "On the text “" + clip(anchor.quote.exact, 60) + "”" : "On <" + anchor.tag + ">" + (anchor.label ? " “" + clip(anchor.label, 50) + "”" : "");
    var ta = h("textarea", { rows: "4", placeholder: "What should change here?", "aria-label": "Comment" });
    ta.value = text || "";
    ta.addEventListener("input", function () {
      saveDraft(anchor, ta.value);
    });
    var save = h("button", { type: "button", class: "primary", text: "Save" });
    var cancel = h("button", { type: "button", text: "Cancel" });
    var err = h("div", { class: "err", role: "alert" });
    ta.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save.click();
    });
    cancel.addEventListener("click", function () {
      saveDraft(anchor, "");
      closePop();
    });
    save.addEventListener("click", function () {
      var body = ta.value;
      if (!clean(body)) return;
      save.disabled = true;
      hashOf(el)
        .then(function (hash) {
          return call("POST", "threads", {
            page: { url: location.href, path: PATH, title: document.title },
            viewport: { w: innerWidth, h: innerHeight, dpr: devicePixelRatio || 1, scrollX: Math.round(scrollX), scrollY: Math.round(scrollY), scheme: matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light" },
            anchor: anchor,
            bodyHash: hash,
            body: body,
          });
        })
        .then(function (r) {
          saveDraft(anchor, "");
          upsert(r.thread);
          closePop();
          render();
          say("Saved. Claude will see it.");
          sendShot(r.thread.id, shot);
        })
        .catch(function (e) {
          save.disabled = false;
          err.textContent = "Not saved: " + e.message;
        });
    });
    pop.appendChild(h("div", { class: "where", text: where }));
    pop.appendChild(ta);
    pop.appendChild(err);
    pop.appendChild(h("div", { class: "actions" }, [save, cancel]));
    placePop(rect || el.getBoundingClientRect());
    pop.hidden = false;
    ta.focus();
  }

  function clip(s, n) {
    s = String(s || "");
    return s.length > n ? s.slice(0, n - 1) + "…" : s;
  }

  function when(ts) {
    var d = new Date(ts);
    return isNaN(d) ? ts : d.toLocaleString([], { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
  }

  function openThread(t) {
    closePop();
    openThreadId = t.id;
    var el = locate(t.anchor);
    var head = h("div", { class: "where" });
    head.appendChild(h("span", { class: "badge " + t.status, text: t.status === "open" ? (t.waiting === "claude" ? "waiting on Claude" : "waiting on you") : t.status }));
    if (!el) head.appendChild(h("span", { class: "badge lost", text: "not found on this page" }));
    else if (t.rev && t.rev.bodyHash && hashes[t.id] && hashes[t.id] !== t.rev.bodyHash) head.appendChild(h("span", { class: "badge changed", text: "changed since this comment" }));
    pop.appendChild(head);
    var where = t.anchor.type === "text" && t.anchor.quote ? "“" + clip(t.anchor.quote.exact, 80) + "”" : "<" + t.anchor.tag + "> " + clip(t.anchor.label, 60);
    pop.appendChild(h("div", { class: "quote", text: where }));
    var list = h("ol", { class: "messages" });
    var shots = t.shots || [];
    var commentShot = shots.filter(function (s) {
      return s.role === "comment" && !s.error;
    })[0] || shots.filter(function (s) {
      return s.role === "comment";
    }).pop();
    t.messages.forEach(function (m, i) {
      var meta = m.author + " · " + when(m.ts) + (m.commit ? " · commit " + m.commit : "") + (m.edited ? " · edited" : "");
      var li = h("li", { class: m.author === "claude" ? "claude" : "" }, [h("div", { class: "meta", text: meta }), h("div", { class: "body", text: m.body })]);
      if (i === 0 && commentShot) li.appendChild(shotView(t, commentShot, "When the comment was made"));
      list.appendChild(li);
    });
    shots.forEach(function (s) {
      if (s.role !== "after" || s.error) return;
      list.appendChild(h("li", { class: "claude" }, [shotView(t, s, "After the fix" + (s.commit ? ", commit " + s.commit.slice(0, 7) : "") + " · " + when(s.ts))]));
    });
    (t.history || []).forEach(function (s) {
      list.appendChild(h("li", { class: "event", text: s.status + " by " + s.author + " · " + when(s.ts) + (s.note ? ": " + s.note : "") }));
    });
    pop.appendChild(list);

    var ta = h("textarea", { rows: "2", placeholder: "Reply", "aria-label": "Reply" });
    var err = h("div", { class: "err", role: "alert" });
    var reply = h("button", { type: "button", class: "primary", text: "Reply" });
    var flip = h("button", { type: "button", text: t.status === "open" ? "Resolve" : "Reopen" });
    var dismiss = h("button", { type: "button", text: "Dismiss" });
    var close = h("button", { type: "button", class: "ghost", text: "Close" });
    function act(path, body) {
      return call("POST", "threads/" + t.id + "/" + path, body)
        .then(function (r) {
          upsert(r.thread);
          render();
          openThread(r.thread);
        })
        .catch(function (e) {
          err.textContent = "Not saved: " + e.message;
        });
    }
    reply.addEventListener("click", function () {
      if (clean(ta.value)) act("replies", { body: ta.value });
    });
    ta.addEventListener("keydown", function (e) {
      if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) reply.click();
    });
    flip.addEventListener("click", function () {
      act("status", { status: t.status === "open" ? "resolved" : "open" });
    });
    dismiss.addEventListener("click", function () {
      act("status", { status: "dismissed" });
    });
    close.addEventListener("click", closePop);
    pop.appendChild(ta);
    pop.appendChild(err);
    pop.appendChild(h("div", { class: "actions" }, [reply, flip, t.status === "open" ? dismiss : null, close]));
    var r = el ? el.getBoundingClientRect() : { left: innerWidth - 400, top: innerHeight - 300, bottom: 80, width: 0, height: 0 };
    placePop(el ? r : { left: innerWidth - 380, top: 60, bottom: 60 });
    pop.hidden = false;
  }

  // ---- Drawing pins and the list ---------------------------------------------------------
  function visible(t) {
    return t.status === "open" || showResolved;
  }

  // Where each shown pin's element sits now. If the page moved under the pins,
  // the next poll redraws them.
  var lastLayout = "";
  var drawn = false; // the first answer always draws, even on a page with no comments
  function layoutKey() {
    return threads
      .filter(visible)
      .map(function (t) {
        var el = locate(t.anchor);
        if (!el) return t.id + ":lost";
        var r = el.getBoundingClientRect();
        return t.id + ":" + Math.round(r.left + scrollX) + "," + Math.round(r.top + scrollY) + "," + Math.round(r.width) + "," + Math.round(r.height);
      })
      .join("|");
  }

  function render() {
    drawn = true;
    lastLayout = layoutKey();
    host.hidden = false;
    bar.hidden = hidden;
    tab.hidden = !hidden;
    pins.hidden = hidden;
    var open = threads.filter(function (t) {
      return t.status === "open";
    });
    btnOpen.textContent = open.length + " open";
    btnResolved.setAttribute("aria-pressed", String(showResolved));
    btnResolved.classList.toggle("on", showResolved);

    pins.textContent = "";
    var lost = [];
    var n = 0;
    threads.forEach(function (t) {
      if (!visible(t)) return;
      n++;
      var el = locate(t.anchor);
      if (!el) {
        lost.push(t);
        return;
      }
      (function (num) {
        hashOf(el).then(function (x) {
          if (x) hashes[t.id] = x;
        });
        var r = el.getBoundingClientRect();
        var fx = t.anchor.box && typeof t.anchor.box.fx === "number" ? t.anchor.box.fx : 1;
        var fy = t.anchor.box && typeof t.anchor.box.fy === "number" ? t.anchor.box.fy : 0;
        var pin = h("button", { type: "button", class: "pin " + t.status + (t.waiting === "human" ? " answered" : ""), title: clip(t.messages[0].body, 120), text: String(num) });
        pin.style.left = r.left + scrollX + r.width * fx - 11 + "px";
        pin.style.top = r.top + scrollY + r.height * fy - 11 + "px";
        pin.addEventListener("click", function () {
          openThread(t);
        });
        pins.appendChild(pin);
      })(n);
    });

    panel.hidden = !panelOpen || hidden;
    // The touch bar wraps onto more rows, so the panel sits above wherever it ends.
    if (TOUCH && !panel.hidden) panel.style.bottom = Math.round(innerHeight - bar.getBoundingClientRect().top + 8) + "px";
    panel.textContent = "";
    if (panelOpen) {
      var shown = threads.filter(visible);
      panel.appendChild(h("div", { class: "title", text: shown.length ? "Comments on this page" : "No comments on this page yet. " + (TOUCH ? "Tap Comment to add one." : "Press C to add one.") }));
      var ul = h("ul");
      shown.forEach(function (t) {
        var isLost = lost.indexOf(t) >= 0;
        var li = h("li", { class: t.status }, [
          h("span", { class: "badge " + t.status, text: t.status === "open" ? (t.waiting === "claude" ? "waiting on Claude" : "waiting on you") : t.status }),
          isLost ? h("span", { class: "badge lost", text: "not found on this page" }) : null,
          h("span", { class: "text", text: clip(t.messages[t.messages.length - 1].body, 90) }),
        ]);
        li.addEventListener("click", function () {
          var el = locate(t.anchor);
          if (el) el.scrollIntoView({ block: "center", behavior: "smooth" });
          setTimeout(function () {
            openThread(t);
          }, el ? 350 : 0);
        });
        ul.appendChild(li);
      });
      panel.appendChild(ul);
    }

    if (openThreadId) {
      var t = threads.find(function (x) {
        return x.id === openThreadId;
      });
      var active = root.activeElement;
      // Refresh an open thread only when nobody is typing in it.
      if (t && !(active && active.tagName === "TEXTAREA" && active.value)) openThread(t);
    }
  }

  // ---- Start ---------------------------------------------------------------------------------
  function start() {
    (document.documentElement || document.body).appendChild(host);
    poll().then(function () {
      try {
        var d = JSON.parse(sessionStorage.getItem(DRAFT_KEY) || "null");
        if (d && d.anchor && d.text) {
          var el = locate(d.anchor) || document.body;
          openComposer(d.anchor, el, null, d.text);
          say("Your unsaved comment is back.");
        }
      } catch (e) {
        /* no draft */
      }
    });
    setInterval(function () {
      if (!document.hidden) poll();
    }, POLL_MS);
    var t = null;
    addEventListener("resize", function () {
      clearTimeout(t);
      t = setTimeout(render, 150);
    });
  }

  if (document.readyState === "loading") document.addEventListener("DOMContentLoaded", start);
  else start();
})();
