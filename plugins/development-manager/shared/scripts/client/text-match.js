// Finding a comment's text again after the page changed (design section 4,
// anchor 3, phase 4). The server puts this file in front of comments.js, and
// the tests run it on its own, so it is kept free of anything page-specific:
// it works on a plain string of the page's text.
//
// findQuote(text, quote) looks for quote.exact in `text`:
//   1. every place the exact words appear (spaces and line breaks count as one space);
//   2. if there are none, places where most of the words appear, found by
//      voting with short pieces of the quote, each then scored with an edit
//      distance. A place counts when it is at least 80% the same as the quote.
// The 32 characters stored before and after the quote (prefix and suffix) then
// pick between places that score the same. When the two best places are still
// too close to call, both are returned, and the page treats that as "not found":
// a comment is never shown on a guessed element.

(function (root) {
  "use strict";
  var THRESHOLD = 0.8; // how alike a place must be to the quote to count
  var CONTEXT_WEIGHT = 0.1; // the words around the quote only break near-ties
  var TIE = 0.02; // two places closer than this are too close to call
  var MAX_FUZZY = 1000; // longer quotes must match exactly
  var MAX_HITS = 300; // places one piece of the quote may vote for

  /** Spaces and line breaks as one space, with each kept character's place in the original. */
  function normalise(s) {
    s = String(s || "");
    var out = "";
    var map = [];
    var space = false;
    for (var i = 0; i < s.length; i++) {
      var c = s.charAt(i);
      if (/\s/.test(c)) {
        if (!space) {
          out += " ";
          map.push(i);
        }
        space = true;
      } else {
        out += c;
        map.push(i);
        space = false;
      }
    }
    return { text: out, map: map };
  }

  function collapse(s) {
    return String(s || "").replace(/\s+/g, " ");
  }

  /** Edit distance between two short strings. */
  function distance(a, b) {
    if (a === b) return 0;
    if (!a.length) return b.length;
    if (!b.length) return a.length;
    var prev = new Array(b.length + 1);
    var cur = new Array(b.length + 1);
    for (var j = 0; j <= b.length; j++) prev[j] = j;
    for (var i = 1; i <= a.length; i++) {
      cur[0] = i;
      for (j = 1; j <= b.length; j++) {
        var cost = a.charCodeAt(i - 1) === b.charCodeAt(j - 1) ? 0 : 1;
        cur[j] = Math.min(prev[j - 1] + cost, prev[j] + 1, cur[j - 1] + 1);
      }
      var t = prev;
      prev = cur;
      cur = t;
    }
    return prev[b.length];
  }

  /** 1 when the two are the same, 0 when nothing is shared. Spaces count as one. */
  function similarity(a, b) {
    a = collapse(a).trim();
    b = collapse(b).trim();
    if (!a.length && !b.length) return 1;
    return 1 - distance(a, b) / Math.max(a.length, b.length);
  }

  /**
   * The best place for `p` anywhere inside `t`, which may start and end
   * anywhere: { dist, start, end } in `t`'s indices.
   */
  function align(p, t) {
    var m = p.length;
    var n = t.length;
    var prev = new Int32Array(n + 1);
    var prevS = new Int32Array(n + 1);
    var cur = new Int32Array(n + 1);
    var curS = new Int32Array(n + 1);
    for (var j = 0; j <= n; j++) {
      prev[j] = 0;
      prevS[j] = j;
    }
    for (var i = 1; i <= m; i++) {
      cur[0] = i;
      curS[0] = 0;
      var pc = p.charCodeAt(i - 1);
      for (j = 1; j <= n; j++) {
        var best = prev[j - 1] + (pc === t.charCodeAt(j - 1) ? 0 : 1);
        var from = prevS[j - 1];
        if (prev[j] + 1 < best) {
          best = prev[j] + 1;
          from = prevS[j];
        }
        if (cur[j - 1] + 1 < best) {
          best = cur[j - 1] + 1;
          from = curS[j - 1];
        }
        cur[j] = best;
        curS[j] = from;
      }
      var x = prev;
      prev = cur;
      cur = x;
      x = prevS;
      prevS = curS;
      curS = x;
    }
    var out = { dist: Infinity, start: 0, end: 0 };
    for (j = 0; j <= n; j++) {
      if (prev[j] < out.dist) out = { dist: prev[j], start: prevS[j], end: j };
    }
    return out;
  }

  /** How well the words before and after a place fit the stored prefix and suffix. */
  function contextScore(text, start, end, prefix, suffix) {
    var n = 0;
    var sum = 0;
    if (prefix) {
      sum += similarity(prefix, text.slice(Math.max(0, start - prefix.length), start));
      n++;
    }
    if (suffix) {
      sum += similarity(suffix, text.slice(end, end + suffix.length));
      n++;
    }
    return n ? sum / n : 0;
  }

  /** Places that may hold the quote, by votes from short pieces of it. */
  function candidates(text, exact) {
    var m = exact.length;
    var q = m < 16 ? 3 : 4;
    var pieces = [];
    for (var o = 0; o + q <= m; o += q) pieces.push(o);
    if (pieces.length > 64) {
      var step = pieces.length / 64;
      var some = [];
      for (var k = 0; k < 64; k++) some.push(pieces[Math.floor(k * step)]);
      pieces = some;
    }
    var size = Math.max(4, Math.floor(m / 10));
    var votes = {};
    pieces.forEach(function (o) {
      var piece = exact.substr(o, q);
      if (!piece.trim()) return;
      var seen = {};
      for (var at = text.indexOf(piece), hits = 0; at >= 0 && hits < MAX_HITS; at = text.indexOf(piece, at + 1), hits++) {
        var b = Math.floor((at - o) / size);
        if (seen[b]) continue; // one vote per piece per place
        seen[b] = true;
        votes[b] = (votes[b] || 0) + 1;
      }
    });
    var need = Math.max(1, Math.floor(pieces.length * 0.3));
    return Object.keys(votes)
      .filter(function (b) {
        return votes[b] >= need;
      })
      .sort(function (a, b) {
        return votes[b] - votes[a];
      })
      .slice(0, 30)
      .map(function (b) {
        return { from: Number(b) * size, size: size };
      });
  }

  /**
   * Find `quote` ({ exact, prefix, suffix }) in `text`. Returns null, or
   * { match, rival }: each { start, end, sim, score } in `text`'s own indices.
   * `rival` is set when a second place is too close to call; the caller then
   * treats the quote as not found, unless both places are the same element.
   */
  function findQuote(text, quote) {
    if (!quote || !quote.exact) return null;
    var page = normalise(text);
    var exact = collapse(quote.exact).trim();
    if (!exact) return null;
    var prefix = collapse(quote.prefix || "");
    var suffix = collapse(quote.suffix || "");
    var found = [];

    for (var at = page.text.indexOf(exact), hits = 0; at >= 0 && hits < MAX_HITS; at = page.text.indexOf(exact, at + 1), hits++) {
      found.push({ start: at, end: at + exact.length, sim: 1 });
    }
    if (!found.length && exact.length >= 4 && exact.length <= MAX_FUZZY) {
      var m = exact.length;
      var slack = Math.ceil(m * (1 - THRESHOLD)) + 2;
      candidates(page.text, exact).forEach(function (c) {
        var from = Math.max(0, c.from - slack);
        var to = Math.min(page.text.length, c.from + c.size + m + slack);
        var a = align(exact, page.text.slice(from, to));
        var len = a.end - a.start;
        var sim = 1 - a.dist / Math.max(m, len);
        if (sim >= THRESHOLD) found.push({ start: from + a.start, end: from + a.end, sim: sim });
      });
    }
    if (!found.length) return null;

    found.forEach(function (f) {
      f.score = f.sim + CONTEXT_WEIGHT * contextScore(page.text, f.start, f.end, prefix, suffix);
    });
    found.sort(function (a, b) {
      return b.score - a.score || a.start - b.start;
    });
    // Windows that overlap the best one are the same place, not a rival.
    var best = found[0];
    var rival = null;
    for (var i = 1; i < found.length; i++) {
      var f = found[i];
      if (f.start < best.end && f.end > best.start) continue;
      if (best.score - f.score < TIE) rival = f;
      break;
    }
    function raw(f) {
      return f && { start: page.map[f.start], end: page.map[f.end - 1] + 1, sim: Math.round(f.sim * 1000) / 1000, score: Math.round(f.score * 1000) / 1000 };
    }
    return { match: raw(best), rival: raw(rival) };
  }

  /**
   * The quote saved for an element comment: the element's whole text, from
   * `start` to `end` in the page's text, with 32 characters either side. None
   * for an element with no words, or with more than `max` characters, where a
   * quote of part of it could later point at a child.
   */
  function quoteAround(text, start, end, max) {
    if (start < 0 || end <= start) return null;
    var exact = text.slice(start, end);
    if (!exact.trim() || exact.length > max) return null;
    return { exact: exact, prefix: text.slice(Math.max(0, start - 32), start), suffix: text.slice(end, end + 32) };
  }

  root.__pageCommentsMatch = { findQuote: findQuote, quoteAround: quoteAround, similarity: similarity, THRESHOLD: THRESHOLD };
})(typeof globalThis !== "undefined" ? globalThis : this);
