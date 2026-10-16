#!/usr/bin/env python3
"""setup_home.py — make a folder for your saves, with the three starter config files.

    setup_home.py --home <dir>          make <dir>/config/ with topics, collections and places
    setup_home.py                       the same in $INSTAGRAM_HOME (or ~/Workspace/git/instagram)

Copies examples/config/{topics,collections,places}.yaml from the plugin into <dir>/config/.
A file that is already there is never overwritten; it is listed as kept. Then prints the
`export INSTAGRAM_HOME=...` line to run, and what to do next.

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

FILES = ("topics.yaml", "collections.yaml", "places.yaml")


def setup(target):
    """Copy the starter files into target/config; return (copied, kept) lists of file names."""
    src = os.path.join(PLUGIN, "examples", "config")
    dst = os.path.join(target, "config")
    os.makedirs(dst, exist_ok=True)
    copied, kept = [], []
    for name in FILES:
        out = os.path.join(dst, name)
        if os.path.exists(out):
            kept.append(name)
            continue
        shutil.copyfile(os.path.join(src, name), out)
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
        print(f"  copied  config/{name}")
    for name in kept:
        print(f"  kept    config/{name} (already there, not changed)")
    print("\nNext:")
    print(f"  1. export INSTAGRAM_HOME={target}")
    print(f"  2. {IMPORT_CMD}")
    print("  3. python3 " + os.path.join(PLUGIN, "skills", "import-saves", "scripts", "import_saved.py") + " --list")
    print("     then edit config/collections.yaml to name your collections, and config/topics.yaml")
    print("     and config/places.yaml to fit what you save. The examples' names are invented.")
    print("  4. The tag-saves skill sorts every save onto your topics.")


if __name__ == "__main__":
    main()
