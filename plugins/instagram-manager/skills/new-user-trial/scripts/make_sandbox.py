#!/usr/bin/env python3
"""make_sandbox.py — an empty home and an invented Instagram export, for a new-user trial.

    make_sandbox.py --out <dir>             make <dir> (it must not exist yet)
    make_sandbox.py --out <dir> --saves 20  only the first 20 saves (a smaller trial)

Writes
    <dir>/downloads/instagram-example_wanderer-2026-10-01-Ab12Cd.zip
                        an export in Instagram's HTML shape: saved posts and saved collections,
                        plus messages, likes and saved music that the importer must never open
    <dir>/home/         empty: the newcomer's data folder (INSTAGRAM_HOME)
    <dir>/media/        empty: where thumbnails and videos would go (INSTAGRAM_MEDIA_DIR)
    <dir>/shots/        empty: screenshots the tester takes
    <dir>/run           runs one command inside the sandbox: INSTAGRAM_HOME, INSTAGRAM_MEDIA_DIR,
                        INSTAGRAM_OFFLINE=1 and the map fixture set, from <dir>/home
    <dir>/.harness/geocode.json   OpenStreetMap-shaped answers for the invented places, so the
                        map gets pins with no network (geocode.py reads it when offline)
    <dir>/.harness/README.md      what the harness is; the tester treats it as scenery

Every person, place, post code and collection here is made up (this plugin is public). The
places sit in an invented state, Westmark, at points on dry land, so no pin lands on water.
The saves are chosen to be awkward the way real ones are: a list naming five cafés, a place only
in a hashtag, a caption in Spanish, an empty caption, a giveaway, a post in two collections, one
only in a collection, two collections with the same name, a recipe that carries a town's hashtag.

Standard library only.
"""

import argparse
import html
import json
import os
import stat
import sys
import zipfile
import zlib

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, "..", "..", "import-saves", "scripts"))
import test_import_saved as shape  # noqa: E402  (the HTML templates the importer is tested against)

ZIP_NAME = "instagram-example_wanderer-2026-10-01-Ab12Cd.zip"

W = ("example_wanderer", "Example Wanderer")
EATS = ("westmark_eats_demo", "Westmark Eats | Food guide", "https://example.com/westmark-eats")
TRAIL = ("trail_notes_demo", "Trail Notes")
COOK = ("kitchen_demo_daily", "Demo Kitchen")
HOME = ("cozy_rooms_demo", "Cozy Rooms")
BIZ = ("side_hustle_demo", "Side Hustle Coach")
MISC = ("random_reels_demo", "Random Reels")

# (kind, code, caption, hashtags, owner, saved time, collections)
SAVES = [
    ("reel", "DEMOa000001", "Top 5 cafés in Port Alder ☕️\n1. The Copper Kettle\n2. Bluebird Bakery\n"
     "3. Fern & Fog Coffee\n4. Harbor Bean\n5. Saltgrass Taqueria (they do café de olla!)\nSave this for your trip",
     ["portalder", "westmarkfood"], EATS, "Sep 28, 2026 8:15 pm", ["Westmark trip", "Food"]),
    ("reel", "DEMOa000002", "Sunset at Alder Bay Beach never misses 🌅 Park at the north lot, walk 5 min.",
     ["westmark", "beachday"], W, "Sep 27, 2026 6:02 pm", ["Westmark trip"]),
    ("reel", "DEMOa000003", "This waterfall is only 1.2 miles in 👀 #hiddengem",
     ["hollowfalls", "cedarhollow", "hiddengem"], TRAIL, "Sep 26, 2026 9:41 am", ["Westmark trip"]),
    ("reel", "DEMOa000004", "Juniper Peak Trail: 6 miles round trip, 1,800 ft of climbing, views the whole way. "
     "Start early, there is no shade. Trailhead is off Route 9 just past Juniper Flats.",
     ["hiking", "westmark"], TRAIL, "Sep 25, 2026 7:30 am", ["Westmark trip", "Hikes"]),
    ("p", "DEMOa000005", "", [], W, "Sep 24, 2026 11:11 pm", ["Westmark trip"]),
    ("reel", "DEMOa000006", "We stayed at the Driftwood Inn in Port Alder and woke up to this. Book the ocean-view room.",
     ["portalder", "travel"], W, "Sep 23, 2026 4:20 pm", ["Westmark trip"]),
    ("reel", "DEMOa000007", "Silverpine Lake in October 🍂 kayaks rent by the hour at the dock",
     ["silverpine", "fallcolors"], TRAIL, "Sep 22, 2026 2:00 pm", ["Hikes"]),
    ("reel", "DEMOa000008", "Climb the Port Alder Lighthouse (142 steps!) then get chowder across the street.",
     ["westmark"], EATS, "Sep 21, 2026 1:05 pm", ["Westmark trip", "Food"]),
    ("reel", "DEMOa000009", "Los mejores tacos de Westmark están en Saltgrass Taqueria 🌮 pidan los de birria",
     ["tacos", "portalder"], EATS, "Sep 20, 2026 9:00 pm", ["Food"]),
    ("reel", "DEMOa000010", "Ridgeview Overlook at golden hour. That's it, that's the post.",
     ["ridgeviewoverlook", "silverpine"], MISC, "Sep 19, 2026 7:45 pm", ["Westmark trip"]),
    ("reel", "DEMOa000011", "3 day road trip through Westmark: Port Alder → Cedar Hollow → Juniper Flats → Silverpine. "
     "Full itinerary in my bio link!", ["westmarkdrive"], W, "Sep 18, 2026 10:10 am", ["Westmark trip"]),
    ("reel", "DEMOa000012", "Brown butter blondies, one bowl, 30 minutes. Recipe:\n- 1 cup butter, browned\n"
     "- 1 cup brown sugar\n- 2 eggs\n- 1.5 cups flour\nBake 25 min at 350°F.",
     ["baking", "portalder"], COOK, "Sep 17, 2026 8:30 pm", ["Recipes 🍝"]),
    ("reel", "DEMOa000013", "Weeknight lemon garlic pasta 🍋 ready in 15. Comment PASTA and I'll DM you the recipe",
     ["pasta", "easyrecipes"], COOK, "Sep 16, 2026 6:45 pm", ["Recipes 🍝"]),
    ("reel", "DEMOa000014", "How to make cold brew at home: coarse grind, 1:8 ratio, 16 hours in the fridge.",
     ["coffee", "coldbrew"], COOK, "Sep 15, 2026 7:00 am", ["Recipes 🍝", "Food"]),
    ("reel", "DEMOa000015", "Sourdough starter day 1 to day 7, everything I wish I knew",
     ["sourdough"], COOK, "Sep 14, 2026 9:20 am", ["Recipes 🍝"]),
    ("p", "DEMOa000016", "Limewash walls + a jute rug = instant calm. Paint is a warm greige, two coats.",
     ["interiordesign", "limewash"], HOME, "Sep 13, 2026 3:33 pm", ["Home ideas"]),
    ("reel", "DEMOa000017", "Small entryway hack: a floating shelf and three hooks. Total cost $40.",
     ["smallspaces", "entryway"], HOME, "Sep 12, 2026 12:12 pm", ["Home ideas"]),
    ("p", "DEMOa000018", "Our reading nook: built-in bench, storage drawers underneath, a sconce on each side.",
     ["readingnook"], HOME, "Sep 11, 2026 5:55 pm", ["Home ideas"]),
    ("reel", "DEMOa000019", "5 things I'd do if I opened a coffee cart tomorrow:\n1. Start at farmers markets\n"
     "2. Keep the menu to 6 drinks\n3. Price for 70% margin\n4. Collect emails from day one\n5. Partner with a local bakery",
     ["smallbusiness", "coffeecart"], BIZ, "Sep 10, 2026 8:08 am", ["Side hustle"]),
    ("reel", "DEMOa000020", "Stop undercharging. Here's the pricing formula I teach every client: cost × 3, then test.",
     ["pricing", "entrepreneur"], BIZ, "Sep 09, 2026 1:01 pm", ["Side hustle"]),
    ("reel", "DEMOa000021", "GIVEAWAY 🎉 Follow, like and tag 3 friends to win a $500 gift card! Ends Friday",
     ["giveaway", "contest"], MISC, "Sep 08, 2026 4:44 pm", []),
    ("reel", "DEMOa000022", "POV: you finally organized your camera roll",
     ["relatable"], MISC, "Sep 07, 2026 10:30 pm", ["Misc"]),
    ("reel", "DEMOa000023", "Read this if you need a sign today ✨ small steps still count.",
     ["motivation"], MISC, "Sep 06, 2026 6:06 am", ["Misc"]),
    ("reel", "DEMOa000024", "Cedar Hollow farmers market every Saturday 8–1. Get the peach hand pies at the Bluebird Bakery stand.",
     ["cedarhollow", "farmersmarket"], EATS, "Sep 05, 2026 9:15 am", ["Food", "Westmark trip"]),
    ("reel", "DEMOa000025", "Easy 3D printed cable clips, free file in my profile",
     ["3dprinting"], MISC, "Sep 04, 2026 7:07 pm", ["Misc"]),
    ("reel", "DEMOa000026", "Toddler activity that bought me 45 minutes: a tray of rice and measuring cups.",
     ["toddleractivities", "momlife"], MISC, "Sep 03, 2026 2:22 pm", ["Misc"]),
    ("reel", "DEMOa000027", "Juniper Flats has the best stargazing in the state. Bring a red flashlight.",
     ["junipersky"], TRAIL, "Sep 02, 2026 11:59 pm", ["Hikes", "Westmark trip"]),
    ("reel", "DEMOa000028", "Harbor Bean's honey lavender latte 💜 worth the line",
     ["portalder"], EATS, "Sep 01, 2026 10:00 am", ["Food"]),
    ("reel", "DEMOa000029", "Where we ate in Westmark: Saltgrass Taqueria, The Copper Kettle, and a food truck I can't remember the name of.",
     ["westmark", "foodie"], W, "Aug 31, 2026 8:00 pm", ["Westmark trip", "Food"]),
    ("reel", "DEMOa000030", "Swipe for the trail map 🗺️", ["hollowfalls"], TRAIL, "Aug 30, 2026 8:30 am", ["Hikes"]),
    ("p", "DEMOa000031", "Kitchen before and after. We kept the cabinets and only swapped the hardware and paint.",
     ["kitchenreno", "beforeandafter"], HOME, "Aug 29, 2026 5:00 pm", ["Home ideas"]),
    ("reel", "DEMOa000032", "Meal prep Sunday: 5 lunches, 1 sheet pan, under $30.",
     ["mealprep"], COOK, "Aug 28, 2026 11:00 am", ["Recipes 🍝"]),
    ("reel", "DEMOa000033", "If you visit one place in Silverpine, make it the Ridgeview Overlook. If two, add Silverpine Lake.",
     ["silverpine"], TRAIL, "Aug 27, 2026 6:30 pm", ["Westmark trip"]),
    ("reel", "DEMOa000034", "Online shop month 3 numbers: $2,140 in sales, $610 profit. What worked and what didn't.",
     ["shopnumbers"], BIZ, "Aug 26, 2026 9:45 pm", ["Side hustle"]),
    ("reel", "DEMOa000035", "The Driftwood Inn breakfast is included and it slaps",
     ["portalder"], W, "Aug 25, 2026 9:05 am", []),
]
# Only in a collection (not in the saved list): Instagram exports have these.
ONLY = [("reel", "DEMOa000036", "Fern & Fog Coffee does a cardamom bun on weekends only",
         ["portalder"], EATS, ["Food"])]
# Two collections with the same name: people make them by accident.
DUPLICATE = ("Westmark trip", ["DEMOa000010", "DEMOa000033"])

PRIVATE = {
    "your_instagram_activity/messages/inbox/demo_friend/message_1.html":
        shape.page("Messages", "<p>HARNESS: a private message. The importer must never open this file.</p>"),
    "your_instagram_activity/likes/liked_posts.html": shape.page("Liked posts", "<p>HARNESS: likes, never opened.</p>"),
    "your_instagram_activity/saved/saved_music.html": shape.page("Saved music", ""),
    "personal_information/personal_information/personal_information.html":
        shape.page("Personal information", "<p>HARNESS: account details, never opened.</p>"),
}


def esc(caption):
    return html.escape(caption, quote=False).replace("@", "&#064;")


def build_zip(path, saves):
    by_code = {s[1]: s for s in saves}
    posts = [(k, c, esc(cap), tags, who, when) for k, c, cap, tags, who, when, _ in saves]
    names = []
    for s in saves:
        for col in s[6]:
            if col not in names:
                names.append(col)
    cols = []
    for name in names:
        members = [(s[0], s[1], esc(s[2]), s[3], s[4]) for s in saves if name in s[6]]
        members += [(k, c, esc(cap), tags, who) for k, c, cap, tags, who, in_cols in ONLY if name in in_cols]
        cols.append((name, members))
    dup_name, dup_codes = DUPLICATE
    dup = [(by_code[c][0], c, esc(by_code[c][2]), by_code[c][3], by_code[c][4]) for c in dup_codes if c in by_code]
    if dup:
        cols.append((dup_name, dup))
    files = {"your_instagram_activity/saved/saved_posts.html": shape.posts_page(posts),
             "your_instagram_activity/saved/saved_collections.html": shape.collections_page(cols)}
    files.update(PRIVATE)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, text in files.items():
            z.writestr(name, text)
    return len(posts), len(cols)


def hit(name, lat, lon, addresstype, category, typ, town=None, box=0.01, importance=0.3):
    address = {"state": "Westmark", "country": "United States", "country_code": "us"}
    if town:
        address["town"] = town
    parts = [name] + ([town] if town and town != name else []) + ["Westmark", "United States"]
    return {"name": name, "display_name": ", ".join(parts), "lat": str(lat), "lon": str(lon),
            "addresstype": addresstype, "category": category, "type": typ, "importance": importance,
            "address": address, "osm_type": "node", "osm_id": zlib.crc32(name.encode()),
            "boundingbox": [str(lat - box), str(lat + box), str(lon - box), str(lon + box)]}


# Points in dry country, far from the sea, so the hub's water check never fires on the fixture.
GEOCODE = [
    hit("Westmark", 39.9, -117.3, "state", "boundary", "administrative", box=1.2, importance=0.7),
    hit("Port Alder", 40.30, -117.80, "town", "place", "town", "Port Alder", box=0.05, importance=0.5),
    hit("Cedar Hollow", 39.70, -117.10, "town", "place", "town", "Cedar Hollow", box=0.05, importance=0.45),
    hit("Juniper Flats", 39.40, -117.60, "village", "place", "village", "Juniper Flats", box=0.04, importance=0.4),
    hit("Silverpine", 40.10, -116.70, "town", "place", "town", "Silverpine", box=0.05, importance=0.45),
    hit("The Copper Kettle", 40.301, -117.802, "amenity", "amenity", "cafe", "Port Alder"),
    hit("Bluebird Bakery", 40.298, -117.797, "shop", "shop", "bakery", "Port Alder"),
    hit("Fern & Fog Coffee", 40.304, -117.806, "amenity", "amenity", "cafe", "Port Alder"),
    hit("Harbor Bean", 40.296, -117.809, "amenity", "amenity", "cafe", "Port Alder"),
    hit("Saltgrass Taqueria", 40.307, -117.795, "amenity", "amenity", "restaurant", "Port Alder"),
    hit("Driftwood Inn", 40.311, -117.812, "tourism", "tourism", "hotel", "Port Alder"),
    hit("Port Alder Lighthouse", 40.318, -117.820, "man_made", "man_made", "lighthouse", "Port Alder"),
    hit("Alder Bay Beach", 40.322, -117.790, "natural", "natural", "beach", "Port Alder"),
    hit("Hollow Falls", 39.715, -117.130, "natural", "waterway", "waterfall", "Cedar Hollow"),
    hit("Juniper Peak Trail", 39.420, -117.640, "highway", "highway", "path", "Juniper Flats"),
    hit("Silverpine Lake", 40.120, -116.680, "natural", "natural", "water", "Silverpine"),
    hit("Ridgeview Overlook", 40.090, -116.720, "tourism", "tourism", "viewpoint", "Silverpine"),
]

RUN = """#!/bin/sh
# Runs one command inside the sandbox: its own data folder, its own media folder, no network.
export INSTAGRAM_HOME="{home}"
export INSTAGRAM_MEDIA_DIR="{media}"
export INSTAGRAM_OFFLINE=1
export INSTAGRAM_GEOCODE_FIXTURE="{fixture}"
cd "$INSTAGRAM_HOME" || exit 1
exec "$@"
"""

HARNESS_README = """# The trial harness

This folder belongs to the trial, not to the newcomer being played.

- `geocode.json` stands in for OpenStreetMap: the plugin's lookups read it when
  `INSTAGRAM_OFFLINE` is set, so the invented places get map pins with no network.
- `../run` sets the sandbox's folders and the offline switch for one command.

A newcomer would have neither. When a step works only because of them, say so in the diary.
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", required=True, help="the sandbox folder to make; it must not exist yet")
    ap.add_argument("--saves", type=int, default=len(SAVES), help=f"how many saves (default all {len(SAVES)})")
    args = ap.parse_args(argv)

    out = os.path.abspath(os.path.expanduser(args.out))
    if os.path.exists(out):
        sys.exit(f"make_sandbox: {out} already exists; pick a new folder so no earlier trial is overwritten")
    for sub in ("downloads", "home", "media", "shots", ".harness"):
        os.makedirs(os.path.join(out, sub))
    n_posts, n_cols = build_zip(os.path.join(out, "downloads", ZIP_NAME), SAVES[:max(1, args.saves)])
    fixture = os.path.join(out, ".harness", "geocode.json")
    with open(fixture, "w", encoding="utf-8") as fh:
        json.dump(GEOCODE, fh, ensure_ascii=False, indent=1)
    with open(os.path.join(out, ".harness", "README.md"), "w", encoding="utf-8") as fh:
        fh.write(HARNESS_README)
    run = os.path.join(out, "run")
    with open(run, "w", encoding="utf-8") as fh:
        fh.write(RUN.format(home=os.path.join(out, "home"), media=os.path.join(out, "media"), fixture=fixture))
    os.chmod(run, os.stat(run).st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"ev=sandbox out={out} saves={n_posts} only_in_collection={len(ONLY)} collections={n_cols} "
          f"places={len(GEOCODE)}")
    print(f"export: {os.path.join(out, 'downloads', ZIP_NAME)}")
    print(f"run a command inside it: {run} <command>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
