// The part of an element a person can actually see, for the outline drawn around
// it in comment mode. A picture in a strip that scrolls sideways, or in a card
// that hides what spills over, can be far wider than what shows; the outline
// should hug what shows, not run off past the card. The server puts this file in
// front of comments.js, and the tests run it on its own, so it works on plain
// boxes: comments.js measures the page and passes them in.
//
// visibleRect(rect, clips) cuts `rect` down by each clip in turn:
//   rect:  { left, top, width, height }, the element's own box;
//   clips: [{ left, top, right, bottom, x, y }], one per container that cuts off
//          what spills over, with `x` and `y` saying which way it cuts.
// It returns { left, top, width, height }. When nothing is left (the element is
// scrolled fully out of its container), it returns the element's own box, so
// the outline still says what was picked.

(function (root) {
  "use strict";

  function visibleRect(rect, clips) {
    var left = rect.left;
    var top = rect.top;
    var right = rect.left + rect.width;
    var bottom = rect.top + rect.height;
    for (var i = 0; i < (clips || []).length; i++) {
      var c = clips[i];
      if (c.x) {
        left = Math.max(left, c.left);
        right = Math.min(right, c.right);
      }
      if (c.y) {
        top = Math.max(top, c.top);
        bottom = Math.min(bottom, c.bottom);
      }
    }
    if (right <= left || bottom <= top) return { left: rect.left, top: rect.top, width: rect.width, height: rect.height };
    return { left: left, top: top, width: right - left, height: bottom - top };
  }

  root.__pageCommentsRect = { visibleRect: visibleRect };
})(typeof globalThis !== "undefined" ? globalThis : this);
