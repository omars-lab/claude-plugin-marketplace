"""home.py — where the private data repo is, so scripts never write beside themselves.

Installed plugins run from the plugin cache, which is wiped on every update. Every script
therefore reads and writes in the data repo: $INSTAGRAM_HOME, or ~/Workspace/git/instagram.

    from home import home, cache
    home()                 # the data repo
    cache("saves.json")    # <data repo>/.cache/saves.json (gitignored there)
    offline()              # True when INSTAGRAM_OFFLINE is set: no script may reach the network
    read_saves()           # saves.json's contents, or a plain "run the import first" and exit
    need_topics(topics)    # exit with a plain message when config/topics.yaml lists no topics

INSTAGRAM_OFFLINE=1 is for trial runs and sandboxes (new-user-trial): OpenStreetMap lookups
fail as if the network were down (only answers already in the cache are used), and fetch-media
and find-google-ids refuse to run. Nothing reaches Instagram, Google or OpenStreetMap.
"""

import json
import os
import sys

DEFAULT = os.path.join("~", "Workspace", "git", "instagram")


def home():
    return os.path.abspath(os.path.expanduser(os.environ.get("INSTAGRAM_HOME") or DEFAULT))


def cache(*parts):
    return os.path.join(home(), ".cache", *parts)


def offline():
    return os.environ.get("INSTAGRAM_OFFLINE", "") not in ("", "0")


PLUGIN = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
IMPORT_CMD = f"python3 {os.path.join(PLUGIN, 'skills', 'import-saves', 'scripts', 'import_saved.py')} --from-zip <your export zip>"


def read_saves(path=None):
    """The whole saves.json (a dict with "saves"); one plain message for every script when it is missing."""
    path = path or cache("saves.json")
    if not os.path.exists(path):
        sys.exit(f"No saves yet: {path} is missing.\n"
                 f"Import your Instagram export first:\n  {IMPORT_CMD}\n"
                 f"(The import-saves skill says how to get the export. Saves go in INSTAGRAM_HOME, now {home()}.)")
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def need_topics(topics):
    """Stop when config/topics.yaml is missing or lists no topics: tagging with an empty list tags nothing."""
    if topics:
        return
    path = os.path.join(home(), "config", "topics.yaml")
    example = os.path.join(PLUGIN, "examples", "config", "topics.yaml")
    state = "is missing" if not os.path.exists(path) else "lists no topics"
    sys.exit(f"{path} {state}, so every save would be tagged with nothing.\n"
             f"Write your topics there first. A commented example to copy: {example}\n"
             f"(The import-saves skill's \"Set up your folder\" step copies all three starter files.)")
