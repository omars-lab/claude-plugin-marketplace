#!/usr/bin/env python3
"""Offline checks for the new-user trial's sandbox and the INSTAGRAM_OFFLINE switch.

    python3 skills/new-user-trial/scripts/test_new_user_trial.py

The sandbox must import cleanly (the counts make_sandbox.py prints), never be written over, and
keep the plugin off the network: map lookups answer from its fixture, fetch-media refuses.
"""

import contextlib
import glob
import io
import json
import os
import re
import sys
import tempfile
import unittest
import urllib.error
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
PLUGIN = os.path.join(HERE, "..", "..", "..")
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(PLUGIN, "shared", "scripts"))
sys.path.insert(0, os.path.join(PLUGIN, "skills", "import-saves", "scripts"))
sys.path.insert(0, os.path.join(PLUGIN, "skills", "fetch-media", "scripts"))
import make_sandbox  # noqa: E402
import review_doc  # noqa: E402
import geocode  # noqa: E402
import import_saved  # noqa: E402
import fetch_media  # noqa: E402
import home  # noqa: E402
import setup_home  # noqa: E402
import check_data  # noqa: E402


def quiet(fn, *a, **kw):
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        return fn(*a, **kw)


class Sandbox(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.box = os.path.join(self.tmp.name, "trial")
        quiet(make_sandbox.main, ["--out", self.box])
        self.env = dict(os.environ)
        os.environ.update({"INSTAGRAM_HOME": os.path.join(self.box, "home"),
                           "INSTAGRAM_MEDIA_DIR": os.path.join(self.box, "media"),
                           "INSTAGRAM_OFFLINE": "1",
                           "INSTAGRAM_GEOCODE_FIXTURE": os.path.join(self.box, ".harness", "geocode.json")})

    def tearDown(self):
        os.environ.clear()
        os.environ.update(self.env)
        self.tmp.cleanup()

    def test_layout_and_home_starts_empty(self):
        for sub in ("downloads", "home", "media", "shots", ".harness", "run"):
            self.assertTrue(os.path.exists(os.path.join(self.box, sub)), sub)
        self.assertEqual(os.listdir(os.path.join(self.box, "home")), [])
        self.assertTrue(os.access(os.path.join(self.box, "run"), os.X_OK))

    def test_never_overwrites_a_sandbox(self):
        with self.assertRaises(SystemExit):
            quiet(make_sandbox.main, ["--out", self.box])

    def test_export_imports_with_the_expected_counts(self):
        zip_path = os.path.join(self.box, "downloads", make_sandbox.ZIP_NAME)
        out = os.path.join(self.box, "home", ".cache", "saves.json")
        self.assertEqual(quiet(import_saved.main, ["--from-zip", zip_path, "--out", out]), 0)
        with open(out, encoding="utf-8") as fh:
            data = json.load(fh)
        saves = data["saves"] if isinstance(data, dict) else data
        codes = {s["code"] for s in saves}
        self.assertEqual(len(codes), len(make_sandbox.SAVES) + len(make_sandbox.ONLY))
        self.assertIn("DEMOa000036", codes)  # only in a collection
        spanish = next(s for s in saves if s["code"] == "DEMOa000009")
        self.assertIn("están", spanish["caption"])
        self.assertIn("\n", next(s for s in saves if s["code"] == "DEMOa000001")["caption"])

    def test_export_has_private_files_the_importer_skips(self):
        with zipfile.ZipFile(os.path.join(self.box, "downloads", make_sandbox.ZIP_NAME)) as z:
            names = z.namelist()
        self.assertTrue(any("/messages/" in n for n in names))
        self.assertTrue(any(n.startswith("personal_information/") for n in names))

    def test_offline_lookups_answer_from_the_fixture_only(self):
        hits = quiet(geocode.fetch, "Bluebird Bakery, Port Alder, Westmark")
        self.assertEqual([h["name"] for h in hits], ["Bluebird Bakery"])
        with self.assertRaises(urllib.error.URLError):
            quiet(geocode.fetch, "Somewhere Real, Anywhere")

    def test_offline_viewbox_keeps_only_hits_inside(self):
        self.assertEqual(len(quiet(geocode.offline_hits, "Hollow Falls", "-117.2,39.8,-117.0,39.6")), 1)
        with self.assertRaises(urllib.error.URLError):
            quiet(geocode.offline_hits, "Hollow Falls", "-100.0,30.0,-99.0,29.0")

    def test_fixture_places_are_invented_and_inside_westmark(self):
        for h in make_sandbox.GEOCODE:
            self.assertEqual(h["address"]["state"], "Westmark")
            self.assertTrue(39 <= float(h["lat"]) <= 41 and -119 <= float(h["lon"]) <= -116, h["name"])

    def test_fetch_media_refuses_offline(self):
        self.assertEqual(quiet(fetch_media.main, ["--all", "--limit", "1"]), 2)


    def test_setup_copies_the_starter_config_and_keeps_what_is_there(self):
        target = os.path.join(self.box, "home")
        self.assertEqual(quiet(setup_home.setup, target), (list(setup_home.FILES), []))
        mine = os.path.join(target, "config", "topics.yaml")
        with open(mine, "w", encoding="utf-8") as fh:
            fh.write("topics: {mine: {label: Mine, about: x, feeds: []}}\n")
        copied, kept = quiet(setup_home.setup, target)
        self.assertEqual((copied, kept), ([], list(setup_home.FILES)))
        with open(mine, encoding="utf-8") as fh:
            self.assertIn("Mine", fh.read())

    def test_setup_writes_a_makefile_that_points_at_this_plugin(self):
        target = os.path.join(self.box, "home")
        quiet(setup_home.setup, target)
        with open(os.path.join(target, "Makefile"), encoding="utf-8") as fh:
            text = fh.read()
        self.assertNotIn("@PLUGIN@", text)
        self.assertIn(f"PLUGIN      ?= {os.path.abspath(setup_home.PLUGIN)}\n", text)

    def test_every_make_line_in_the_docs_is_a_target_in_the_starter_makefile(self):
        plugin = os.path.abspath(setup_home.PLUGIN)
        with open(os.path.join(plugin, "examples", "Makefile"), encoding="utf-8") as fh:
            targets = set(re.findall(r"^([a-z][a-z-]+):", fh.read(), re.M))
        # Targets only the author's own data repo has; the docs say so where they name them.
        own = {"comments", "check-public", "init-hooks", "gitleaks"}
        missing = []
        for path in glob.glob(os.path.join(plugin, "**", "*.md"), recursive=True):
            with open(path, encoding="utf-8") as fh:
                for name in re.findall(r"`make ([a-z][a-z-]+)", fh.read()):
                    if name not in targets and name not in own:
                        missing.append(f"{os.path.relpath(path, plugin)}: make {name}")
        self.assertEqual(missing, [])

    def test_starter_config_fits_and_names_the_collections_to_rename(self):
        target = os.path.join(self.box, "home")
        quiet(setup_home.setup, target)
        zip_path = os.path.join(self.box, "downloads", make_sandbox.ZIP_NAME)
        quiet(import_saved.main, ["--from-zip", zip_path, "--out", os.path.join(target, ".cache", "saves.json")])
        # The only complaints are the invented collections the export lacks, each saying to rename it.
        probs = quiet(check_data.problems, quiet=True)
        self.assertTrue(probs)
        for p in probs:
            self.assertEqual(p["file"], "config/collections.yaml", p)
            self.assertIn("rename it to one of yours", p["msg"])

    def test_missing_saves_and_empty_topics_say_what_to_do(self):
        err = io.StringIO()
        with self.assertRaises(SystemExit) as cm, contextlib.redirect_stderr(err):
            home.read_saves()
        self.assertIn("import_saved.py --from-zip", str(cm.exception.code))
        with self.assertRaises(SystemExit) as cm:
            home.need_topics({})
        self.assertIn("examples/config/topics.yaml", str(cm.exception.code))
        self.assertIsNone(home.need_topics({"travel": {}}))


class ReviewDoc(unittest.TestCase):
    """review_doc.py with --no-maps: no browser, no network."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        t = self.tmp.name
        self.box, self.out, self.media = (os.path.join(t, d) for d in ("box", "out", "media"))
        os.makedirs(os.path.join(self.box, "shots"))
        for name in ("map.png", "topic.png"):
            with open(os.path.join(self.box, "shots", name), "wb") as f:
                f.write(b"\x89PNG\r\n\x1a\n")
        with open(os.path.join(self.box, "review.md"), "w") as f:
            f.write("# Review\n\n![the map, first look](shots/map.png)\n\n"
                    "| # | Finding | Picture |\n|---|---|---|\n| F3 | No pins | shots/topic.png |\n\n"
                    "Again: shots/map.png and shots/gone.png.\n")

    def tearDown(self):
        self.tmp.cleanup()

    def test_pictures_point_at_the_media_folder_and_named_ones_show_after_their_block(self):
        quiet(review_doc.main, ["--sandbox", self.box, "--out", self.out, "--media", self.media, "--no-maps"])
        with open(os.path.join(self.out, "review.md")) as f:
            doc = f.read()
        media_map = review_doc.file_url(os.path.join(self.media, "shots", "map.png"))
        self.assertIn(f"![the map, first look]({media_map})", doc)
        # A picture only named in a table row is shown once, after the table, labelled by its finding.
        self.assertIn("![Finding F3: topic.png|700](" + review_doc.file_url(
            os.path.join(self.media, "shots", "topic.png")) + ")", doc)
        self.assertEqual(doc.count("|700]("), 1)
        self.assertNotIn("](shots/", doc)
        self.assertIn("shots/gone.png", doc)  # a missing picture stays as text
        self.assertTrue(os.path.isfile(os.path.join(self.media, "shots", "topic.png")))
        self.assertFalse(os.path.exists(os.path.join(self.out, "diary.md")))

    def test_a_post_row_is_named_by_its_creator_and_places(self):
        page = os.path.join(self.tmp.name, "DEMOa000001.html")
        pins = [[1, 2, f"Cafe {n}"] for n in range(6)]
        with open(page, "w") as f:
            f.write(f"<h1>@example_<b>wanderer</b></h1><script>var d={json.dumps(pins)};</script>")
        self.assertEqual(review_doc.page_name(page, "posts"),
                         "DEMOa000001 by @example_wanderer: Cafe 0, Cafe 1, Cafe 2, Cafe 3 and 2 more")
        self.assertEqual(review_doc.page_name(page, "places"), "@example_wanderer")


if __name__ == "__main__":
    unittest.main()
