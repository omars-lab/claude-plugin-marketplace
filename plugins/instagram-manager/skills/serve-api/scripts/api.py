#!/usr/bin/env python3
"""api.py — the saved posts and their places as a local data API, for other hubs to read and for
the hub to manage the data through. Runs in Docker (../docker/compose.yaml), bound to 127.0.0.1.

    uvicorn api:app --app-dir <this folder> --host 0.0.0.0 --port 8000 [--reload]   (compose runs this)
    python3 api.py --schema DIR     write one JSON Schema file per model in contract.py into DIR

Read   /v1/areas, /v1/areas/{area}     the travel areas (states, countries), as out/travel/<area>.yaml
       /v1/topics, /v1/topics/{topic}  the other topics, as out/<topic>.yaml
       /v1/saves, /v1/saves/{code}     saves with every area's spots together; filters
       /v1/spots                       every location, one row per spot; filters, and within km of a
                                       point (lat, lon) or of a saved spot's Google place (google_id)
       /v1/manage/decisions            everything waiting on a person, as the decisions page lists it
       /media/{path}                   a thumbnail, still or clip, when the media folder is mounted
Write  PUT  /v1/manage/tags/{code}            a save's topics, places and purposes (`by: hand`)
       POST /v1/manage/review/{code}/{index}  ok, drop or lookup for a spot OpenStreetMap missed
       POST /v1/manage/google/{key}           none or chain for a spot's Google place
       POST /v1/manage/reload                 read the data again now
Docs   /docs (Swagger), /redoc, /openapi.json, /schema, /schema/{name}.json (JSON Schema per model)

The answers come from send-topics' own code (send_topics.load), so the API and the out/ files say the
same thing. A write goes through the same functions as the make targets (tag-saves' and
resolve-post-location's writers, find-google-ids' choose), and is refused when it would add a problem
`make check` reports. Writes need the X-Hub-Token header: API_TOKEN, else the token in
$INSTAGRAM_HOME/.cache/api-token (made on first start; git ignores .cache).

Nothing here fetches from Instagram, calls Google or runs a model: picking a Google place needs the
key, so that answer is the `make google-ids` line to run instead.

Hot reload: the data files are polled every API_POLL_S seconds (default 2; 0 turns it off) and read
again when one changes; a failed read keeps the data before it and says why on /health. A file that
iCloud has not downloaded yet (a .name.icloud placeholder) holds the reload back rather than serving
part of the data. Code reload is uvicorn's --reload, which compose turns on.

Env    INSTAGRAM_HOME (the data folder), INSTAGRAM_MEDIA_DIR (optional), API_PILOT (one pilot's saves
       only), API_POLL_S, API_TOKEN, API_LOG (a log file, besides stderr)
"""

import argparse
import datetime as dt
import json
import math
import os
import secrets
import sys
import threading
import time
from contextlib import asynccontextmanager
from typing import List, Optional

HERE = os.path.dirname(os.path.abspath(__file__))
SKILLS = os.path.join(HERE, os.pardir, os.pardir)
sys.path.insert(0, os.path.join(SKILLS, os.pardir, "shared", "scripts"))
for skill in ("send-topics", "build-hub", "find-google-ids", "tag-saves", "resolve-post-location"):
    sys.path.insert(0, os.path.join(SKILLS, skill, "scripts"))
sys.path.insert(0, HERE)

from fastapi import Depends, FastAPI, Header, HTTPException, Query  # noqa: E402
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse  # noqa: E402

import build_hub as bh  # noqa: E402
import check_data  # noqa: E402
import contract as c  # noqa: E402
import decisions_page as dp  # noqa: E402
import google_ids as gi  # noqa: E402
import resolve_post_location as rpl  # noqa: E402
import send_topics as st  # noqa: E402
import tag_saves as ts  # noqa: E402
from home import cache, home  # noqa: E402
from log import log, log_to  # noqa: E402
from places import Places, load_yaml  # noqa: E402

VERSION = "1.0.0"
TAGS, REVIEW, GOOGLE = "data/tags.yaml", "data/pins-review.yaml", "data/google.yaml"
ELSEWHERE = os.path.join("docs", "tasks", "elsewhere.yaml")


# --- the data, read again when a file changes ------------------------------------------------------

def watched():
    """The files the answers come from: config/ and data/, the export copy, the Google to-pick list
    and the elsewhere list. iCloud placeholders (.name.icloud) are listed too, so they are seen."""
    out = []
    for d in ("config", "data"):
        folder = os.path.join(home(), d)
        for name in sorted(os.listdir(folder)) if os.path.isdir(folder) else []:
            if name.endswith((".yaml", ".icloud")):
                out.append(os.path.join(folder, name))
    for p in (cache("saves.json"), cache(gi.TO_PICK), os.path.join(home(), ELSEWHERE)):
        out += [p, os.path.join(os.path.dirname(p), "." + os.path.basename(p) + ".icloud")]
    return out


def signature():
    """((path, mtime, size) per file, [files iCloud has not downloaded yet])."""
    sig, waiting = [], []
    for p in watched():
        name = os.path.basename(p)
        if name.startswith(".") and name.endswith(".icloud"):
            if os.path.exists(p):
                waiting.append(name[1:-len(".icloud")])
            continue
        try:
            s = os.stat(p)
            sig.append((p, s.st_mtime_ns, s.st_size))
        except OSError:
            sig.append((p, None, None))
    return tuple(sig), waiting


def build(pilot):
    """Everything the read endpoints answer with, from send-topics' own records."""
    sender, _, _, _ = st.load(pilot)
    scope = st.pilot_scope([pilot]) if pilot else "every tagged save"
    files = {os.path.splitext(rel)[0]: sender.doc(rel, scope) for rel in sender.files}
    saves = {}
    for name in sorted(files):
        for e in files[name]["saves"]:
            a = saves.get(e["code"])
            if a is None:
                a = {k: v for k, v in e.items() if k not in ("also_in", "items", "places")}
                a.update(files=[], items=[], places=[])
                saves[e["code"]] = a
            a["files"].append(name)
            a["items"] += e.get("items") or []
            a["places"] += [p for p in e.get("places") or [] if p not in a["places"]]
    for a in saves.values():
        if not a["places"]:
            del a["places"]
    spots = [{**i, "code": e["code"], "area_file": name}
             for name in sorted(files) if name.startswith("travel/")
             for e in files[name]["saves"] for i in e.get("items") or []]
    return {"files": files, "saves": saves, "spots": spots, "scope": scope}


class Store:
    def __init__(self, pilot=None):
        self.pilot = pilot
        self.data, self.sig, self.error = None, None, None
        self.reloads, self.loaded_at, self.load_ms = 0, None, None
        self.lock = threading.Lock()

    def load(self, why):
        """Read the data again. False, with the reason in .error, when it could not; the data
        before stays served."""
        with self.lock:
            sig, waiting = signature()
            if waiting:
                self.error = f"iCloud has not downloaded {', '.join(waiting)} to this Mac yet"
                log("icloud_placeholder", files=",".join(waiting), msg="kept the data already loaded")
                return False
            t0 = time.monotonic()
            try:
                data = build(self.pilot)
            except Exception as e:   # a bad edit must not take the API down; /health says why
                self.sig, self.error = sig, f"{type(e).__name__}: {e}"
                log("reload_fail", why=why, error=self.error)
                return False
            self.data, self.sig, self.error = data, sig, None
            self.reloads += 1
            self.load_ms = int((time.monotonic() - t0) * 1000)
            self.loaded_at = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            log("reload", why=why, ms=self.load_ms, saves=len(data["saves"]), spots=len(data["spots"]))
            return True

    def check(self):
        """Read again if a file changed since the last read. True when it read."""
        sig, waiting = signature()
        if sig == self.sig and not waiting:
            return False
        return self.load("changed")

    def need(self):
        if self.data is None:
            raise HTTPException(503, f"no data loaded: {self.error or 'not started'}")
        return self.data


STORE = Store(os.environ.get("API_PILOT") or None)


def poll(stop, every):
    while not stop.wait(every):
        try:
            STORE.check()
        except Exception as e:   # the poller must outlive one bad read
            log("poll_fail", error=f"{type(e).__name__}: {e}")


def token():
    """API_TOKEN, else the one in .cache/api-token, made on first use (readable by its owner only)."""
    t = os.environ.get("API_TOKEN")
    if t:
        return t
    path = cache("api-token")
    try:
        with open(path, encoding="utf-8") as fh:
            got = fh.read().strip()
        if got:
            return got
    except OSError:
        pass
    os.makedirs(os.path.dirname(path), exist_ok=True)
    got = secrets.token_urlsafe(24)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(got + "\n")
    log("api_token_made", file=path)
    return got


@asynccontextmanager
async def lifespan(_app):
    if os.environ.get("API_LOG"):
        log_to(os.environ["API_LOG"])
    log("api_start", home=home(), pilot=STORE.pilot or "", version=VERSION)
    token()
    STORE.load("start")
    stop = threading.Event()
    every = float(os.environ.get("API_POLL_S", "2"))
    if every > 0:
        threading.Thread(target=poll, args=(stop, every), daemon=True).start()
    yield
    stop.set()


app = FastAPI(
    title="Saved places data API", version=VERSION, lifespan=lifespan,
    description="Saved Instagram posts and the places they name, read from the data folder. The read "
                "answers have the same shape as the send-topics files (`out/travel/<area>.yaml`, "
                "`out/<topic>.yaml`); `/schema` lists a JSON Schema per model. Writes need the "
                "`X-Hub-Token` header, from `.cache/api-token` in the data folder. Local only: the server "
                "listens on 127.0.0.1.")
app.add_middleware(CORSMiddleware, allow_origin_regex=r"^http://(localhost|127\.0\.0\.1)(:\d+)?$",
                   allow_methods=["GET", "POST", "PUT"], allow_headers=["X-Hub-Token", "Content-Type"])

READ = {"response_model_exclude_none": True}


def need_token(x_hub_token: Optional[str] = Header(None, description="The token in .cache/api-token.")):
    if not x_hub_token or not secrets.compare_digest(x_hub_token, token()):
        raise HTTPException(401, "send the token from .cache/api-token in the X-Hub-Token header")


# --- read -------------------------------------------------------------------------------------------

@app.get("/", include_in_schema=False)
def root():
    return RedirectResponse("/docs")


@app.get("/health", response_model=c.Health, tags=["about"], **READ)
def health():
    d = STORE.data
    return {"ok": d is not None and STORE.error is None, "loaded_at": STORE.loaded_at, "load_ms": STORE.load_ms,
            "reloads": STORE.reloads, "saves": len(d["saves"]) if d else 0, "spots": len(d["spots"]) if d else 0,
            "scope": d["scope"] if d else None, "error": STORE.error}


def summary(name, doc):
    return {"file": name, "topic": doc["topic"], "area": doc.get("area"), "feeds": doc["feeds"],
            "saves": doc["count"], "spots": sum(len(s.get("items") or []) for s in doc["saves"])}


@app.get("/v1/areas", response_model=List[c.FileSummary], tags=["read"], **READ)
def areas():
    """The travel areas (states and countries), each with how many saves and spots."""
    files = STORE.need()["files"]
    return [summary(n, files[n]) for n in sorted(files) if n.startswith("travel/")]


@app.get("/v1/areas/{area}", response_model=c.TopicFile, tags=["read"], **READ)
def area(area: str):
    """One area's saves and their spots there: the content of out/travel/<area>.yaml."""
    doc = STORE.need()["files"].get(f"travel/{area}")
    if doc is None:
        raise HTTPException(404, f"no area {area!r}; /v1/areas lists them")
    return doc


@app.get("/v1/topics", response_model=List[c.FileSummary], tags=["read"], **READ)
def topics():
    files = STORE.need()["files"]
    return [summary(n, files[n]) for n in sorted(files) if not n.startswith("travel/")]


@app.get("/v1/topics/{topic}", response_model=c.TopicFile, tags=["read"], **READ)
def topic(topic: str):
    """One topic's saves: the content of out/<topic>.yaml. Travel is split by area under /v1/areas."""
    doc = STORE.need()["files"].get(topic)
    if doc is None or topic.startswith("travel/"):
        raise HTTPException(404, f"no topic {topic!r}; /v1/topics lists them")
    return doc


def page(rows, limit, offset):
    return {"total": len(rows), "offset": offset, "limit": limit}, rows[offset:offset + limit]


@app.get("/v1/saves", response_model=c.SavesPage, tags=["read"], **READ)
def saves(topic: Optional[str] = None, area: Optional[str] = Query(None, description="an area's slug"),
          purpose: Optional[str] = None, creator: Optional[str] = None,
          place: Optional[str] = Query(None, description="a place it is tagged with"),
          limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)):
    rows = [s for _, s in sorted(STORE.need()["saves"].items())
            if (not topic or topic in s["topics"]) and (not area or f"travel/{area}" in s["files"])
            and (not purpose or purpose in (s.get("purposes") or []))
            and (not creator or s.get("creator") == creator) and (not place or place in (s.get("places") or []))]
    head, rows = page(rows, limit, offset)
    return {**head, "saves": rows}


@app.get("/v1/saves/{code}", response_model=c.SaveAll, tags=["read"], **READ)
def save(code: str):
    s = STORE.need()["saves"].get(code)
    if s is None:
        raise HTTPException(404, f"no tagged save {code!r}")
    return s


def km_between(lat1, lon1, lat2, lon2):
    """Great-circle distance in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = (math.sin((p2 - p1) / 2) ** 2
         + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2)
    return 6371.0 * 2 * math.asin(math.sqrt(a))


@app.get("/v1/spots", response_model=c.SpotsPage, tags=["read"], **READ)
def spots(area: Optional[str] = Query(None, description="an area's slug"), kind: Optional[str] = None,
          exact: Optional[bool] = Query(None, description="true: pinned at the spot; false: at its town"),
          near: Optional[str] = Query(None, description="the town, park or area, as the spot's `near`"),
          code: Optional[str] = None,
          lat: Optional[float] = Query(None, ge=-90, le=90, description="with lon: spots within `km` of here"),
          lon: Optional[float] = Query(None, ge=-180, le=180),
          google_id: Optional[str] = Query(None, description="spots within `km` of the saved spot that "
                                                             "carries this Google place id"),
          km: float = Query(5, gt=0, le=500, description="how far from lat/lon or google_id"),
          limit: int = Query(500, ge=1, le=5000), offset: int = Query(0, ge=0)):
    """Every location the saves name, one row per spot per save. With lat and lon, or google_id, only
    the pinned spots within `km`, nearest first, each with `km_away`. google_id works for a Google
    place one of the saves names; for any other place, look its position up and pass lat and lon."""
    every = STORE.need()["spots"]
    if (lat is None) != (lon is None):
        raise HTTPException(422, "lat and lon go together")
    if google_id and lat is not None:
        raise HTTPException(422, "give lat and lon, or google_id, not both")
    if google_id:
        at = next((s for s in every if s.get("google_id") == google_id and s.get("lat") is not None), None)
        if at is None:
            raise HTTPException(404, "no saved spot with a pin carries that Google place id; "
                                     "look its position up and pass lat and lon")
        lat, lon = at["lat"], at["lon"]
    rows = [s for s in every
            if (not area or s["area_file"] == f"travel/{area}") and (not kind or s.get("kind") == kind)
            and (exact is None or s["exact"] == exact) and (not near or s.get("near") == near)
            and (not code or s["code"] == code)]
    if lat is not None:
        rows = sorted(({**s, "km_away": round(km_between(lat, lon, s["lat"], s["lon"]), 3)}
                       for s in rows if s.get("lat") is not None and s.get("lon") is not None),
                      key=lambda s: s["km_away"])
        rows = [s for s in rows if s["km_away"] <= km]
    head, rows = page(rows, limit, offset)
    return {**head, "spots": rows}


@app.get("/media/{path:path}", tags=["read"])
def media(path: str):
    """A thumbnail, still or clip by the path the answers give, from INSTAGRAM_MEDIA_DIR."""
    root = os.environ.get("INSTAGRAM_MEDIA_DIR") or ""
    if not root or not os.path.isdir(root):
        raise HTTPException(404, "the media folder is not mounted")
    base = os.path.realpath(root)
    full = os.path.realpath(os.path.join(base, path))
    if not full.startswith(base + os.sep) or not os.path.isfile(full):
        raise HTTPException(404, "no such media file")
    return FileResponse(full)


@app.get("/schema", tags=["about"])
def schemas():
    """The JSON Schema of each model, by name."""
    return {name: f"/schema/{name}.json" for name in c.SCHEMAS}


@app.get("/schema/{name}.json", tags=["about"])
def schema(name: str):
    model = c.SCHEMAS.get(name)
    if model is None:
        raise HTTPException(404, f"no schema {name!r}; /schema lists them")
    return JSONResponse(json_schema(name, model))


def json_schema(name, model):
    return {"$schema": "https://json-schema.org/draft/2020-12/schema", "$id": f"{name}.schema.json",
            **model.model_json_schema(by_alias=True)}


# --- manage -----------------------------------------------------------------------------------------

WRITE = threading.Lock()


def guarded(rel, new):
    """Refuse a change that adds a problem `make check` would report."""
    key = lambda p: json.dumps(p, sort_keys=True)  # noqa: E731
    before = {key(p) for p in check_data.problems(quiet=True)}
    added = [p for p in check_data.problems({rel: new}, quiet=True) if key(p) not in before]
    if added:
        log("api_refused", file=rel, problems=len(added))
        raise HTTPException(422, {"message": f"not saved: it would add {len(added)} problem(s) to {rel}",
                                  "problems": added})


def done(rel, message, run=None, **kv):
    log("api_write", file=rel, **kv)
    STORE.load("write")
    return {"ok": True, "file": rel, "message": message, "run": run}


@app.get("/v1/manage/decisions", response_model=c.Decisions, tags=["manage"], **READ)
def decisions():
    """Everything waiting on a person: Google picks, spots to check, moves, merges, videos, links."""
    saves_path = cache("saves.json")
    saves_list = bh.load_saves(saves_path) if os.path.exists(saves_path) else []
    pins, review = load_yaml(os.path.join("data", "pins.yaml")), load_yaml(REVIEW)
    rows = dp.google_rows(dp.load_json(cache(dp.TO_PICK)), load_yaml(GOOGLE),
                          dp.spot_index(saves_list, pins, bh.placed_spots(review)))
    check, town = dp.open_review(review)
    moves = load_yaml(os.path.join("data", "moves.yaml"))
    try:
        links = dp.load_links(ELSEWHERE if os.path.exists(os.path.join(home(), ELSEWHERE)) else None)
    except SystemExit as e:
        raise HTTPException(500, str(e))
    return {
        "google": [{"key": r["key"], "query": r["query"], "codes": r["codes"], "ids": r["ids"]} for r in rows],
        "review": [{"code": code, "index": next(i for i, x in enumerate(review[code]) if x is e),
                    **{k: e.get(k) for k in ("said", "name", "near", "why")}} for code, e in check],
        "town_only": len(town),
        "moves": [{"code": k, **v} for k, v in sorted((moves if isinstance(moves, dict) else {}).items())
                  if isinstance(v, dict)],
        "answers_to_merge": dp.waiting_answers(cache("batches")),
        "videos_waiting": dp.videos_waiting(cache(os.path.join("frames", "stuck.txt")),
                                            load_yaml(os.path.join("data", "media.yaml"))),
        "elsewhere": links}


@app.put("/v1/manage/tags/{code}", response_model=c.Written, tags=["manage"], dependencies=[Depends(need_token)])
def put_tags(code: str, body: c.TagsIn):
    """Set a save's topics, places and purposes. Places sitting inside others gain them (a town
    gains its state), as tag-saves does. Marked `by: hand`, so no tagging round changes it."""
    with WRITE:
        tags = load_yaml(TAGS)
        places = Places.load()
        old = tags.get(code) if isinstance(tags.get(code), dict) else {}
        entry = {**old, "topics": sorted(set(body.topics)),
                 "cities": sorted(places.fold({places.resolve(p) or p for p in body.places})),
                 "source": old.get("source") or "hand", "by": "hand"}
        if body.purposes is not None:
            entry["purposes"] = sorted(set(body.purposes))
        new = {**tags, code: entry}
        guarded(TAGS, new)
        ts.write_yaml(TAGS, new)
    return done(TAGS, f"{code}: tags saved and marked by hand", code=code)


@app.post("/v1/manage/review/{code}/{index}", response_model=c.Written, tags=["manage"],
          dependencies=[Depends(need_token)])
def post_review(code: str, index: int, body: c.ReviewIn):
    """Decide on a spot OpenStreetMap did not find; `make locate-merge` applies it."""
    with WRITE:
        review = load_yaml(REVIEW)
        entries = review.get(code)
        if not isinstance(entries, list) or not 0 <= index < len(entries) or not isinstance(entries[index], dict):
            raise HTTPException(404, f"no spot {index} for {code} in {REVIEW}; /v1/manage/decisions lists them")
        e = {k: v for k, v in entries[index].items() if k not in ("ok", "drop", "lookup")}
        if body.action == "lookup":
            if not (body.name or "").strip():
                raise HTTPException(422, "lookup needs the name to search")
            e["lookup"] = body.name.strip()
        else:
            e[body.action] = True
        new = {**review, code: entries[:index] + [e] + entries[index + 1:]}
        guarded(REVIEW, new)
        rpl.write_yaml(REVIEW, new)
    return done(REVIEW, f"{code} spot {index}: {body.action} saved", run="make locate-merge",
                code=code, index=index, action=body.action)


@app.post("/v1/manage/google/{key:path}", response_model=c.Written, tags=["manage"],
          dependencies=[Depends(need_token)])
def post_google(key: str, body: c.GoogleIn):
    """Mark a spot's Google place: none of the candidates, or a chain whose branches all do. A pick
    is answered with the make line to run, since checking the id needs the key."""
    if body.verdict == "pick":
        pid = (body.place_id or "").strip()
        if not pid:
            raise HTTPException(422, "pick needs place_id")
        return JSONResponse(status_code=409, content={
            "ok": False, "file": GOOGLE, "run": f"make google-ids PILOT= PICK='{key}={pid}'",
            "message": "picking a place checks its id with Google, which needs the key; the key never "
                       "enters the API, so run this line in the data repo"})
    with WRITE:
        saves_path = cache("saves.json")
        if not os.path.exists(saves_path):
            raise HTTPException(503, "no .cache/saves.json; run make import first")
        review = load_yaml(REVIEW)
        spots_all = gi.spots_in_scope(bh.load_saves(saves_path), load_yaml(TAGS), load_yaml("data/pins.yaml"),
                                      bh.placed_spots(review), None)
        try:
            gi.choose(spots_all, {}, [key] if body.verdict == "none" else [],
                      [key] if body.verdict == "chain" else [], "hand", dt.date.today().isoformat())
        except ValueError as e:
            raise HTTPException(404, str(e))
    return done(GOOGLE, f"{key}: marked {body.verdict}", key=key, verdict=body.verdict)


@app.post("/v1/manage/reload", response_model=c.Health, tags=["manage"], dependencies=[Depends(need_token)],
          **READ)
def reload():
    """Read the data again now, without waiting for the next poll."""
    STORE.load("asked")
    return health()


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--schema", metavar="DIR", required=True, help="write <name>.schema.json per model here")
    args = ap.parse_args(argv)
    os.makedirs(args.schema, exist_ok=True)
    for name, model in c.SCHEMAS.items():
        with open(os.path.join(args.schema, f"{name}.schema.json"), "w", encoding="utf-8") as fh:
            json.dump(json_schema(name, model), fh, indent=2, ensure_ascii=False)
            fh.write("\n")
    print(f"wrote {len(c.SCHEMAS)} schema files in {args.schema}")


if __name__ == "__main__":
    main()
