#!/usr/bin/env python3
"""heard.py — a trial: does what a reel says out loud tell us when each spot comes up? Many reels
never put a spot's name on screen (stills.yaml `how: not_on_screen`), so extract_stills.py has no
moment to cut its still at. This turns each reel's speech into words with their times, on this Mac
(whisper.cpp, no network, no account), and looks for each spot's name among them. It writes nothing
in data/; it only reports. On the first 19 reels it found none: they were music or silent, and the
one voice never said a name. So it stays a check to run on a new set of reels, not a step.

    heard.py [CODE ...]           the reels given, or every reel with a spot not on screen
    options: --model PATH         a whisper.cpp model (default .cache/whisper/models/ggml-small.en.bin)
             --prompt             give the model the reel's spot names first, so it spells them right
             --tag NAME           names this run's files (default: the model's name, plus -prompt)

Needs   whisper-cli (brew install whisper.cpp) and a model from
        https://huggingface.co/ggerganov/whisper.cpp (ggml-small.en.bin, 465 MB)
Reads   $INSTAGRAM_HOME/data/stills.yaml             the spots per reel, and when the ones on screen show
        $INSTAGRAM_HOME/data/media.yaml              each reel's video
        $INSTAGRAM_MEDIA_DIR/<code>/video.mp4
Writes  $INSTAGRAM_HOME/.cache/whisper/<code>.wav           the sound, 16 kHz mono (made once)
        $INSTAGRAM_HOME/.cache/whisper/<code>.<tag>.json    whisper's words, one per segment, with times
        $INSTAGRAM_HOME/.cache/whisper/trial-<tag>.json     what was found per spot, for the write-up

How a spot is found: its `said` and its `name`, as lowercase letters and digits, against every run of
as many heard words (and one more or one fewer), letters compared with difflib; a run scoring
MATCH or more is a hit, at the time of its first word. For spots that are on screen too, the report
gives how far the spoken time is from the on-screen one, as a check on the times.
"""

import argparse
import difflib
import json
import os
import re
import shutil
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(HERE, os.pardir, os.pardir)
sys.path.insert(0, os.path.join(SKILLS, os.pardir, "shared", "scripts"))
sys.path.insert(0, os.path.join(SKILLS, "read-frames", "scripts"))
import read_frames as rf  # noqa: E402
from home import cache, home  # noqa: E402
from log import log  # noqa: E402
from places import load_yaml  # noqa: E402

MEDIA_DEFAULT = "~/Library/Mobile Documents/com~apple~CloudDocs/CloudDesktop/data/instagram"
MATCH = 0.8
TIMEOUT = 600
# Words that say what kind of place it is, not which one: "Pfeiffer Beach" heard as "the beach" is no hit.
GENERIC = {"the", "a", "of", "at", "and", "beach", "park", "state", "national", "trail", "point", "lake",
           "falls", "cafe", "restaurant", "bar", "view", "vista", "overlook", "cove", "bay", "creek", "river"}


def media_dir():
    return os.path.expanduser(os.environ.get("INSTAGRAM_MEDIA_DIR") or MEDIA_DEFAULT)


def words_of(text):
    s = unicodedata.normalize("NFKD", str(text)).encode("ascii", "ignore").decode().lower()
    return re.findall(r"[a-z0-9]+", s.replace("'", ""))


def has_sound(video):
    rc, out, _ = rf.run(["ffprobe", "-v", "error", "-select_streams", "a", "-show_entries", "stream=index",
                         "-of", "csv=p=0", video], 30)
    return rc == 0 and bool(out.strip())


def sound(video, wav):
    if os.path.isfile(wav) and os.path.getsize(wav) > 0:
        return True
    rc, _, _ = rf.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-y", "-i", video, "-vn", "-ac", "1",
                       "-ar", "16000", wav], TIMEOUT)
    return rc == 0 and os.path.isfile(wav)


def listen(wav, model, base, prompt=None):
    """[(seconds, word)] from whisper-cli, one word per segment; and the seconds it took."""
    cmd = ["whisper-cli", "-m", model, "-f", wav, "-l", "en", "-ml", "1", "-sow", "-oj", "-of", base, "-np"]
    if prompt:
        cmd += ["--prompt", prompt]
    t0 = time.time()
    log("heard_start", file=os.path.basename(base))
    rc, _, err = rf.run(cmd, TIMEOUT)
    took = round(time.time() - t0, 1)
    log("heard_done", file=os.path.basename(base), rc=rc, seconds=took)
    if rc != 0 or not os.path.isfile(base + ".json"):
        return None, took
    with open(base + ".json", encoding="utf-8", errors="replace") as fh:
        segs = json.load(fh).get("transcription") or []
    heard = []
    for s in segs:
        for w in words_of(s.get("text", "")):
            heard.append((s["offsets"]["from"] / 1000.0, w))
    return heard, took


def find(terms, heard):
    """(score, seconds, the words heard) for the best run of heard words matching one of the terms."""
    best = (0.0, None, "")
    for term in terms:
        want = [w for w in words_of(term)]
        if not want or all(w in GENERIC for w in want):
            continue
        target = "".join(want)
        for n in {max(1, len(want) - 1), len(want), len(want) + 1}:
            for i in range(0, max(0, len(heard) - n + 1)):
                run = heard[i:i + n]
                if all(w in GENERIC for _, w in run):
                    continue
                score = difflib.SequenceMatcher(None, target, "".join(w for _, w in run)).ratio()
                if score > best[0]:
                    best = (score, run[0][0], " ".join(w for _, w in run))
    return best


def trial(codes, model, use_prompt, tag):
    stills = load_yaml(os.path.join(home(), "data", "stills.yaml"))
    media = load_yaml(os.path.join(home(), "data", "media.yaml"))
    folder = cache("whisper")
    os.makedirs(folder, exist_ok=True)
    report = []
    for code in codes:
        rows = [r for r in stills.get(code) or [] if isinstance(r, dict)]
        entry = media.get(code) or {}
        video = os.path.join(media_dir(), entry["video"]) if isinstance(entry.get("video"), str) else None
        got = {"code": code, "spots": len(rows), "hidden": sum(1 for r in rows if r.get("how") == "not_on_screen")}
        if not video or not os.path.isfile(video):
            report.append({**got, "result": "no video"})
            continue
        if not has_sound(video):
            report.append({**got, "result": "no sound"})
            continue
        wav = os.path.join(folder, code + ".wav")
        if not sound(video, wav):
            report.append({**got, "result": "sound not cut"})
            continue
        names = sorted({r["name"] for r in rows if isinstance(r.get("name"), str)})
        heard, took = listen(wav, model, os.path.join(folder, f"{code}.{tag}"),
                             ", ".join(names) if use_prompt else None)
        if heard is None:
            report.append({**got, "result": "whisper failed", "seconds": took})
            continue
        spots = []
        for r in rows:
            score, t, said = find([r.get("said"), r.get("name")], heard)
            spots.append({"name": r.get("name"), "how": r.get("how"), "screen_t": r.get("t"),
                          "score": round(score, 2), "t": t if score >= MATCH else None,
                          "heard": said if score >= MATCH else ""})
        report.append({**got, "result": "ok", "seconds": took, "words": len(heard),
                       "distinct": len({w for _, w in heard}), "spots_found": spots})
        log("heard", code=code, words=len(heard), hidden=got["hidden"],
            found=sum(1 for s in spots if s["t"] is not None and s["how"] == "not_on_screen"))
    with open(os.path.join(folder, f"trial-{tag}.json"), "w") as fh:
        json.dump(report, fh, indent=1)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("codes", nargs="*")
    ap.add_argument("--model", default=None)
    ap.add_argument("--prompt", action="store_true")
    ap.add_argument("--tag", default=None)
    args = ap.parse_args(argv)
    if not shutil.which("whisper-cli"):
        sys.exit("needs whisper-cli: brew install whisper.cpp")
    model = args.model or os.path.join(cache("whisper"), "models", "ggml-small.en.bin")
    if not os.path.isfile(model):
        sys.exit(f"no model at {model}: see https://huggingface.co/ggerganov/whisper.cpp")
    tag = args.tag or (os.path.basename(model).replace("ggml-", "").replace(".bin", "")
                       + ("-prompt" if args.prompt else ""))
    codes = args.codes or sorted(c for c, rows in load_yaml(os.path.join(home(), "data", "stills.yaml")).items()
                                 if any(isinstance(r, dict) and r.get("how") == "not_on_screen" for r in rows or []))
    total = {"hidden": 0, "found": 0, "seconds": 0.0}
    for r in trial(codes, model, args.prompt, tag):
        if r["result"] != "ok":
            print(f"{r['code']}: {r['result']} ({r['hidden']} of {r['spots']} spots not on screen)")
            total["hidden"] += r["hidden"]
            continue
        hidden = [s for s in r["spots_found"] if s["how"] == "not_on_screen"]
        found = [s for s in hidden if s["t"] is not None]
        shown = [s for s in r["spots_found"] if s["how"] == "on_screen" and s["t"] is not None and s["screen_t"] is not None]
        gap = (f"; said within {max(abs(s['t'] - s['screen_t']) for s in shown):.0f} s of on screen for "
               f"{len(shown)} shown spots") if shown else ""
        print(f"{r['code']}: {r['words']} words ({r['distinct']} different) in {r['seconds']} s; "
              f"{len(found)} of {len(hidden)} hidden spots heard{gap}")
        for s in hidden:
            print(f"    {'HIT ' if s['t'] is not None else 'miss'} {s['name']}"
                  + (f"  at {s['t']:.1f} s, heard \"{s['heard']}\" ({s['score']})" if s["t"] is not None
                     else f"  (best {s['score']})"))
        total["hidden"] += len(hidden)
        total["found"] += len(found)
        total["seconds"] += r["seconds"]
    print(f"total: {total['found']} of {total['hidden']} hidden spots heard; whisper took {total['seconds']:.0f} s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
