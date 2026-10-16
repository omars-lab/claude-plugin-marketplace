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
  frame merge uses). Only when no frame shows it that way does a looser test count: the name without
  the words at its end that say what kind of place it is ("Stout Grove" for Stout Grove Trail, at
  least two words), or a long name with one letter misread ("Monferey Bay Aquarium"). Road-trip reels often put only the area on screen ("Stop 2. Big Sur") and leave
  its viewpoints to the caption: a spot whose own name never shows takes the first frame showing its
  area (`near`, never a whole state or country), gets `how: area` and `area: <name>`, and shares that
  one still and clip with the other spots of the area. Only when the reel shows two or more of its
  areas at different times, and never a frame naming several (a title card, a map). An area is
  looked for by its full name first, then by its short one ("Yosemite" for Yosemite National Park,
  so a frame reading "Sequoia & Kings Canyon" names two areas and is skipped too). One area on
  screen is what the whole reel is about, so it marks no part of it. A spot with neither gets
  `how: not_on_screen` and no files: the hub shows the reel's cover for it, and a person can set
  `t:` (seconds) on the entry by hand, marked `by: hand`, to cut it there on the next run.

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
from home import cache, home, read_saves  # noqa: E402
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
# Words at the end of a name that say what kind of place it is, not which one.
KIND_WORDS = {"national", "state", "park", "parks", "recreation", "area", "and", "the", "of",
              "trail", "trailhead", "loop", "vista", "point", "viewpoint", "overlook"}
SHORT_LETTERS = 6      # a short name needs this many letters ("Sequoia"), so "Mist" never stands alone
TYPO_LETTERS = 12      # a name needs this many letters before one misread letter is let through
DENSE_STEP = 0.5       # seconds between the extra frames read when read-frames' frames miss a spot


def slug(name):
    s = unicodedata.normalize("NFKD", str(name)).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")[:60] or "spot"


def spot_terms(e):
    return [t for t in (e.get("said"), e.get("name"), e.get("lookup")) if isinstance(t, str) and t.strip()]


def short(name, words=1):
    """The name without the words at its end that only say what kind of place it is ("Yosemite" for
    Yosemite National Park, "Stout Grove" for Stout Grove Trail), or None when that leaves nothing
    new, fewer than `words` words or fewer than SHORT_LETTERS letters."""
    parts = re.findall(r"[^\W_]+", unicodedata.normalize("NFKC", str(name)))
    keep = list(parts)
    while keep and keep[-1].lower() in KIND_WORDS:
        keep.pop()
    if len(keep) == len(parts) or len(keep) < words or len("".join(keep)) < SHORT_LETTERS:
        return None
    return " ".join(keep)


def one_letter_off(term, seen):
    """True when a long name is on screen with one letter misread ("Monferey" for Monterey)."""
    a, s = rpl.squash(term), rpl.squash(seen)
    if len(a) < TYPO_LETTERS:
        return False
    return any(sum(x != y for x, y in zip(a, s[i:i + len(a)])) <= 1 for i in range(len(s) - len(a) + 1))


def loosely_on_screen(term, seen, words=1):
    """The second try, only after no frame showed the name itself: its short form, or the name with one
    letter misread."""
    s = short(term, words)
    return bool(s and rpl.on_screen(s, seen)) or one_letter_off(term, seen)


def by_time(frames):
    return sorted(frames or [], key=lambda f: f.get("t") or 0)


def tries(info, dense, exact, loose):
    """The tries in order, each (frames, test): read-frames' frames by the exact test, then the frames
    read every DENSE_STEP s by it, then all of them by the loose one. The first try that finds a
    moment wins, so a name read-frames already saw keeps the moment it had."""
    mine, more = by_time(info.get("frames")), by_time((dense or {}).get("frames"))
    return [(mine, exact), (more, exact), (by_time(mine + more), loose)]


def moment(e, info, dense=None):
    """(frame number, seconds) of the first frame showing one of the spot's names, or None. A frame of
    `dense` has no number. Only when no frame shows a name does a frame showing one loosely count (two
    words or more left; see short)."""
    for frames, test in tries(info, dense, rpl.on_screen, lambda t, seen: loosely_on_screen(t, seen, words=2)):
        for f in frames:
            seen = rpl.frame_words(f)
            if any(test(t, seen) for t in spot_terms(e)):
                return f.get("n"), float(f["t"])
    return None


def dense_info(code, video, length):
    """The words on a frame every DENSE_STEP s, for a reel whose cuts outrun read-frames' 12 frames (a
    reel of 19 one-second stops loses 7 of them). Only the words are kept, in frames/dense.json, made
    once per video; the frames are thrown away. Apple Vision reads them, or tesseract off a Mac.

    Each frame keeps the time it really has in the video. ffmpeg's fps filter would stamp it with its
    half-second slot instead, while the picture is the slot's last frame, up to a quarter second
    later: a label read at "7.0" was on screen at 7.2, after the cut, so the still at 7.0 showed the
    stop before."""
    path = os.path.join(rpl.media_dir(), code, "frames", "dense.json")
    try:
        if os.path.getmtime(path) >= os.path.getmtime(video):
            with open(path, encoding="utf-8") as fh:
                info = json.load(fh)
            if info.get("times") == "real":
                return info
    except (OSError, ValueError):
        pass
    frames = []
    with tempfile.TemporaryDirectory() as tmp:
        log("stills_dense_start", shortcode=code, seconds=length)
        # The first frame, then each frame at least DENSE_STEP after the last one kept (a hair less, so
        # float sums of the frame times don't skip one); showinfo prints each kept frame's time.
        rc, _, err = rf.run(["ffmpeg", "-hide_banner", "-nostats", "-y", "-i", video, "-an", "-vf",
                             f"select='isnan(prev_selected_t)+gte(t-prev_selected_t\\,{DENSE_STEP - 0.01})',"
                             f"showinfo,scale={rf.FRAME_WIDTH}:-2", "-fps_mode", "vfr", "-q:v", "3",
                             os.path.join(tmp, "d-%04d.jpg")], TIMEOUT)
        times = [float(t) for t in re.findall(r"pts_time:\s*([\d.]+)", err)] if rc == 0 else []
        paths = sorted(os.path.join(tmp, f) for f in os.listdir(tmp) if f.endswith(".jpg"))[:len(times)]
        seen = rf.vision(paths)
        for t, p in zip(times, paths):
            frames.append({"t": round(t, 2), **({"vision": seen.get(p, "")} if seen else {"text": rf.ocr(p)})})
    info = {"video": f"{code}/video.mp4", "step": DENSE_STEP, "times": "real", "frames": frames}
    if frames:
        rpl.write_json(path, info)
    log("stills_dense_done", shortcode=code, frames=len(frames), reader="vision" if seen else "tesseract")
    return info


def area_of(e, places):
    """The area a spot sits in (`near`), when it is smaller than a state; else None."""
    near = e.get("near")
    if not isinstance(near, str) or not near.strip():
        return None
    return None if (places.get(near) or {}).get("kind") in ("state", "country") else near


def area_moments(spots, info, places, dense=None):
    """{area: (frame, seconds)} for a reel that moves through its areas one after another: the first
    frame naming that area and no other of the reel's areas (a title card or map naming several is
    skipped). Empty unless two or more areas show at different times; one area on screen is the
    whole reel, not a part of it."""
    areas = sorted({a for a in (area_of(e, places) for e in spots if isinstance(e, dict)) if a})
    found = {}
    # The full names first; then, for the areas still without a moment, their short names
    # ("Yosemite" for Yosemite National Park). A frame naming two areas either way is still skipped.
    loose = lambda a, seen: rpl.on_screen(a, seen) or loosely_on_screen(a, seen)
    for frames, test in tries(info, dense, rpl.on_screen, loose):
        for f in frames:
            seen = rpl.frame_words(f)
            named = [a for a in areas if test(a, seen)]
            if len(named) == 1 and named[0] not in found:
                found[named[0]] = (f.get("n"), float(f["t"]))
    return found if len({t for _, t in found.values()}) >= 2 else {}


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


def do_post(code, spots, video, old, redo, places=None):
    """The stills.yaml entries for one reel's spots."""
    info = rf.frame_info(code)
    if info is None:
        info = rf.make_frames(code, video)
    if not info:
        log("stills_no_frames", shortcode=code)
        return [], 0
    length = info.get("seconds")
    before = {}   # a spot's old rows, in order: two spots of one reel can share a name
    for e in old or []:
        if isinstance(e, dict):
            before.setdefault(key_of(e), []).append(e)
    out, cut, used, done = [], 0, set(), {}   # done: an area's still, cut once and shared this run
    # Read a frame every DENSE_STEP s only when read-frames' frames miss a spot's own name: a reel
    # cutting faster than its 12 frames loses whole stops.
    dense = None
    if any(isinstance(e, dict) and isinstance(e.get("name"), str)
           and (before.get(key_of(e)) or [{}])[0].get("by") != "hand" and moment(e, info) is None for e in spots):
        dense = dense_info(code, video, length)
    by_area = area_moments(spots, info, places or {}, dense)
    for e in spots:
        if not isinstance(e, dict) or not isinstance(e.get("name"), str):
            continue
        mine = before.get(key_of(e))
        prev = mine.pop(0) if mine else {}
        area = None
        if prev.get("by") == "hand" and isinstance(prev.get("t"), (int, float)):
            found = (prev.get("frame"), float(prev["t"]))
            # A hand time set for the area ("Sequoia & Kings Canyon" names two areas, so no frame
            # counts): its spots share the area's picture, as `how: area` spots do.
            area = prev["area"] if isinstance(prev.get("area"), str) else None
        else:
            found = moment(e, info, dense)
            if found is None:
                area = area_of(e, places or {})
                found = by_area.get(area)
                area = area if found else None
        row = {"name": e["name"], "said": e.get("said") or e["name"]}
        if found is None:
            out.append({**row, "how": "not_on_screen"})
            continue
        n, t = found
        if area:
            name = "area-" + slug(area)
        else:
            name = slug(e["name"])
            while name in used:   # two spots with one name in one reel
                name += "-2"
            used.add(name)
        how = "hand" if prev.get("by") == "hand" else "area" if area else "on_screen"
        row.update({**({"frame": n} if n is not None else {}), "t": round(t, 2), "how": how, **({"area": area} if area else {}),
                    "still": f"{code}/spots/still-{name}.jpg", "clip": f"{code}/spots/clip-{name}.webp"})
        if prev.get("by") == "hand":
            row["by"] = "hand"
        if row["still"] in done:   # another spot of this area already cut it
            out.append(row if done[row["still"]] else {**{k: row[k] for k in ("name", "said", "frame", "t") if k in row},
                                                       "how": "cut_failed"})
            continue
        same = prev.get("still") == row["still"] and prev.get("t") == row["t"]
        if same and not redo and files_there(code, row):
            done[row["still"]] = True
            out.append(row)
            continue
        folder = os.path.join(rpl.media_dir(), code, "spots")
        os.makedirs(folder, exist_ok=True)
        ok = cut_still(video, t, os.path.join(rpl.media_dir(), row["still"]))
        ok = cut_clip(video, t, os.path.join(rpl.media_dir(), row["clip"]), length) and ok
        done[row["still"]] = ok
        if not ok:
            log("stills_cut_failed", shortcode=code, spot=name)
            out.append({**{k: row[k] for k in ("name", "said", "frame", "t") if k in row}, "how": "cut_failed"})
            continue
        cut += 1
        out.append(row)
    return out, cut


def need_video(saves, tags, media, pins, pilot):
    """The reels whose spots would all share one cover: 2 or more spots, and no video yet."""
    def asked(m):   # a video, or an error (gone, login wall, no video): not tried again
        return any(k in m for k in ("video", "error", "video_error"))

    codes = [s["code"] for s in saves
             if len(pins.get(s["code"]) or []) >= 2 and (media.get(s["code"]) or {}).get("kind", s.get("kind")) == "reel"
             and not asked(media.get(s["code"]) or {}) and in_pilot(s, tags.get(s["code"]), pilot)]
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
    saves = read_saves(args.saved)["saves"]
    tags, media, pins = load_yaml(rpl.TAGS), load_yaml(rf.MEDIA), load_yaml(rpl.PINS)
    if args.need_video:
        return need_video(saves, tags, media, pins, pilot)
    stills = load_yaml(STILLS)
    places = load_yaml(os.path.join("data", "places.yaml")).get("places") or {}
    reels = cut = shown = by_area = hidden = 0
    for s in saves:
        code = s["code"]
        video = (media.get(code) or {}).get("video")
        if not video or not pins.get(code) or not in_pilot(s, tags.get(code), pilot):
            continue
        log("stills_post", shortcode=code, spots=len(pins[code]))
        rows, n = do_post(code, pins[code], os.path.join(rpl.media_dir(), video), stills.get(code), args.redo, places)
        if rows:
            stills[code] = rows
        reels += 1
        cut += n
        shown += sum(1 for r in rows if r.get("still"))
        by_area += sum(1 for r in rows if r.get("how") == "area")
        hidden += sum(1 for r in rows if r.get("how") == "not_on_screen")
    rpl.write_yaml(STILLS, stills)
    log("stills", scope=args.pilot or "all", reels=reels, cut=cut, with_still=shown, by_area=by_area,
        not_on_screen=hidden)
    print(f"{reels} reels with a video: {shown} spots have a still and a clip ({cut} cut this run; "
          f"{by_area} from the moment their area is on screen), "
          f"{hidden} never show their name or area on screen (the hub shows the reel's cover for those)")
    print(os.path.join(home(), STILLS))
    return 0


if __name__ == "__main__":
    sys.exit(main())
