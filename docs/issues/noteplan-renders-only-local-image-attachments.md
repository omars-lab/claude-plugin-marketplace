# NotePlan renders only local image attachments, never a remote `http://` URL

**Status:** resolved — shipped in wiki-manager 0.6.2
**Affects:** `plugins/wiki-manager/bin/wiki_map.py`, `skills/manage-wiki/SKILL.md`, `README.md`

## Symptom

The `🗺️ Concept Map` note had embedded its two PlantUML diagrams as

```markdown
![Wiki hierarchy — space to topic to article](http://<render-host>:8080/plantuml/png/XLZ1Sji…)
```

for several versions. In NotePlan the diagrams simply were not there — no broken-image icon, no
error, just an empty gap between the `## Hierarchy` heading and the next one. The user's report was
"we still don't have previewable diagram images in noteplan".

## Why it was hard to see

The URL is *correct*. Fetching it directly returns the image:

```
$ curl -s -o /dev/null -w "%{http_code} %{content_type} %{size_download}\n" "http://<render-host>…/png/XLZ…"
200 image/png 377598
```

So every check available from the shell says the feature works. The render server was up, the
encoding was right, the link was well-formed. Reasoning from the source and from `curl` can only
conclude that the note is fine — which is what happened, repeatedly.

## Cause

macOS App Transport Security blocks cleartext `http://` loads from an app by default. NotePlan
therefore never fetches the image, and it fails **silently** — the markdown renders as if the line
were not there.

The generator's own docstring had encoded the wrong mental model, in as many words:

> The tool never contacts a server itself — it only writes the URL; NotePlan fetches the image
> when it renders the note.

That second clause was the bug. NotePlan does not fetch it.

## What NotePlan actually supports

Its own attachment convention, discoverable by grepping the vault for image embeds that *do* work:

```markdown
![image](Project%20SDS%20Driver%20Feedback%20Tracker%20P0_attachments/Screenshot%20….jpg)
```

- a sibling folder named `<note stem>_attachments/`
- a relative path, percent-encoded
- alt text is the literal word `image`

## What we did

`wiki_map.py` now **downloads** each PNG from the render server into
`🗺️ Concept Map_attachments/` and links it by relative path. This is the default whenever `--out`
is given; `--remote-images` restores the old link-only behaviour for publishing the note somewhere
that is not NotePlan. The ```plantuml source fences stay under `## Source` either way, so a failed
fetch degrades to text rather than to nothing.

Downloading also removes the dependency on the render host being reachable at *read* time — the map
now renders on a laptop that is off the Tailscale network.

## A second-order bug found the same way

The first working version emitted a descriptive alt text and left the emoji literal:

```markdown
![Wiki hierarchy — space to topic to article](🗺️%20Concept%20Map_attachments/hierarchy.png)
```

That renders. But NotePlan rewrote the note into its own canonical form within seconds of the
generator writing it — percent-encoding the emoji and replacing the alt text with `image`. Left
alone, every regeneration would have produced a spurious git diff and a stale-map nudge for a map
that had not changed. The generator now emits the canonical form directly, verified by re-hashing
the file after opening it in NotePlan (hash unchanged — the app has nothing to rewrite).

## Takeaway

The standing rule is *look at the actual render before reasoning from source*. This is the case it
exists for: the source was valid, the server was up, `curl` returned 200, and the feature was
completely broken. No amount of reading the generator could have shown it, because the generator
was correct — the assumption about the *consumer* was wrong. One screenshot settled it.

Corollary: when an app both reads and writes a file, check what it writes back. Matching its
canonical output is the difference between a generated artifact and a permanent diff.
