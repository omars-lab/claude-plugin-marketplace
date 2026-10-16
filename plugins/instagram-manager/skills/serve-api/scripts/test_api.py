#!/usr/bin/env python3
"""Offline checks for api.py and contract.py, on an invented data repo in a temp folder. No network.
Needs fastapi and httpx, so it runs inside the API's image:

    make -C <data repo> api-test        (docker compose run --rm api python3 .../test_api.py)

Every code, handle, collection and place name here is made up (this plugin is public).
"""

import contextlib
import io
import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, "send-topics", "scripts"))
sys.path.insert(0, HERE)
import yaml  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import api  # noqa: E402
import contract as c  # noqa: E402
import send_topics  # noqa: E402
import test_send_topics as fx  # noqa: E402

TOKEN = {"X-Hub-Token": "test-token"}
# One spot whose map lookup gave a doubtful answer: a person decides it on the decisions page.
REVIEW = {**fx.REVIEW, "CAFE1": [{"name": "Example Mill", "said": "the old mill", "near": "Fixture Town",
                                  "why": "the caption's town is not the one found"}]}
IN_FILES = len(fx.TAGS) - 1   # NONE1 is tagged travel with no place, so no file lists it


class Api(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = os.path.join(self.tmp.name, "home")
        self.media = os.path.join(self.tmp.name, "media")
        for rel, data in (("config/topics.yaml", fx.TOPICS), ("config/collections.yaml", fx.COLLECTIONS),
                          ("data/places.yaml", fx.PLACES), ("data/tags.yaml", fx.TAGS), ("data/pins.yaml", fx.PINS),
                          ("data/pins-review.yaml", REVIEW), ("data/media.yaml", fx.MEDIA),
                          ("data/stills.yaml", fx.STILLS), ("data/items.yaml", fx.ITEMS)):
            self.write(rel, data)
        self.write(".cache/saves.json", {"saves": fx.SAVES, "collections": [{"name": n} for n in fx.COLLECTIONS["collections"]]})
        self.write(".cache/google-to-pick.json", {"osm:way/7": {"query": "Example Cove Beach, Fixture Town",
                                                                "ids": ["EXAMPLE_ID_1", "EXAMPLE_ID_2"]}})
        os.makedirs(os.path.join(self.media, "TRIP1"))
        with open(os.path.join(self.media, "TRIP1", "thumb.jpg"), "wb") as fh:
            fh.write(b"\xff\xd8 not really a jpeg")
        with open(os.path.join(self.tmp.name, "secret.txt"), "w") as fh:
            fh.write("outside the media folder")
        self.env = {k: os.environ.get(k) for k in ("INSTAGRAM_HOME", "INSTAGRAM_MEDIA_DIR", "API_POLL_S", "API_TOKEN",
                                                   "API_LOG")}
        os.environ.pop("API_LOG", None)   # the container's log is the real data folder's; keep test lines out
        os.environ.update(INSTAGRAM_HOME=self.root, INSTAGRAM_MEDIA_DIR=self.media, API_POLL_S="0",
                          API_TOKEN="test-token")
        api.STORE = api.Store()
        self.err = contextlib.redirect_stderr(io.StringIO())
        self.err.__enter__()
        self.client = TestClient(api.app)
        self.client.__enter__()

    def tearDown(self):
        self.client.__exit__(None, None, None)
        self.err.__exit__(None, None, None)
        for k, v in self.env.items():
            if v is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = v
        self.tmp.cleanup()

    def write(self, rel, data):
        path = os.path.join(self.root, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w") as fh:
            json.dump(data, fh) if rel.endswith(".json") else yaml.safe_dump(data, fh)

    def read(self, rel):
        with open(os.path.join(self.root, rel)) as fh:
            return yaml.safe_load(fh)

    def get(self, url, code=200):
        r = self.client.get(url)
        self.assertEqual(r.status_code, code, r.text)
        return r.json()

    # --- the contract --------------------------------------------------------------------------------

    def test_every_sent_file_fits_the_contract(self):
        with contextlib.redirect_stdout(io.StringIO()):
            send_topics.main(["--all"])
        out = os.path.join(self.root, "out")
        files = [os.path.join(d, f) for d, _, fs in os.walk(out) for f in fs if f.endswith(".yaml")]
        self.assertGreaterEqual(len(files), 4)
        for path in files:
            with open(path) as fh:
                c.TopicFile.model_validate(yaml.safe_load(fh))

    def test_a_new_field_in_the_files_fails_the_contract(self):
        doc = self.get("/v1/areas/fixture-state")
        doc["saves"][0]["caption"] = "a field the contract does not name"
        with self.assertRaises(Exception):
            c.TopicFile.model_validate(doc)

    def test_area_answer_is_the_sent_file(self):
        with contextlib.redirect_stdout(io.StringIO()):
            send_topics.main(["--all"])
        with open(os.path.join(self.root, "out", "travel", "fixture-state.yaml")) as fh:
            self.assertEqual(self.get("/v1/areas/fixture-state"), yaml.safe_load(fh))

    def test_checked_in_schema_files_match_the_models(self):
        folder = os.path.join(HERE, os.pardir, "schema")
        self.assertEqual(sorted(os.listdir(folder)), sorted(f"{n}.schema.json" for n in c.SCHEMAS))
        for name, model in c.SCHEMAS.items():
            with open(os.path.join(folder, f"{name}.schema.json")) as fh:
                self.assertEqual(json.load(fh), api.json_schema(name, model), f"run api.py --schema for {name}")
            self.assertEqual(self.get(f"/schema/{name}.json"), api.json_schema(name, model))

    def test_docs_and_openapi(self):
        self.assertEqual(self.client.get("/docs").status_code, 200)
        spec = self.get("/openapi.json")
        for path in ("/v1/areas", "/v1/saves", "/v1/spots", "/v1/manage/decisions", "/v1/manage/tags/{code}"):
            self.assertIn(path, spec["paths"])
        self.assertIn("/schema/spot.json", self.get("/schema").values())

    # --- read ----------------------------------------------------------------------------------------

    def test_health(self):
        h = self.get("/health")
        self.assertTrue(h["ok"])
        self.assertEqual(h["saves"], IN_FILES)
        self.assertNotIn("error", h)

    def test_areas_and_topics(self):
        self.assertEqual([a["file"] for a in self.get("/v1/areas")], ["travel/fixture-state", "travel/other-state"])
        self.assertEqual({t["file"] for t in self.get("/v1/topics")}, {"recipes", "crafts"})
        recipes = next(t for t in self.get("/v1/topics") if t["file"] == "recipes")
        self.assertGreaterEqual(recipes["items"], 2)                         # a topic's dishes are items,
        self.assertEqual(recipes["spots"], 0)                                # never spots
        area = self.get("/v1/areas")[0]
        self.assertEqual(area["spots"], area["items"])
        self.get("/v1/areas/nowhere", 404)
        self.get("/v1/topics/travel/fixture-state", 404)
        self.assertEqual({s["code"] for s in self.get("/v1/topics/recipes")["saves"]},
                         {"CAFE1", "BOTH1", "SOUP1", "SOUP2"})

    def test_a_save_across_areas_has_all_its_spots(self):
        s = self.get("/v1/saves/ROAD1")
        self.assertEqual(s["files"], ["travel/fixture-state", "travel/other-state"])
        self.assertEqual(sorted(i["name"] for i in s["items"]), ["Example Bluff", "Example Pier", "Example Point"])
        self.assertNotIn("also_in", s)
        self.get("/v1/saves/NOPE1", 404)

    def test_a_topic_save_has_its_split_items(self):
        soup = self.get("/v1/topics/recipes")["saves"]
        self.assertEqual([i["kind"] for s in soup if s["code"] == "SOUP1" for i in s["items"]], ["dish", "dish"])
        both = self.get("/v1/saves/BOTH1")["items"]
        self.assertIn({"topic": "recipes", "kind": "dish", "name": "Example picnic salad", "quote": "picnic salad"}, both)

    def test_save_filters_and_paging(self):
        self.assertEqual({s["code"] for s in self.get("/v1/saves?topic=recipes&area=fixture-state")["saves"]}, {"BOTH1"})
        self.assertEqual([s["code"] for s in self.get("/v1/saves?purpose=eat")["saves"]], ["TRIP1"])
        p = self.get("/v1/saves?limit=2&offset=1")
        self.assertEqual((p["total"], len(p["saves"]), p["offset"]), (IN_FILES, 2, 1))

    def test_spots(self):
        rows = self.get("/v1/spots?area=fixture-state")["spots"]
        self.assertIn(("TRIP1", "Example Cove Beach"), {(r["code"], r["name"]) for r in rows})
        self.assertTrue(all(r["area_file"] == "travel/fixture-state" for r in rows))
        town = self.get("/v1/spots?exact=false")["spots"]
        self.assertTrue(town and all("lat" not in r for r in town))

    def test_spots_near_a_point(self):
        rows = self.get("/v1/spots?lat=10.51&lon=20.51&km=5")["spots"]
        self.assertEqual((rows[0]["name"], rows[0]["km_away"]), ("Example Cove Beach", 0.0))
        self.assertEqual([r["km_away"] for r in rows], sorted(r["km_away"] for r in rows))
        self.assertTrue(all(r["km_away"] <= 5 for r in rows))
        self.assertNotIn("Example Point", {r["name"] for r in rows})        # about 47 km away
        self.assertIn("Example Point", {r["name"] for r in self.get("/v1/spots?lat=10.51&lon=20.51&km=100")["spots"]})
        self.assertNotIn("km_away", self.get("/v1/spots?area=fixture-state")["spots"][0])
        self.get("/v1/spots?lat=10.51", 422)                                 # lat and lon go together
        self.get("/v1/spots?lat=91&lon=0", 422)

    def test_spots_near_a_google_place(self):
        self.write("data/google.yaml", {"osm:node/8": {"query": "Example Point, Fixture Coast", "verdict": "match",
                                                       "id": "ChIJexamplePoint", "by": "auto", "date": "2026-01-02"}})
        self.assertEqual(self.client.post("/v1/manage/reload", headers=TOKEN).status_code, 200)
        rows = self.get("/v1/spots?google_id=ChIJexamplePoint&km=3")["spots"]
        self.assertEqual((rows[0]["name"], rows[0]["km_away"]), ("Example Point", 0.0))
        self.assertIn("Example Bluff", {r["name"] for r in rows})            # about 1.5 km away
        self.assertNotIn("Example Cove Beach", {r["name"] for r in rows})
        self.get("/v1/spots?google_id=ChIJnotOneOfOurs", 404)                # look it up, pass lat and lon
        self.get("/v1/spots?google_id=ChIJexamplePoint&lat=1&lon=1", 422)

    def test_media_stays_in_its_folder(self):
        self.assertEqual(self.client.get("/media/TRIP1/thumb.jpg").status_code, 200)
        self.assertEqual(self.client.get("/media/../secret.txt").status_code, 404)
        self.assertEqual(self.client.get("/media/%2e%2e/secret.txt").status_code, 404)
        self.assertEqual(self.client.get("/media/TRIP1/nothing.jpg").status_code, 404)

    # --- hot reload ----------------------------------------------------------------------------------

    def test_an_edited_file_is_read_again(self):
        self.assertFalse(api.STORE.check())
        tags = self.read("data/tags.yaml")
        tags["SOUP1"]["topics"] = ["crafts"]
        self.write("data/tags.yaml", tags)
        self.assertTrue(api.STORE.check())
        self.assertEqual([s["code"] for s in self.get("/v1/topics/crafts")["saves"]], ["SOUP1"])

    def test_a_broken_file_keeps_the_data_before(self):
        with open(os.path.join(self.root, "data", "tags.yaml"), "a") as fh:
            fh.write("\n  : : not yaml [\n")
        self.assertFalse(api.STORE.check())
        h = self.get("/health")
        self.assertFalse(h["ok"])
        self.assertTrue(h["error"])
        self.assertEqual(h["saves"], IN_FILES)
        self.assertFalse(api.STORE.check(), "the same broken file is not read again and again")

    def test_a_file_icloud_has_not_downloaded_holds_the_reload(self):
        os.remove(os.path.join(self.root, "data", "stills.yaml"))
        open(os.path.join(self.root, "data", ".stills.yaml.icloud"), "w").close()
        self.assertFalse(api.STORE.check())
        h = self.get("/health")
        self.assertIn("stills.yaml", h["error"])
        self.assertEqual(h["spots"], len(api.STORE.data["spots"]))
        self.assertTrue(any(i.get("still") for i in self.get("/v1/saves/TRIP1")["items"]),
                        "the stills already loaded are still served")

    def test_reload_now(self):
        r = self.client.post("/v1/manage/reload", headers=TOKEN)
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["reloads"], 2)

    # --- manage --------------------------------------------------------------------------------------

    def test_writes_need_the_token(self):
        body = {"topics": ["travel"], "places": ["Fixture Town"]}
        self.assertEqual(self.client.put("/v1/manage/tags/NONE1", json=body).status_code, 401)
        self.assertEqual(self.client.put("/v1/manage/tags/NONE1", json=body,
                                         headers={"X-Hub-Token": "wrong"}).status_code, 401)
        self.assertEqual(self.client.post("/v1/manage/reload").status_code, 401)

    def test_set_tags_by_hand(self):
        r = self.client.put("/v1/manage/tags/NONE1", headers=TOKEN,
                            json={"topics": ["travel"], "places": ["Fixture Town"], "purposes": ["eat"]})
        self.assertEqual(r.status_code, 200, r.text)
        t = self.read("data/tags.yaml")["NONE1"]
        self.assertEqual((t["cities"], t["by"], t["purposes"]), (["Fixture State", "Fixture Town"], "hand", ["eat"]))
        self.assertEqual(self.get("/v1/saves/NONE1")["places"], ["Fixture Town"])

    def test_tags_that_would_break_the_data_are_refused(self):
        before = self.read("data/tags.yaml")
        r = self.client.put("/v1/manage/tags/NONE1", headers=TOKEN,
                            json={"topics": ["travel"], "places": ["Nowhere Land"]})
        self.assertEqual(r.status_code, 422, r.text)
        self.assertEqual(r.json()["detail"]["problems"][0]["city"], "Nowhere Land")
        self.assertEqual(self.read("data/tags.yaml"), before)

    def test_tags_need_a_known_body(self):
        r = self.client.put("/v1/manage/tags/NONE1", headers=TOKEN, json={"topics": ["travel"], "places": [], "x": 1})
        self.assertEqual(r.status_code, 422)

    def test_decisions(self):
        d = self.get("/v1/manage/decisions")
        self.assertEqual([(x["code"], x["index"]) for x in d["review"]], [("CAFE1", 0)])
        self.assertEqual(d["town_only"], 1)
        self.assertEqual([g["key"] for g in d["google"]], ["osm:way/7"])

    def test_review_ok(self):
        r = self.client.post("/v1/manage/review/CAFE1/0", headers=TOKEN, json={"action": "ok"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(r.json()["run"], "make locate-merge")
        self.assertTrue(self.read("data/pins-review.yaml")["CAFE1"][0]["ok"])
        self.assertEqual(self.get("/v1/manage/decisions")["review"], [])

    def test_review_lookup_and_bad_index(self):
        r = self.client.post("/v1/manage/review/CAFE1/0", headers=TOKEN, json={"action": "lookup", "name": "Example Mill Cafe"})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(self.read("data/pins-review.yaml")["CAFE1"][0]["lookup"], "Example Mill Cafe")
        self.assertEqual(self.client.post("/v1/manage/review/CAFE1/0", headers=TOKEN,
                                          json={"action": "lookup"}).status_code, 422)
        self.assertEqual(self.client.post("/v1/manage/review/CAFE1/5", headers=TOKEN,
                                          json={"action": "ok"}).status_code, 404)

    def test_google_none(self):
        r = self.client.post("/v1/manage/google/osm:way/7", headers=TOKEN, json={"verdict": "none"})
        self.assertEqual(r.status_code, 200, r.text)
        kept = self.read("data/google.yaml")["osm:way/7"]
        self.assertEqual((kept["verdict"], kept["by"], kept["query"]), ("none", "hand", "Example Cove Beach, Fixture Town"))
        self.assertEqual(self.get("/v1/manage/decisions")["google"], [])

    def test_google_pick_answers_with_the_make_line(self):
        r = self.client.post("/v1/manage/google/osm:way/7", headers=TOKEN,
                             json={"verdict": "pick", "place_id": "EXAMPLE_ID_1"})
        self.assertEqual(r.status_code, 409)
        self.assertEqual(r.json()["run"], "make google-ids PILOT= PICK='osm:way/7=EXAMPLE_ID_1'")
        self.assertFalse(os.path.exists(os.path.join(self.root, "data", "google.yaml")))

    def test_google_unknown_spot(self):
        r = self.client.post("/v1/manage/google/osm:way/999", headers=TOKEN, json={"verdict": "chain"})
        self.assertEqual(r.status_code, 404)


if __name__ == "__main__":
    unittest.main()
