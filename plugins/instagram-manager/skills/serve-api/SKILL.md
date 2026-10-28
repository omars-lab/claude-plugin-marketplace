---
name: serve-api
description: Run the saved posts and their places as a local data API in Docker on 127.0.0.1, so other hubs and apps can list every Instagram location (by state or country, topic, save or spot) and the hub can make its decisions (tags, review answers, Google place none or chain) through it. Swagger at /docs, the OpenAPI spec at /openapi.json and one JSON Schema per model at /schema. Reloads by itself when a data file or the code changes. Use when another project should read the saves over HTTP instead of the out/ files, when someone asks what the API returns or how to start, stop, test or change it, or when its schema files need writing again.
---

# Serve API

The data repo's saves, places and spots as a small web API on this Mac only. Other hubs read it
instead of copying `out/`; the hub can send its decisions through it. It answers from send-topics'
own code, so `/v1/areas/<area>` says what `out/travel/<area>.yaml` says, field for field.

Track the work with `TaskCreate`: one task per step below, each marked done as it finishes.

## What it serves

| Path | What |
|---|---|
| `GET /v1/areas`, `/v1/areas/{area}` | each state or country: as `out/travel/<area>.yaml` |
| `GET /v1/topics`, `/v1/topics/{topic}` | each other topic: as `out/<topic>.yaml` |
| `GET /v1/saves`, `/v1/saves/{code}` | saves with all their spots together; filter by `topic`, `area`, `purpose`, `creator`, `place`; `limit`, `offset` |
| `GET /v1/spots` | every location, one row per spot; filter by `area`, `kind`, `exact`, `near` (the town), `code`. Within `km` (default 5) of a point (`lat`, `lon`) or of a saved spot's Google place (`google_id`): pinned spots only, nearest first, each with `km_away` |
| `GET /media/{path}` | a thumbnail, still or clip from the media folder (read only) |
| `GET /v1/manage/decisions` | what waits on a person: Google picks, review spots, town-only spots, moves, decisions elsewhere |
| `PUT /v1/manage/tags/{code}` | a save's topics, places and purposes, written `by: hand` |
| `POST /v1/manage/review/{code}/{index}` | `ok`, `drop` or `lookup` for a spot OpenStreetMap missed |
| `POST /v1/manage/google/{key}` | `none` or `chain` for a spot's Google place; `pick` answers with the `make google-ids` line to run |
| `POST /v1/manage/reload` | read the data again now |
| `GET /health` | counts, when the data was read, and the last reload error if any |
| `/docs`, `/redoc`, `/openapi.json`, `/schema`, `/schema/{name}.json` | the contract: Swagger, the spec, one JSON Schema per model |

**Writes** need the `X-Hub-Token` header: `API_TOKEN`, else `.cache/api-token` in the data repo
(made on first start, readable by its owner only). Never print the token; send it as
`-H "X-Hub-Token: $(cat .cache/api-token)"`. A write goes through the same functions as the make
targets and is refused (422, with the problems) when `make check` would report something new.
Nothing is written then.

**Near a Google place.** `google_id` works when one of the saves names that place (its id is kept in
`data/google.yaml`); the centre is then the spot's own OpenStreetMap pin. For any other place the caller
looks its position up itself and passes `lat` and `lon`. The server keeps no request log (uvicorn's
`--no-access-log`), so a position from Google never lands in a log.

**Never in the API:** anything that fetches from Instagram, the Google key (picking a Google place
needs it, so that stays a `make google-ids` line), and model steps. The server binds to
`127.0.0.1` only; putting it online is a separate decision that needs Omar's OK in chat.

**Hot reload.** Every `API_POLL_S` seconds (default 2) it checks the data files and reads them again
when one changed (`ev=reload why=changed` in `.cache/api.log`). A failed read keeps the data before
it and says why on `/health` (`ev=reload_fail`). A file iCloud has not downloaded yet holds the
reload back (`ev=icloud_placeholder`). A code edit in the plugin restarts the server by itself.

## Steps

1. **Start.** It needs Docker running. `make api` in your saves folder builds the image and starts
   the container; it prints the address (`http://127.0.0.1:8780/docs`; `API_PORT=` for another
   port). `make api-logs` shows its last 50 lines, `make api-stop` stops it. By hand, from the folder:
   `INSTAGRAM_HOME=$PWD INSTAGRAM_MEDIA_DIR=<media folder> docker compose -f <plugin>/skills/serve-api/docker/compose.yaml up -d --build`.
2. **Look.** Open `/docs` and check `/health`: its save and spot counts should match the hub's.
   Try `/v1/areas/<one area>` against `out/travel/<that area>.yaml`.
3. **Before changing the API, read what its users ran into:** the data repo's `docs/api-feedback/`
   (`seen.yaml` counts each kind of call and trouble; each `<date>-<words>.md` is a note with
   `status: open`). When a change answers a note, set its `status: done` and `done_in:` the commit,
   or `status: no` with why. Callers' skills write there; the data repo's sessions commit it.
4. **After changing the code:** `make api-test` (the tests run in the container, since this Mac's
   python has no FastAPI), then `make api-schema` when a model in `contract.py` changed, and commit
   the schema files with the change.
5. **Stop.** `make api-stop`.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/api.py` | The API itself (FastAPI); also writes the schema files | Run by Docker; by hand only for `--schema` | `make api` / `make api-schema` (`python3 scripts/api.py --schema schema/`) |
| `scripts/contract.py` | The models: what each answer and each write looks like, strict, the same shape send-topics writes | Change it first when a field is added; then schema, tests and send-topics agree | (imported by `api.py`) |
| `scripts/test_api.py` | Offline tests on send-topics' invented data repo: every read against send-topics' own files, filters, paging, the schema files, media paths kept inside the folder, hot reload and a failed reload, writes with and without the token, a write refused by the check, review and Google answers | After any change here, or to send-topics, check_data or google_ids | `make api-test`. When Docker won't start: a Python 3.12 environment with `docker/requirements.txt` (`uv venv --python 3.12 <dir>`, `uv pip install --python <dir>/bin/python -r docker/requirements.txt`), then `<dir>/bin/python scripts/test_api.py`; the same for `api.py --schema` |
| `docker/Dockerfile`, `docker/compose.yaml` | The image and how it runs: the data folder at `/data`, the media folder read only at `/media`, the plugin's code over `/plugin` so edits reload | Run through the make targets | `make api`, `make api-stop`, `make api-logs` |

## What it can't do yet

- **The hub's buttons.** The decisions page still shows `make` lines; it does not call the API yet.
- **Picking a Google place**, on purpose: that needs the key, which stays out of the container.
- **Being reached from another machine.** Bound to `127.0.0.1`; see the plan's online-copy task.
