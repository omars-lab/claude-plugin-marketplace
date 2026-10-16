#!/usr/bin/env python3
"""read_frames.py — read where a saved reel was filmed from its video: the names on screen (a title
card, a sign, a menu), for the posts whose caption names no spot. The reading is done by the
frame-reader agent in batches; this script never calls a model.

    read_frames.py --stuck --pilot NAME    write the list of reels to read (.cache/frames/stuck.txt),
                                           for fetch_media.py --video
    read_frames.py --prepare               frames, their text and contact sheets for every listed reel
                                           whose video is fetched, then batch files for the agent
    read_frames.py --text                  read the words again on frames already made (no new
                                           frames, no batches), after a text reader changes
    options: --redo (frames again, even for reels that have them), --batch-saves N

    The answers are merged by resolve_post_location.py --merge --frames.

Reads   $INSTAGRAM_HOME/.cache/saves.json            captions and creators
        $INSTAGRAM_HOME/data/tags.yaml, places.yaml  each save's places
        $INSTAGRAM_HOME/data/pins.yaml, pins-review.yaml, no-spot.yaml   what the captions gave
        $INSTAGRAM_HOME/data/media.yaml              which reels have a video
        $INSTAGRAM_MEDIA_DIR/<code>/video.mp4
Writes  $INSTAGRAM_HOME/.cache/frames/stuck.txt      one code a line, with why, for fetch_media.py --video
        $INSTAGRAM_MEDIA_DIR/<code>/frames/          frame-NN.jpg (720 px wide), sheet-N.jpg (6 frames
                                                     each, for the agent to look at), text.json (what
                                                     each text reader read on each frame, and when it
                                                     shows: `text` tesseract, `vision` Apple Vision)
        $INSTAGRAM_HOME/.cache/bin/vision_ocr         vision_ocr.swift, compiled on first use
        $INSTAGRAM_HOME/.cache/batches/frames/       batch-NNN.json (in), batch-NNN.answers.json (out)

Which reels are stuck
  A save in the pilot whose post is a reel, and one of:
  - its caption names no spot (it is in no-spot.yaml);
  - it is tagged with no town, park or region, only a state, so there is nowhere to search near;
  - it is for eating or staying (its tagged purposes) and its map link opens only its town: no pin,
    and no venue the caption named that OpenStreetMap just doesn't list.

How frames are picked (ffmpeg only)
  The first frame (where a title card usually is), then a frame at each scene change (ffmpeg's
  scene score above 0.3), at most 12, spread evenly when there are more. A reel with fewer than 6
  gets frames at even times to make up 6. Six frames make one contact sheet, numbered in reading
  order.

How the words are read
  Two text readers read each frame. tesseract (sparse-text mode, which suits words laid over a
  picture) reads plain print well but misses styled subtitles: outlined, yellow, bold over a busy
  picture, and the names on an Instagram profile card. On a Mac, Apple Vision (macOS's own text
  reader, vision_ocr.swift) reads those too. Both go into text.json; the merge accepts a name either
  one read. Off a Mac, or when the Swift compiler is missing, only tesseract runs.

Every call that can hang has a timeout: ffprobe, ffmpeg, tesseract, swiftc and the Vision reader.
"""

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "resolve-post-location", "scripts"))
import resolve_post_location as rpl  # noqa: E402
from home import cache  # noqa: E402
from log import log  # noqa: E402
from pilot import in_pilot  # noqa: E402
from places import load_yaml  # noqa: E402

MEDIA = os.path.join("data", "media.yaml")
MAX_FRAMES = 12
MIN_FRAMES = 6
SCENE = 0.3
FRAME_WIDTH = 720       # px: what the text readers read
SHEET_COLS, SHEET_ROWS = 3, 2
SHEET_FRAME_WIDTH = 360
BATCH_SAVES = 6         # each save brings 2 sheets: about 12 images an agent looks at
PURPOSES = ("eat", "stay")
# Review reasons where the caption named a venue and only the map lookup failed: the hub already
# opens that venue by name (build-hub's placed_spots).
LOOKUP_MISSES = (re.compile(r"^not found near "), re.compile(r"^found .*, a different name$"),
                 re.compile(r"^\d+ km from "))
PROBE_TIMEOUT = 30
FFMPEG_TIMEOUT = 180
OCR_TIMEOUT = 60
VISION_SRC = os.path.join(HERE, "vision_ocr.swift")
VISION_TIMEOUT = 300    # one call reads all of a reel's frames
COMPILE_TIMEOUT = 600


media_dir = rpl.media_dir


def frames_dir():
    return cache("frames")


def batch_dir():
    return cache("batches", "frames")


# --- which reels ---------------------------------------------------------------------------------

def opens_a_venue(code, pins, review):
    if pins.get(code):
        return True
    return any(isinstance(e, dict) and not e.get("drop") and any(r.match(str(e.get("why") or "")) for r in LOOKUP_MISSES)
               for e in review.get(code) or [])


def stuck(saves, tags, places, media, pins, review, no_spot, pilot):
    """[(code, why)] of the pilot's reels whose venue or town the caption did not give, in export order."""
    out = []
    for s in saves:
        code, tag = s["code"], tags.get(s["code"]) or {}
        if not in_pilot(s, tag, pilot) or (media.get(code) or {}).get("kind") != "reel":
            continue
        if code in no_spot:
            out.append((code, "the caption names no spot"))
        elif not rpl.areas_of(tag, places):
            out.append((code, "tagged with a state only"))
        elif set(tag.get("purposes") or []) & set(PURPOSES) and not opens_a_venue(code, pins, review):
            out.append((code, "for eating or staying, but opens only its town"))
    return out


def write_stuck(rows):
    path = os.path.join(frames_dir(), "stuck.txt")
    os.makedirs(frames_dir(), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("# reels whose place is not in the caption: read_frames.py --stuck writes this\n")
        for code, why in rows:
            fh.write(f"{code}  # {why}\n")
    return path


def read_codes(path):
    with open(path, encoding="utf-8") as fh:
        return [w for line in fh for w in line.split("#")[0].split()[:1]]


# --- frames --------------------------------------------------------------------------------------

def run(cmd, secs):
    """(returncode, stdout, stderr); a timeout logs ev=frames_timeout and returns code -1."""
    try:
        p = subprocess.run(cmd, capture_output=True, text=True, timeout=secs)
    except subprocess.TimeoutExpired:
        log("frames_timeout", cmd=os.path.basename(cmd[0]), secs=secs)
        return -1, "", ""
    return p.returncode, p.stdout, p.stderr


def duration(video):
    rc, out, _ = run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", video],
                     PROBE_TIMEOUT)
    try:
        return float(out.strip()) if rc == 0 else None
    except ValueError:
        return None


def scene_times(video):
    """The first frame's time and each scene change's, in seconds."""
    rc, _, err = run(["ffmpeg", "-hide_banner", "-nostats", "-i", video, "-an", "-vf",
                      f"select='eq(n\\,0)+gt(scene\\,{SCENE})',showinfo", "-fps_mode", "vfr", "-f", "null", "-"],
                     FFMPEG_TIMEOUT)
    if rc != 0:
        return []
    return sorted({round(float(t), 2) for t in re.findall(r"pts_time:\s*([\d.]+)", err)})


def pick_times(scenes, length, most=MAX_FRAMES, least=MIN_FRAMES):
    """At most `most` times: the first, then scene changes spread evenly; topped up to `least` with
    even times across the video, none within half a second of another."""
    times = list(scenes) or [0.0]
    if len(times) > most:
        step = (len(times) - 1) / (most - 1)
        times = [times[round(i * step)] for i in range(most)]
    if len(times) < least and length:
        for i in range(1, least + 1):
            t = round(length * i / (least + 1), 2)
            if len(times) >= least:
                break
            if all(abs(t - u) >= 0.5 for u in times):
                times.append(t)
    return sorted(times)


def grab(video, t, path):
    rc, _, _ = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-ss", f"{t:.2f}", "-i", video,
                    "-frames:v", "1", "-vf", f"scale={FRAME_WIDTH}:-2", "-q:v", "3", path], FFMPEG_TIMEOUT)
    return rc == 0 and os.path.exists(path) and os.path.getsize(path) > 0


def sheet(folder, first, count, path):
    """Frames first..first+count-1 side by side, SHEET_COLS a row, in reading order."""
    rc, _, _ = run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-start_number", str(first),
                    "-i", os.path.join(folder, "frame-%02d.jpg"), "-frames:v", "1", "-vf",
                    f"scale={SHEET_FRAME_WIDTH}:-2,tile={SHEET_COLS}x{SHEET_ROWS}:nb_frames={count}:padding=8:"
                    "color=white", "-q:v", "3", path], FFMPEG_TIMEOUT)
    return rc == 0 and os.path.exists(path)


def keep_lines(out):
    """One line each, lines with no word of 3 letters or digits dropped."""
    lines = [re.sub(r"\s+", " ", ln).strip() for ln in out.splitlines()]
    return "\n".join(ln for ln in lines if re.search(r"\w{3,}", ln))


def ocr(path):
    """The words tesseract reads on a frame."""
    rc, out, _ = run(["tesseract", path, "stdout", "--psm", "11"], OCR_TIMEOUT)
    return keep_lines(out) if rc == 0 else ""


def vision_reader():
    """The compiled Apple Vision reader, compiling it when missing or older than its source; None off a
    Mac or when it cannot be built."""
    if sys.platform != "darwin" or not shutil.which("xcrun"):
        return None
    exe = cache("bin", "vision_ocr")
    if os.path.exists(exe) and os.path.getmtime(exe) >= os.path.getmtime(VISION_SRC):
        return exe
    os.makedirs(os.path.dirname(exe), exist_ok=True)
    rc, _, err = run(["xcrun", "--sdk", "macosx", "swiftc", "-O", "-o", exe, VISION_SRC], COMPILE_TIMEOUT)
    if rc != 0 or not os.path.exists(exe):
        log("vision_unbuilt", msg=err.strip().splitlines()[-1] if err.strip() else "swiftc failed")
        return None
    log("vision_built", exe=exe)
    return exe


def vision(paths):
    """path → the words Apple Vision reads on that frame; {} when it is not available."""
    exe = vision_reader()
    if not exe or not paths:
        return {}
    rc, out, _ = run([exe] + list(paths), VISION_TIMEOUT)
    if rc != 0:
        return {}
    found = {}
    for line in out.splitlines():
        try:
            row = json.loads(line)
        except ValueError:
            continue
        found[row.get("file")] = keep_lines(row.get("text") or "")
    return found


def read_words(folder, frames):
    """Fill each frame's `text` (tesseract) and `vision` (Apple Vision, when it runs)."""
    paths = [os.path.join(folder, f["file"]) for f in frames]
    seen = vision(paths)
    for f, path in zip(frames, paths):
        f["text"] = ocr(path)
        if path in seen:
            f["vision"] = seen[path]
        else:
            f.pop("vision", None)


def make_frames(code, video):
    """frames/ for one reel: frame-NN.jpg, sheet-N.jpg and text.json. Returns text.json's content, or None."""
    folder = os.path.join(media_dir(), code, "frames")
    if os.path.isdir(folder):
        shutil.rmtree(folder)
    os.makedirs(folder)
    length = duration(video)
    times = pick_times(scene_times(video), length)
    frames = []
    for t in times:
        name = f"frame-{len(frames) + 1:02d}.jpg"
        if grab(video, t, os.path.join(folder, name)):
            frames.append({"n": len(frames) + 1, "t": t, "file": name})
    if not frames:
        log("frames_none", shortcode=code)
        return None
    read_words(folder, frames)
    per = SHEET_COLS * SHEET_ROWS
    sheets = []
    for i in range(0, len(frames), per):
        name = f"sheet-{i // per + 1}.jpg"
        if sheet(folder, i + 1, min(per, len(frames) - i), os.path.join(folder, name)):
            sheets.append({"file": name, "frames": [f["n"] for f in frames[i:i + per]]})
    info = {"video": f"{code}/video.mp4", "seconds": length, "frames": frames, "sheets": sheets}
    rpl.write_json(os.path.join(folder, "text.json"), info)
    log("frames_done", shortcode=code, frames=len(frames), sheets=len(sheets),
        words=sum(len(f["text"].split()) for f in frames),
        vision_words=sum(len((f.get("vision") or "").split()) for f in frames))
    return info


def retext(code, info):
    """Read the words again on a reel's frames already made, and rewrite its text.json."""
    folder = os.path.join(media_dir(), code, "frames")
    frames = [f for f in info.get("frames") or [] if os.path.exists(os.path.join(folder, f["file"]))]
    read_words(folder, frames)
    rpl.write_json(os.path.join(folder, "text.json"), info)
    log("frames_text", shortcode=code, frames=len(frames), words=sum(len(f["text"].split()) for f in frames),
        vision_words=sum(len((f.get("vision") or "").split()) for f in frames))


def frame_info(code):
    path = os.path.join(media_dir(), code, "frames", "text.json")
    try:
        with open(path, encoding="utf-8") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


# --- batches -------------------------------------------------------------------------------------

def state_areas(tag, places):
    """For a save tagged with a state only: every town, park and region in places.yaml inside it."""
    states = {c for c in (tag or {}).get("cities") or [] if (places.get(c) or {}).get("kind") == "state"}
    return [a for a in (rpl.exact_area(n, places) for n, p in sorted(places.items())
                        if isinstance(p, dict) and p.get("in") in states) if a]


def record(save, tag, places, info):
    folder = os.path.join(media_dir(), save["code"])
    areas = rpl.areas_of(tag, places)
    rec = rpl.record(save, areas or state_areas(tag, places))
    rec["state_only"] = not areas
    rec["sheets"] = [{"path": os.path.join(folder, "frames", s["file"]), "frames": s["frames"]}
                     for s in info["sheets"]]
    cover = os.path.join(folder, "cover.jpg")
    if os.path.exists(cover):
        rec["cover"] = cover
    rec["frame_text"] = {str(f["n"]): rpl.frame_words(f) for f in info["frames"] if rpl.frame_words(f)}
    return rec


def read_done():
    """Codes whose frame answers are merged already, from the merged answers files."""
    done = set()
    for path in glob.glob(os.path.join(batch_dir(), "batch-*.answers.merged.json")):
        answers, _ = rpl.read_answers(path)
        done |= set(answers)
    return done


def last_number():
    nums = [int(m.group(1)) for p in os.listdir(batch_dir())
            for m in [re.match(r"batch-(\d{3})\.answers\.merged\.json$", p)] if m]
    return max(nums, default=0)


def prepare(args, saves, tags, places, media):
    out = batch_dir()
    waiting = sorted(glob.glob(os.path.join(out, "batch-[0-9][0-9][0-9].answers.json")))
    if waiting:
        sys.exit(f"{len(waiting)} answers files are not merged yet ({os.path.basename(waiting[0])}...): "
                 "run resolve_post_location.py --merge --frames first")
    listed = os.path.join(frames_dir(), "stuck.txt")
    if not os.path.exists(listed):
        sys.exit(f"no {listed}: run --stuck first")
    for tool in ("ffmpeg", "ffprobe", "tesseract"):
        if not shutil.which(tool):
            sys.exit(f"{tool} is not on PATH (brew install ffmpeg tesseract)")
    by_code = {s["code"]: s for s in saves}
    done = read_done()
    recs, no_video, made = [], 0, 0
    for code in read_codes(listed):
        entry = media.get(code) or {}
        if code not in by_code or not entry.get("video"):
            no_video += 1
            continue
        if code in done and not args.redo:
            continue
        info = None if args.redo else frame_info(code)
        if info is None:
            info = make_frames(code, os.path.join(media_dir(), entry["video"]))
            made += 1
        if info and info.get("sheets"):
            recs.append(record(by_code[code], tags.get(code), places, info))
    os.makedirs(out, exist_ok=True)
    for old in glob.glob(os.path.join(out, "batch-[0-9][0-9][0-9].json")):  # a new round replaces the last one
        os.remove(old)
    batches = [recs[i:i + args.batch_saves] for i in range(0, len(recs), args.batch_saves)]
    for i, chunk in enumerate(batches, last_number() + 1):  # after the merged ones, so no name is reused
        name = f"batch-{i:03d}"
        path = os.path.join(out, name + ".json")
        rpl.write_json(path, {"batch": name, "answers": os.path.join(out, name + ".answers.json"), "saves": chunk})
        print(path)
    log("frames_prepare", reels=len(recs), frames_made=made, batches=len(batches), no_video=no_video,
        read_before=len(done))
    print(f"{len(recs)} reels in {len(batches)} batches ({made} had frames made); {no_video} listed reels have no "
          "video yet")
    return 0


def text_again():
    listed = os.path.join(frames_dir(), "stuck.txt")
    if not os.path.exists(listed):
        sys.exit(f"no {listed}: run --stuck first")
    if not shutil.which("tesseract"):
        sys.exit("tesseract is not on PATH (brew install tesseract)")
    reels = 0
    for code in read_codes(listed):
        info = frame_info(code)
        if info:
            retext(code, info)
            reels += 1
    have = "with Apple Vision" if vision_reader() else "tesseract only (no Apple Vision here)"
    log("frames_text_done", reels=reels)
    print(f"words read again on {reels} reels' frames, {have}")
    return 0


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    action = ap.add_mutually_exclusive_group(required=True)
    action.add_argument("--stuck", action="store_true", help="write the list of reels to read")
    action.add_argument("--prepare", action="store_true", help="frames, text, sheets and batch files")
    action.add_argument("--text", action="store_true", help="read the words again on frames already made")
    scope = ap.add_mutually_exclusive_group()
    scope.add_argument("--pilot", help="a pilot name from config/collections.yaml")
    scope.add_argument("--all", action="store_true", help="every save")
    ap.add_argument("--redo", action="store_true", help="make frames again for reels that have them")
    ap.add_argument("--batch-saves", type=int, default=BATCH_SAVES, help="most saves in one batch")
    ap.add_argument("--saved", default=None, help="saves.json (default: the data repo's .cache)")
    args = ap.parse_args(argv)
    if args.text:
        return text_again()
    with open(args.saved or cache("saves.json"), encoding="utf-8") as fh:
        saves = json.load(fh)["saves"]
    tags, media = load_yaml(rpl.TAGS), load_yaml(MEDIA)
    places = load_yaml(rpl.PLACES).get("places") or {}
    if args.stuck:
        if not (args.pilot or args.all):
            ap.error("--stuck needs --pilot NAME or --all")
        pilot = None
        if args.pilot:
            pilots = load_yaml(os.path.join("config", "collections.yaml")).get("pilots") or {}
            if args.pilot not in pilots:
                sys.exit(f"no pilot {args.pilot!r} in config/collections.yaml (have: {', '.join(pilots) or 'none'})")
            pilot = pilots[args.pilot]
        rows = stuck(saves, tags, places, media, load_yaml(rpl.PINS), load_yaml(rpl.REVIEW), load_yaml(rpl.NO_SPOT),
                     pilot)
        path = write_stuck(rows)
        whys = {}
        for _, why in rows:
            whys[why] = whys.get(why, 0) + 1
        log("frames_stuck", scope=args.pilot or "all", reels=len(rows))
        print(f"{len(rows)} reels to read: " + "; ".join(f"{n} {w}" for w, n in whys.items()))
        print(path)
        return 0
    return prepare(args, saves, tags, places, media)


if __name__ == "__main__":
    sys.exit(main())
