"""pilot.py — which saves are in a pilot, the one rule every step shares.

A pilot (config/collections.yaml, `pilots:`) holds the saves in its collections and the saves
tagged with one of its places. The tagger also passes `hints`, the places its rules guessed from a
caption before any agent read it, so that a save that might be in the pilot gets read. Every later
step (spot pins, thumbnails, the hub) goes by the tags alone, so they all work on the same saves.
"""


def in_pilot(save, tag, pilot, hints=()):
    if pilot is None:
        return True
    if set(save.get("collections") or []) & set(pilot.get("collections") or []):
        return True
    return bool(set(pilot.get("cities") or []) & (set(hints) | set((tag or {}).get("cities") or [])))
