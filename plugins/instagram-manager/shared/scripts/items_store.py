"""items_store.py — where split-saves keeps the things each non-travel save names.

The items live in one file per topic, data/items/<topic>.yaml, so no one file grows past the data
repo's 1 MB limit. A save goes in the file of the first of its own topics (sorted), the whole
entry in one place, so a save tagged business and recipes-coffee sits in business.yaml with both
topics' items. A save with no topics goes in other.yaml.

    from items_store import load_items, write_items, file_for, duplicates
    load_items()                 # code → {topics, items}: every file read together
    write_items(items)           # write the files again; empty ones and the old one-file layout go
    duplicates()                 # {code: [files]}: a save in more than one file (a hand edit)

The old single file, data/items.yaml, is still read when it is there, so a repo written before the
split keeps working; the next write moves its entries into the folder and removes it. An entry in
the folder wins over the same code in the old file.
"""

import glob
import os

import yaml

from home import home

DIR = os.path.join("data", "items")
OLD = os.path.join("data", "items.yaml")
NO_TOPIC = "other"


def file_for(entry):
    """data/items/<topic>.yaml for one entry: the first of its topics, sorted."""
    topics = entry.get("topics") if isinstance(entry, dict) else None
    named = sorted(t for t in topics or [] if isinstance(t, str) and t.strip())
    return os.path.join(DIR, f"{named[0] if named else NO_TOPIC}.yaml")


def _read(path):
    with open(path, encoding="utf-8") as fh:
        return yaml.safe_load(fh) or {}


def files(root=None):
    """The topic files there are now, relative to the data repo, sorted."""
    root = root or home()
    return sorted(os.path.relpath(p, root) for p in glob.glob(os.path.join(root, DIR, "*.yaml")))


def exists(root=None):
    root = root or home()
    return os.path.exists(os.path.join(root, OLD)) or bool(files(root))


def load_items(root=None):
    """code → entry from every topic file (and the old single file, if it is still there)."""
    root = root or home()
    out = {}
    if os.path.exists(os.path.join(root, OLD)):
        old = _read(os.path.join(root, OLD))
        out.update(old if isinstance(old, dict) else {})
    for rel in files(root):
        part = _read(os.path.join(root, rel))
        out.update(part if isinstance(part, dict) else {})
    return out


def duplicates(root=None):
    """{code: [files]} for a save that sits in more than one topic file."""
    root = root or home()
    where = {}
    for rel in files(root):
        part = _read(os.path.join(root, rel))
        for code in part if isinstance(part, dict) else {}:
            where.setdefault(code, []).append(rel)
    return {code: rels for code, rels in where.items() if len(rels) > 1}


def write_items(items, write_yaml, root=None):
    """Write each topic's file with `write_yaml(rel, data)` (sorted, stable), remove topic files
    left with no entries and the old single file. Returns the files written."""
    root = root or home()
    groups = {}
    for code, entry in items.items():
        groups.setdefault(file_for(entry), {})[code] = entry
    for rel in sorted(groups):
        write_yaml(rel, groups[rel])
    for rel in set(files(root)) - set(groups):
        os.remove(os.path.join(root, rel))
    if os.path.exists(os.path.join(root, OLD)):
        os.remove(os.path.join(root, OLD))
    return sorted(groups)
