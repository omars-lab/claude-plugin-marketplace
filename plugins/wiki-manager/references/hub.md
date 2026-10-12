---
title: Wiki
type: wiki-hub
updated: YYYY-MM-DD
---

# 📚 Wiki

A standing LLM knowledge base compiled from this vault, organized as an **FAQ**: every article answers **one question**, grounded verbatim in a raw note or built on another answer, so you can **crawl down the links to the base facts** and never re-read the raw notes.

The wiki is split into **spaces** — one per domain, each bound to a **confidentiality/PII tolerance**. A space is a compartment: a derived answer may only build on answers in its own space or in the public floor 🌐 General, so following the dependency crawl never leaks one domain's confidential content into another. See [[spaces]] for the rubric and the two invariants.

- **Maintain it:** `/wiki-manager:manage-wiki`
- **How it works:** raw (immutable sources) → wiki (these FAQ graphs) → references (templates + the
  [[spaces]] rubric). See [[log]] for the running history across all spaces.

## Spaces

<!-- One row per space. The index link opens that space's own FAQ graph. -->

| Space | Domain | Tolerance | Articles |
|---|---|---|---|
| [[🌐 General]] | cross-cutting | **public floor** — no PII, shareable; the only space others build on | 0 |
| [[🏢 Work]] | current employer | employer-confidential + colleague PII | 0 |
| [[📦 Past Work]] | former employer | former-employer-confidential + colleague PII | 0 |
| [[🏡 Personal]] | self + family | personal/family PII — health, home, minors | 0 |
| [[☕️ NaqshCoffee]] | coffee business | business-confidential | 0 |
| [[👥 EarlBear]] | venture | venture-confidential | 0 |

> Each space link points at that space's folder-note (`<space>/<space>.md`). No secret enters any
> space (invariant 1); no private space builds on another private space (invariant 2). See [[spaces]].

## Open threads / gaps (across spaces)

<!-- Aggregated `## Gaps` notes worth surfacing at the very top. Name the space. -->

- ...
