"""home.py — where the private data repo is, so scripts never write beside themselves.

Installed plugins run from the plugin cache, which is wiped on every update. Every script
therefore reads and writes in the data repo: $INSTAGRAM_HOME, or ~/Workspace/git/instagram.

    from home import home, cache
    home()                 # the data repo
    cache("saves.json")    # <data repo>/.cache/saves.json (gitignored there)
"""

import os

DEFAULT = os.path.join("~", "Workspace", "git", "instagram")


def home():
    return os.path.abspath(os.path.expanduser(os.environ.get("INSTAGRAM_HOME") or DEFAULT))


def cache(*parts):
    return os.path.join(home(), ".cache", *parts)
