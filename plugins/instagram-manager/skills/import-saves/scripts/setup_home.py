#!/usr/bin/env python3
"""setup_home.py — make a folder for your saves, with the three starter config files and a Makefile.

    setup_home.py --home <dir>          make <dir>/config/ with topics, collections and places
    setup_home.py                       the same in $INSTAGRAM_HOME (or ~/Workspace/git/instagram)

Copies examples/config/{topics,collections,places}.yaml from the plugin into <dir>/config/, and
examples/Makefile into <dir>/ with this plugin's path filled in, so every `make` line in the skills
runs from that folder (`make help` lists them). A file that is already there is never overwritten;
it is listed as kept. Then prints the `export INSTAGRAM_HOME=...` line to run, and what to do next.

Everything the plugin writes lands in that folder: .cache/ (saves.json, batches, the hub),
data/ (tags, items, pins) and out/ (topic files). Keep it private; it holds your saves.
"""

import argparse
import os
import shutil
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(HERE, os.pardir, os.pardir, os.pardir, "shared", "scripts"))
from home import IMPORT_CMD, PLUGIN, home  # noqa: E402

FILES = ("config/topics.yaml", "config/collections.yaml", "config/places.yaml", "Makefile")


def setup(target):
    """Copy the starter files into target; return (copied, kept) lists of their paths in it."""
    os.makedirs(os.path.join(target, "config"), exist_ok=True)
    copied, kept = [], []
    for name in FILES:
        out = os.path.join(target, name)
        if os.path.exists(out):
            kept.append(name)
            continue
        src = os.path.join(PLUGIN, "examples", name)
        if name == "Makefile":
            with open(src, encoding="utf-8") as fh:
                text = fh.read().replace("@PLUGIN@", os.path.abspath(PLUGIN))
            with open(out, "w", encoding="utf-8") as fh:
                fh.write(text)
        else:
            shutil.copyfile(src, out)
        copied.append(name)
    return copied, kept


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--home", help="the folder for your saves (default: $INSTAGRAM_HOME)")
    args = ap.parse_args()
    target = os.path.abspath(os.path.expanduser(args.home)) if args.home else home()
    copied, kept = setup(target)
    print(f"Your folder: {target}")
    for name in copied:
        print(f"  copied  {name}")
    for name in kept:
        print(f"  kept    {name} (already there, not changed)")
    print("\nNext (the make lines run from that folder; each prints the command it runs):")
    print(f"  1. cd {target}   (make sets INSTAGRAM_HOME itself; for a python3 line, export INSTAGRAM_HOME={target})")
    print(f"  2. make import EXPORT=path/to/instagram-....zip   (or: {IMPORT_CMD})")
    print("  3. make collections, then edit config/collections.yaml to name your collections, and")
    print("     config/topics.yaml and config/places.yaml to fit what you save. The examples' names are invented.")
    print("  4. The tag-saves skill sorts every save onto your topics. make help lists every step.")


if __name__ == "__main__":
    main()
