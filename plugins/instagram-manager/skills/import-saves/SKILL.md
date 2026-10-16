---
name: import-saves
description: Import Instagram saved posts and collections from a data export zip into the private data repo's .cache/saves.json, reading only the saved/ files in memory. Use when someone has downloaded a new Instagram export, wants their saves or collections listed, or wants the post links in one collection.
---

# Import Saves

Reads `your_instagram_activity/saved/saved_posts.*` and `saved_collections.*` straight out of
the export zip, in memory. Nothing else in the zip is opened, so messages and the rest of the
account never touch disk. Works with the HTML export (current) and the older JSON shapes.

## Steps

1. **Get the export from Instagram.** If the user has no zip yet, walk them through it:
   - In the Instagram app or on instagram.com: **Settings → Accounts Center → Your information
     and permissions → Download your information → Download or transfer information**.
   - Pick the account, then **Some of your information**, and tick only **Saved** (under "Your
     Instagram activity"). A smaller export is faster and holds nothing else of theirs.
   - **Download to device**, date range **All time**, format **HTML** (JSON also imports, but older JSON exports carry
     no captions), then **Create files**.
   - Instagram emails when it is ready (minutes to a couple of days). Download it from the same
     page; the link lasts a few days. The file is named like `instagram-<account>-<date>.zip`.

   What this plugin does with it, to tell them plainly: it opens only the `saved/` files inside
   the zip, in memory, and never unpacks the rest. It never logs in to Instagram. Everything it
   writes stays in their own folder on this computer.
2. **Set up your folder** (first time only). One folder holds their saves and everything made
   from them; it starts with three commented config files, copied from the plugin's examples:
   ```bash
   python3 <plugin>/skills/import-saves/scripts/setup_home.py --home ~/my-saves
   export INSTAGRAM_HOME=~/my-saves
   ```
   It never overwrites a file that is already there. Track the run with `TaskCreate` (set up,
   import, check counts, list collections).
3. **Import.** Use the zip path they give (usually `~/Downloads/instagram-*.zip`).
   ```bash
   python3 <plugin>/skills/import-saves/scripts/import_saved.py --from-zip ~/Downloads/instagram-example.zip
   ```
   It writes `$INSTAGRAM_HOME/.cache/saves.json` and `$INSTAGRAM_HOME/.cache/never-public.txt`, and
   ends with one line like:
   ```
   ev=import saves=1200 only_in_collection=2 collections=14 collection_links=310 saves_in_a_collection=300 reels=900 posts=290 tv=10 no_caption=25
   ```
4. **Check the counts** against what Instagram shows (Saved → All posts, and the collection
   count). `only_in_collection` counts posts that sit in a collection but not in the saved list;
   they are kept, with no save time.
5. **List collections** so the user can pick what to work on next:
   ```bash
   python3 <plugin>/skills/import-saves/scripts/import_saved.py --list
   ```
   If they want to start with a few collections, use `AskUserQuestion` with the collection names
   as options.
6. **Name the collections in the config.** Replace the invented collections in
   `config/collections.yaml` with theirs (topics and places each one gives for free), and trim
   `config/topics.yaml` and `config/places.yaml` to what they save. Then the tag-saves skill.

## What `saves.json` holds

```
{"exported", "account", "format": "html"|"json",
 "saves": [{code, url, kind: reel|post|tv, caption, hashtags[], owner{username,name,url},
            saved_at, saved_at_text, collections[], only_in_collection?}],
 "collections": [{name, type, privacy, updated, codes[]}]}
```

- `caption` is word for word, with HTML entities decoded (`&#064;` → `@`).
- `saved_at` is the export's own clock time, with no timezone (Instagram doesn't say which).
- Two collections can share a name; both are kept. A save in two collections lists both.

## Example

An invented export with a save from `@example_bakery` in collections "Weekend Trips" and
"Bread": `--collection "weekend trips"` prints its link; `--list` shows both collections with
their counts.

## Scripts — when to use each

| Script | What it does | When to reach for it | Command |
|---|---|---|---|
| `scripts/import_saved.py` | Export zip or folder → `saves.json` + never-public list | A new export arrived | `python3 scripts/import_saved.py --from-zip <zip>` |
| `scripts/import_saved.py --list` | Collection names and counts | Choosing what to work on | `python3 scripts/import_saved.py --list` |
| `scripts/import_saved.py --collection NAME` | Post links in one collection (same-name collections merged) | Feeding one collection to the next step | `python3 scripts/import_saved.py --collection "<name>"` |
| `scripts/setup_home.py` | Makes the saves folder with the three starter config files; never overwrites | First time, before the first import | `python3 scripts/setup_home.py --home <dir>` |
| `scripts/test_import_saved.py` | Offline tests on an invented export | After any change to the importer | `python3 scripts/test_import_saved.py` |
