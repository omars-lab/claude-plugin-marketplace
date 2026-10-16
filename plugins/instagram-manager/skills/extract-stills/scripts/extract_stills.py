#!/usr/bin/env python3
"""extract_stills.py — a still and a 3 s clip for each spot a saved reel names, cut from its video at
the moment the spot's name is on screen. A reel that names 13 places gets 13 pictures, so each
place's page in the hub shows that place, not the reel's cover. No model is called.

    extract_stills.py --pilot NAME    every spot in the pilot whose reel has a video
    extract_stills.py --all           every spot whose reel has a video
    options: --redo (cut again, even spots that have a still)
    --need-video (with --pilot or --all): list the reels naming 2 or more spots that have no video
                 yet, in .cache/stills/need-video.txt, for fetch-media --video; cuts nothing

Reads   $INSTAGRAM_HOME/.cache/saves.json            which saves are in the pilot
        $INSTAGRAM_HOME/data/tags.yaml               the same
        $INSTAGRAM_HOME/data/pins.yaml               the spots each reel names (resolve-post-location)
        $INSTAGRAM_HOME/data/media.yaml              which reels have a video (fetch-media --video)
        $INSTAGRAM_MEDIA_DIR/<code>/video.mp4
        $INSTAGRAM_MEDIA_DIR/<code>/frames/text.json the words on each frame (read-frames); made here
                                                     with read-frames' own code when it is missing
Writes  $INSTAGRAM_MEDIA_DIR/<code>/spots/still-<slug>.jpg   about 600 px wide
        $INSTAGRAM_MEDIA_DIR/<code>/spots/clip-<slug>.webp   3 s, 320 px wide, 10 frames a second,
                                                             silent and looping
        $INSTAGRAM_HOME/data/stills.yaml             one entry per spot: which frame, when, and the
                                                     two files (pointers only; the files stay in iCloud)

How the moment is picked
  The frames read-frames took (the first, then one per scene change) and the words read on each.
  The spot's moment is the first frame where the words the caption used for it (`said`), its
  OpenStreetMap name or its `lookup` are on screen, letters and digits in order (the same test the
  frame merge uses). A spot whose name is never on screen gets `how: not_on_screen` and no files:
  the hub shows the reel's cover for it, and a person can set `t:` (seconds) on the entry by hand,
  marked `by: hand`, to cut it there on the next run.

Every ffmpeg and img2webp call has a timeout.
"""

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(HERE, os.pardir, os.pardir)
sys.path.insert(0, os.path.join(SKILLS, os.pardir, "shared", "scripts"))
sys.path.insert(0, os.path.join(SKILLS, "resolve-post-location", "scripts"))
sys.path.insert(0, os.path.join(SKILLS, "read-frames", "scripts"))
import read_frames as rf  # noqa: E402
import resolve_post_location as rpl  # noqa: E402
from home import cache, home  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import load_yaml  # noqa: E402

STILLS = os.path.join("data", "stills.yaml")
NEED_VIDEO = os.path.join("stills", "need-video.txt")
STILL_WIDTH = 600
CLIP_WIDTH = 320
CLIP_SECONDS = 3.0
CLIP_FPS = 10
CLIP_QUALITY = 55      # img2webp -lossy -q: small files, still readable at 320 px
TIMEOUT = 180


def slug(name):
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "spot"


def spot_terms(e):
    return [t for t in (e.get("said"), e.get("name"), e.get("lookup")) if isinstance(t, str) and t.strip()]


def moment(e, info):
    """(frame number, seconds) of the first frame showing one of the spot's names, or None."""
    for f in sorted(info.get("frames") or [], key=lambda f: f.get("t") or 0):
        seen = rpl.frame_words(f)
        if any(rpl.on_screen(t, seen) for t in spot_terms(e)):
            return f["n"], float(f["t"])
    return None


def cut_still(video, t, path):
    rc, _, _ = rf.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", video,
                       "-frames:v", "1", "-vf", f"scale={STILL_WIDTH}:-2", "-q:v", "3", path], TIMEOUT)
    return rc == 0 and os.path.isfile(path) and os.path.getsize(path) > 0


def cut_clip(video, t, path, length=None):
    """A silent looping WebP: ffmpeg writes the frames, img2webp joins them (this ffmpeg has no WebP
    encoder). Starts at t, or earlier when t is within 3 s of the end."""
    if length:
        t = max(0.0, min(t, length - CLIP_SECONDS))
    with tempfile.TemporaryDirectory() as tmp:
        rc, _, _ = rf.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", video,
                           "-t", f"{CLIP_SECONDS}", "-an", "-vf", f"fps={CLIP_FPS},scale={CLIP_WIDTH}:-2",
                           os.path.join(tmp, "f-%03d.png")], TIMEOUT)
        frames = sorted(os.path.join(tmp, f) for f in os.listdir(tmp) if f.endswith(".png"))
        if rc != 0 or not frames:
            return False
        rc, _, _ = rf.run(["img2webp", "-loop", "0", "-lossy", "-q", str(CLIP_QUALITY), "-d",
                           str(round(1000 / CLIP_FPS))] + frames + ["-o", path], TIMEOUT)
    return rc == 0 and os.path.isfile(path) and os.path.getsize(path) > 0


def key_of(e):
    return (e.get("said") or e.get("name") or "").strip().lower()


def files_there(code, entry):
    return all(os.path.isfile(os.path.join(rpl.media_dir(), entry[k])) for k in ("still", "clip") if entry.get(k))


def do_post(code, spots, video, old, redo):
    """The stills.yaml entries for one reel's spots."""
    info = rf.frame_info(code)
    if info is None:
        info = rf.make_frames(code, video)
    if not info:
        log("stills_no_frames", shortcode=code)
        return [], 0
    length = info.get("seconds")
    before = {key_of(e): e for e in old or [] if isinstance(e, dict)}
    out, cut, used = [], 0, set()
    for e in spots:
        if not isinstance(e, dict) or not isinstance(e.get("name"), str):
            continue
        prev = before.get(key_of(e)) or {}
        if prev.get("by") == "hand" and isinstance(prev.get("t"), (int, float)):
            found = (prev.get("frame"), float(prev["t"]))
        else:
            found = moment(e, info)
        row = {"name": e["name"], "said": e.get("said") or e["name"]}
        if found is None:
            out.append({**row, "how": "not_on_screen"})
            continue
        n, t = found
        name = slug(e["name"])
        while name in used:   # two spots with one name in one reel
            name += "-2"
        used.add(name)
        row.update({"frame": n, "t": round(t, 2), "how": "hand" if prev.get("by") == "hand" else "on_screen",
                    "still": f"{code}/spots/still-{name}.jpg", "clip": f"{code}/spots/clip-{name}.webp"})
        if prev.get("by") == "hand":
            row["by"] = "hand"
        same = prev.get("still") == row["still"] and prev.get("t") == row["t"]
        if same and not redo and files_there(code, row):
            out.append(row)
            continue
        folder = os.path.join(rpl.media_dir(), code, "spots")
        os.makedirs(folder, exist_ok=True)
        ok = cut_still(video, t, os.path.join(rpl.media_dir(), row["still"]))
        ok = cut_clip(video, t, os.path.join(rpl.media_dir(), row["clip"]), length) and ok
        if not ok:
            log("stills_cut_failed", shortcode=code, spot=name)
            out.append({**{k: row[k] for k in ("name", "said", "frame", "t")}, "how": "cut_failed"})
            continue
        cut += 1
        out.append(row)
    return out, cut


def need_video(saves, tags, media, pins, pilot):
    """The reels whose spots would all share one cover: 2 or more spots, and no video yet."""
    codes = [s["code"] for s in saves
             if len(pins.get(s["code"]) or []) >= 2 and (media.get(s["code"]) or {}).get("kind", s.get("kind")) == "reel"
             and not (media.get(s["code"]) or {}).get("video") and not (media.get(s["code"]) or {}).get("error")
             and in_pilot(s, tags.get(s["code"]), pilot)]   # an error (gone, login wall) is not tried again
    path = cache(NEED_VIDEO)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("".join(f"{c}\n" for c in codes))
    log("stills_need_video", reels=len(codes), spots=sum(len(pins[c]) for c in codes))
    print(f"{len(codes)} reels naming {sum(len(pins[c]) for c in codes)} spots have no video yet")
    print(path)
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    scope = ap.add_mutually_exclusive_group(required=True)
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    ap.add_argument("--redo", action="store_true", help="cut again, even spots that have a still")
    ap.add_argument("--need-video", action="store_true",
                    help="list the reels naming 2 or more spots with no video yet, and cut nothing")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)
    for tool in ("ffmpeg", "ffprobe", "img2webp"):
        if not shutil.which(tool):
            sys.exit(f"{tool} is not on PATH (brew install ffmpeg webp)")
    pilot = None
    if args.pilot:
        pilots = load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}
        if args.pilot not in pilots:
            sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
        pilot = pilots[args.pilot]
    with open(args.saved or cache("saves.json"), encoding="utf-8") as fh:
        saves = json.load(fh)["saves"]
    tags, media, pins = load_yaml(rpl.TAGS), load_yaml(rf.MEDIA), load_yaml(rpl.PINS)
    if args.need_video:
        return need_video(saves, tags, media, pins, pilot)
    stills = load_yaml(STILLS)
    reels = cut = shown = hidden = 0
    for s in saves:
        code = s["code"]
        video = (media.get(code) or {}).get("video")
        if not video or not pins.get(code) or not in_pilot(s, tags.get(code), pilot):
            continue
        log("stills_post", shortcode=code, spots=len(pins[code]))
        rows, n = do_post(code, pins[code], os.path.join(rpl.media_dir(), video), stills.get(code), args.redo)
        if rows:
            stills[code] = rows
        reels += 1
        cut += n
        shown += sum(1 for r in rows if r.get("still"))
        hidden += sum(1 for r in rows if r.get("how") == "not_on_screen")
    rpl.write_yaml(STILLS, stills)
    log("stills", scope=args.pilot or "all", reels=reels, cut=cut, with_still=shown, not_on_screen=hidden)
    print(f"{reels} reels with a video: {shown} spots have a still and a clip ({cut} cut this run), "
          f"{hidden} never show their name on screen (the hub shows the reel's cover for those)")
    print(os.path.join(home(), STILLS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
