#!/usr/bin/env python3
"""Turn the hub's background comment responder on or off (macOS launchd).

    responder.py on     [--root <hub>]   write the LaunchAgent and load it
    responder.py off    [--root <hub>]   unload it and remove the LaunchAgent
    responder.py status [--root <hub>]   loaded or not, comments waiting, last log lines

The agent runs <hub>/.claude/hooks/respond-comments.sh whenever a thread file is added or
removed (WatchPaths) and every 5 minutes, because appending to a thread doesn't change the
folder. The script exits at once when nothing waits on Claude or a session in the hub is open.
"""
import argparse
import os
import plistlib
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "recreate-technique" / "scripts"))
import lib  # noqa: E402

LABEL = "com.technique-hub.responder"
PLIST = Path.home() / "Library" / "LaunchAgents" / f"{LABEL}.plist"
LOG = Path.home() / "Library" / "Logs" / "technique-hub-responder.log"
DOMAIN = f"gui/{os.getuid()}"


def launchctl(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(["launchctl", *args], capture_output=True, text=True)


def on(root: Path) -> str:
    script = root / ".claude" / "hooks" / "respond-comments.sh"
    if not script.exists():
        raise SystemExit(f"{script} is missing; copy it from {Path(__file__).parent.parent / 'templates'}")
    PLIST.parent.mkdir(parents=True, exist_ok=True)
    LOG.parent.mkdir(parents=True, exist_ok=True)
    PLIST.write_bytes(plistlib.dumps({
        "Label": LABEL,
        "ProgramArguments": ["/bin/bash", str(script)],
        "WorkingDirectory": str(root),
        "WatchPaths": [str(root / ".page-comments" / "threads")],
        "StartInterval": 300,
        "RunAtLoad": True,
        "StandardOutPath": str(LOG),
        "StandardErrorPath": str(LOG),
    }))
    launchctl("bootout", f"{DOMAIN}/{LABEL}")  # reload if it was on
    r = launchctl("bootstrap", DOMAIN, str(PLIST))
    if r.returncode != 0:
        raise SystemExit(f"launchctl bootstrap failed: {r.stderr.strip()}")
    return f"responder on: {PLIST}\nlog: {LOG}"


def off() -> str:
    launchctl("bootout", f"{DOMAIN}/{LABEL}")
    PLIST.unlink(missing_ok=True)
    return "responder off"


def status(root: Path) -> str:
    loaded = launchctl("print", f"{DOMAIN}/{LABEL}").returncode == 0
    r = subprocess.run([str(root / ".page-comments" / "run"), "list", "--open", "--waiting", "claude"],
                       cwd=root, capture_output=True, text=True)
    tail = LOG.read_text(encoding="utf-8").splitlines()[-5:] if LOG.exists() else []
    return "\n".join([f"responder {'on' if loaded else 'off'}" + (f" ({PLIST})" if PLIST.exists() else ""),
                      "waiting on Claude:", "  " + (r.stdout.strip() or r.stderr.strip()).replace("\n", "\n  "),
                      "last log lines:", *("  " + line for line in tail)])


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("action", choices=("on", "off", "status"))
    ap.add_argument("--root", help="the hub (default: the configured one)")
    args = ap.parse_args()
    if sys.platform != "darwin":
        raise SystemExit("The responder uses launchd, so it runs on macOS only. Run this in a Mac terminal.")
    root = lib.find_root(args.root)
    if not lib.is_hub(root):
        raise SystemExit(f"{root} is not a hub (no hub.json)")
    print(on(root) if args.action == "on" else off() if args.action == "off" else status(root))
    return 0


if __name__ == "__main__":
    sys.exit(main())
