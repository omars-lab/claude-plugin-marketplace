#!/usr/bin/env python3
"""previews.py — a small picture and a flipbook per post, for pages that list many posts at once
(the pins page). A spot's 3 s clip is 300 KB or more; a page of hundreds of posts cannot load those.
These are made for a list: about 5 KB for the picture, and about 50 KB for the flipbook, which
only loads when its post scrolls into view.

    previews.py CODE [CODE ...]     make the previews for these posts (skips ones already made)
    options: --out DIR (default $INSTAGRAM_HOME/.cache/hub/previews), --redo

Reads   $INSTAGRAM_HOME/data/media.yaml             each post's thumbnail, cover and video
        $INSTAGRAM_MEDIA_DIR/<code>/thumb.jpg, cover.jpg, video.mp4
Writes  OUT/<code>.jpg    144 x 192, the post's cover (or thumbnail), cropped to fit
        OUT/<code>.webp   the same size, 12 frames spread over the whole reel, 0.35 s each, looping;
                          only for posts with a video

Both are made again when their source file is newer. Every ffmpeg and img2webp call has a timeout.
"""

import argparse
import os
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(HERE, os.pardir, os.pardir)
sys.path.insert(0, os.path.join(SKILLS, os.pardir, "shared", "scripts"))
sys.path.insert(0, os.path.join(SKILLS, "read-frames", "scripts"))
sys.path.insert(0, os.path.join(SKILLS, "build-hub", "scripts"))
import read_frames as rf  # noqa: E402
from home import cache, home  # noqa: E402
from log import log  # noqa: E402
from places import load_yaml  # noqa: E402

MEDIA_DEFAULT = "~/Library/Mobile Documents/com~apple~CloudDocs/CloudDesktop/data/instagram"
W, H = 144, 192          # twice the 72 x 96 box the page shows them in
FRAMES = 12              # spread over the whole reel, so the flipbook shows what the post is about
FRAME_MS = 350
QUALITY = 45             # img2webp -lossy -q
TIMEOUT = 120
FIT = f"scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H}"


MAX_PLAYING = 8          # flipbooks moving at once on a page

# For a page that shows them: <img src=PICTURE data-poster=PICTURE data-anim=FLIPBOOK>. A flipbook
# loads and plays only while its picture is on screen (at least 60% of it, inside any scrolled box),
# at most MAX_PLAYING at once, and turns back into the picture when it scrolls away. With reduced
# motion asked for, it plays only while the pointer is on it. A list drawn later calls
# window.flipbooks(itsBox); pictures taken off the page are dropped.
PLAYER_JS = """<script>(function(){var MAX=__MAX__,imgs=[],seen=new Set(),held=null,
auto=!(window.matchMedia&&matchMedia('(prefers-reduced-motion: reduce)').matches),
io='IntersectionObserver' in window?new IntersectionObserver(function(es){
es.forEach(function(e){if(e.isIntersecting)seen.add(e.target);else seen.delete(e.target)});refresh()},{threshold:0.6}):null;
function refresh(){var n=0;imgs=imgs.filter(function(i){if(i.isConnected)return true;seen.delete(i);if(io)io.unobserve(i);return false});
imgs.forEach(function(i){var play=i===held||(auto&&seen.has(i)&&n<MAX);if(play&&i!==held)n++;
var want=play?i.getAttribute('data-anim'):i.getAttribute('data-poster');if(i.getAttribute('src')!==want)i.setAttribute('src',want)})}
window.flipbooks=function(root){(root||document).querySelectorAll('img[data-anim]:not([data-flip])').forEach(function(i){
i.setAttribute('data-flip','');imgs.push(i);
i.addEventListener('mouseenter',function(){held=i;refresh()});i.addEventListener('mouseleave',function(){held=null;refresh()});
if(io)io.observe(i)});refresh()};window.flipbooks(document);})();</script>"""


def player_js():
    return PLAYER_JS.replace("__MAX__", str(MAX_PLAYING))


def media_dir():
    return os.path.expanduser(os.environ.get("INSTAGRAM_MEDIA_DIR") or MEDIA_DEFAULT)


def out_dir():
    return cache(os.path.join("hub", "previews"))


def fresh(path, src):
    return os.path.isfile(path) and os.path.getsize(path) > 0 and os.path.getmtime(path) >= os.path.getmtime(src)


def poster(src, path):
    rc, _, _ = rf.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", src,
                       "-frames:v", "1", "-vf", FIT, "-q:v", "6", path], TIMEOUT)
    return rc == 0 and os.path.isfile(path) and os.path.getsize(path) > 0


def flipbook(video, path):
    """FRAMES frames at even steps through the reel, joined into a looping WebP (this ffmpeg has no
    WebP encoder, so img2webp joins them, as extract_stills does)."""
    length = rf.duration(video) or 0
    if length <= 0:
        return False
    with tempfile.TemporaryDirectory() as tmp:
        rc, _, _ = rf.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-an",
                           "-vf", f"fps={FRAMES}/{length:.2f},{FIT}", "-frames:v", str(FRAMES),
                           os.path.join(tmp, "f-%03d.png")], TIMEOUT)
        frames = sorted(os.path.join(tmp, f) for f in os.listdir(tmp) if f.endswith(".png"))
        if rc != 0 or len(frames) < 2:
            return False
        rc, _, _ = rf.run(["img2webp", "-loop", "0", "-lossy", "-q", str(QUALITY), "-d", str(FRAME_MS)]
                          + frames + ["-o", path], TIMEOUT)
    return rc == 0 and os.path.isfile(path) and os.path.getsize(path) > 0


def make(code, entry, src_dir, out, redo=False, name=None):
    """{"poster": file name or None, "anim": file name or None} for one post, made when missing or
    older than its source. `name` is the file name without its ending (the code by default)."""
    got = {"poster": None, "anim": None}
    if not isinstance(entry, dict):
        return got
    os.makedirs(out, exist_ok=True)
    pic = next((os.path.join(src_dir, entry[k]) for k in ("cover", "thumb")
                if isinstance(entry.get(k), str) and os.path.isfile(os.path.join(src_dir, entry[k]))), None)
    video = os.path.join(src_dir, entry["video"]) if isinstance(entry.get("video"), str) else None
    video = video if video and os.path.isfile(video) else None
    name = name or code
    jpg, webp = os.path.join(out, name + ".jpg"), os.path.join(out, name + ".webp")
    if pic and (not redo and fresh(jpg, pic) or poster(pic, jpg)):
        got["poster"] = name + ".jpg"
    if video and (not redo and fresh(webp, video) or flipbook(video, webp)):
        got["anim"] = name + ".webp"
    return got


def make_all(codes, out=None, redo=False, names=None):
    """{code: {"poster", "anim"}} for each code, logging one line per post it makes. Files are named
    as the hub names its post pages (`names`, {code: name}, or worked out here), since two codes can
    differ by case alone and a Mac's disk does not."""
    media = load_yaml(os.path.join(home(), "data", "media.yaml"))
    src, out = media_dir(), out or out_dir()
    if names is None:
        from build_hub import Hub
        names = Hub._files(list(codes))
    made = {}
    def stamps(name):
        return [os.path.getmtime(p) if os.path.isfile(p) else None
                for p in (os.path.join(out, name + ext) for ext in (".jpg", ".webp"))]

    for code in codes:
        before = stamps(names[code])
        made[code] = make(code, media.get(code), src, out, redo, names[code])
        if stamps(names[code]) != before:
            log("preview", code=code, poster=bool(made[code]["poster"]), anim=bool(made[code]["anim"]))
    return made


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("codes", nargs="+")
    ap.add_argument("--out", default=None)
    ap.add_argument("--redo", action="store_true")
    args = ap.parse_args(argv)
    made = make_all(args.codes, args.out, args.redo)
    out = args.out or out_dir()
    for code, m in made.items():
        sizes = ", ".join(f"{k} {os.path.getsize(os.path.join(out, m[k])) // 1024} KB" for k in m if m[k])
        print(f"{code}: {sizes or 'no thumbnail or video'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
