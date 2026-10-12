#!/usr/bin/env python3
"""check_data.py — the data repo's files load and fit together. Run by its `make check`.

    python3 shared/scripts/check_data.py          # checks $INSTAGRAM_HOME (default ~/Workspace/git/instagram)

Checks, each one only when its file exists:
  config/topics.yaml       a `topics:` map, each with a label
  config/collections.yaml  every topic is a known topic; every pilot names known collections;
                           with .cache/saves.json present, every collection name is in the export
                           (a typo would silently tag nothing)
  data/tags.yaml           code → {topics[], cities[]}, topics known, codes in the export

Prints one ev= line per problem and exits 1 if there is any.
"""

import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import yaml  # noqa: E402

from home import cache, home  # noqa: E402
from log import log  # noqa: E402


def load(rel):
    path = os.path.join(home(), rel)
    if not os.path.exists(path):
        return None
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def check():
    problems = []

    def bad(ev, **kv):
        problems.append(ev)
        log(ev, **kv)

    topics = load("config/topics.yaml")
    known = set()
    if topics is not None:
        if not isinstance(topics.get("topics"), dict):
            bad("check_fail", file="config/topics.yaml", msg="needs a topics: map")
        else:
            known = set(topics["topics"])
            for t, v in topics["topics"].items():
                if not isinstance(v, dict) or not v.get("label"):
                    bad("check_fail", file="config/topics.yaml", topic=t, msg="needs a label")

    exported = None
    codes = None
    if os.path.exists(cache("saves.json")):
        with open(cache("saves.json"), encoding="utf-8") as fh:
            saved = json.load(fh)
        exported = {c["name"] for c in saved["collections"]}
        codes = {s["code"] for s in saved["saves"]}

    cols = load("config/collections.yaml")
    if cols is not None:
        mapping = cols.get("collections") or {}
        for name, rule in mapping.items():
            if not isinstance(rule, dict):
                bad("check_fail", file="config/collections.yaml", collection=name, msg="needs {topics, cities}")
                continue
            for t in rule.get("topics") or []:
                if known and t not in known:
                    bad("check_fail", file="config/collections.yaml", collection=name, topic=t, msg="unknown topic")
            if exported is not None and name not in exported:
                bad("check_fail", file="config/collections.yaml", collection=name, msg="not a collection in the export")
        for pilot, p in (cols.get("pilots") or {}).items():
            for name in p.get("collections") or []:
                if name not in mapping:
                    bad("check_fail", file="config/collections.yaml", pilot=pilot, collection=name,
                        msg="pilot names a collection with no entry above")

    tags = load("data/tags.yaml")
    if tags is not None:
        for code, t in tags.items():
            if not isinstance(t, dict):
                bad("check_fail", file="data/tags.yaml", code=code, msg="needs {topics, cities}")
                continue
            for topic in t.get("topics") or []:
                if known and topic not in known:
                    bad("check_fail", file="data/tags.yaml", code=code, topic=topic, msg="unknown topic")
            if codes is not None and code not in codes:
                bad("check_fail", file="data/tags.yaml", code=code, msg="not a save in the export")

    log("check", home=home(), problems=len(problems))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(check())
