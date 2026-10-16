"""purposes.py — what a saved post is for: eat, stay, get outdoors, or see something.

The hub's Purpose menu and the save-tagger share this list. A post gets a purpose two ways: from
the kinds of place it names (a café is "eat", a park "adventure"), and from the tagger reading it.

    from purposes import load, NO_PURPOSE
    load()      # slug → {label, about, kinds[]}: config/purposes.yaml when there, else PURPOSES

config/purposes.yaml, when there, takes the place of the list below (same shape, under `purposes:`).
"""

import os

import yaml

from home import home

PURPOSES = {
    "eat": {"label": "Eat & drink", "about": "a restaurant, café, bar, bakery, winery or food to try",
            "kinds": ["restaurant", "cafe", "coffee", "bakery", "fast_food", "bar", "pub", "ice_cream", "food_court",
                      "winery", "brewery", "marketplace"]},
    "stay": {"label": "Stay", "about": "a hotel, cabin, campsite or other place to sleep",
             "kinds": ["hotel", "motel", "guest_house", "hostel", "resort", "camp_site", "caravan_site", "chalet",
                       "apartment"]},
    "adventure": {"label": "Adventure & outdoors",
                  "about": "a hike, beach, park, waterfall, viewpoint, swim, climb or road trip",
                  "kinds": [
        "park", "beach", "waterfall", "viewpoint", "peak", "cliff", "lake", "footway", "path", "track", "cycleway",
        "nature_reserve", "protected_area", "national_park", "meadow", "wood", "forest", "stream", "river", "islet",
        "island", "tree", "cave_entrance", "hot_spring", "spring", "glacier", "volcano", "valley", "bay", "cape",
        "arch", "rock", "dune", "picnic_site", "trailhead"]},
    "see-do": {"label": "See & do", "about": "a museum, sight, landmark, garden, show, market or town to walk",
               "kinds": [
        "museum", "aquarium", "zoo", "theme_park", "attraction", "artwork", "gallery", "pier", "lighthouse", "bridge",
        "tower", "garden", "castle", "monument", "memorial", "ruins", "place_of_worship", "playground", "water_park",
        "theatre", "marina"]},
}
NO_PURPOSE = ("none", "Not worked out yet")


def load():
    path = os.path.join(home(), "config", "purposes.yaml")
    if os.path.exists(path):
        with open(path, encoding="utf-8") as fh:
            got = (yaml.safe_load(fh) or {}).get("purposes")
        if isinstance(got, dict) and got:
            return {k: v for k, v in got.items() if isinstance(v, dict)}
    return PURPOSES
