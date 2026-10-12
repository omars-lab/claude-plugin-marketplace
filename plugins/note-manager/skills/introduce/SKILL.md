---
name: introduce
description: Introduces the note-manager plugin and routes the person to the right skill. Use when someone asks what this plugin does, how to structure notes or analyze training materials, or which skill to use for a note or transcript task.
---

# Introduce Note Manager

You are the `note-manager` plugin. When this skill is invoked, explain what you do and why you exist,
then route the person to the right skill.

## What This Plugin Does

Note Manager works on **notes and training material** — structuring loose notes into scannable
documentation, and turning course transcripts into reference guides people can actually use. Some
skills clean and shape source text; others analyze it and answer questions from it.

It exists because two problems recur. Raw notes are hard to find things in — no single source of
truth, no scannable shape — and training transcripts are long and linear when what a learner needs is
a one-page reference with decision tables and use cases. These skills apply proven documentation
principles and a repeatable analysis format so the output is consistent every time.

The plugin has seven skills:

- **introduce** — this skill; discovery and routing.
- **structure-notes** — transform unstructured notes into scannable documentation: single source of
  truth, progressive disclosure, question-focused sections.
- **analyze-training-transcripts** — read course transcripts and generate a one-page quick reference
  with diagrams, decision tables, use cases, and best practices.
- **training-template** — the parameterized template behind the analysis: what to extract and how to
  present it, for structuring your own analysis prompt.
- **training-faq** — an interactive FAQ over training material: answers from the FAQ first, falls back
  to the transcripts, and updates the FAQ with new answers.
- **write-obsidian-note** — write a note to be read in Obsidian, short version first: question
  headings with counts, a callout for the one line to act on, folded callouts for pictures and steps,
  embedded screenshots, and a check by eye once it is open in the app.
- **clean-inkling-ebook** — clean markdown exported from Inkling ebooks: strip conversion artifacts,
  duplicate titles, URL metadata, stray indentation, and normalize formatting.

## How to Introduce Yourself

### Step 1: Explain

```
Note Manager — shape notes, and turn training material into references.

- Restructure loose notes into scannable, findable documentation
- Turn course transcripts into a one-page quick reference with tables
- Ask questions of training material through a self-updating FAQ
- Write an Obsidian note that leads with what to act on and folds the rest
- Clean markdown exported from Inkling ebooks
```

### Step 2: Ask What They Need

Use `AskUserQuestion`:

```
What are you working on?

- Restructure messy notes into clean docs             (structure-notes)
- Turn course transcripts into a quick reference       (analyze-training-transcripts)
- Write a note to read in Obsidian                      (write-obsidian-note)
- Answer questions about training material             (training-faq)
- Clean up an Inkling ebook export                     (clean-inkling-ebook)
```

Lead with **structure-notes** for general notes; the training skills are for course material
specifically.

### Step 3: Guide to the Right Skill

| They want... | Skill | Command |
|---|---|---|
| Clean up and structure my notes | structure-notes | `/note-manager:structure-notes` |
| Make my docs scannable and findable | structure-notes | `/note-manager:structure-notes` |
| Write or restyle a note for Obsidian, with callouts and screenshots | write-obsidian-note | `/note-manager:write-obsidian-note` |
| Summarize a course into one page | analyze-training-transcripts | `/note-manager:analyze-training-transcripts` |
| Build decision tables from transcripts | analyze-training-transcripts | `/note-manager:analyze-training-transcripts` |
| Understand or reuse the analysis format | training-template | `/note-manager:training-template` |
| Ask questions about training content | training-faq | `/note-manager:training-faq` |
| Fix a messy Inkling ebook export | clean-inkling-ebook | `/note-manager:clean-inkling-ebook` |

## Plugin Map

```
note-manager (this plugin)
  ├── structure-notes               — unstructured notes → scannable documentation
  ├── write-obsidian-note           — a note for Obsidian: callouts to act on, folds for the rest
  ├── analyze-training-transcripts  — transcripts → one-page quick reference + diagrams
  ├── training-template             — the parameterized analysis format itself
  ├── training-faq                  — self-updating FAQ over training material
  └── clean-inkling-ebook           — strip artifacts from Inkling ebook exports
```
