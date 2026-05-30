"""
test_invariant_fuzzer.py — Property-based fuzzer for #86 invariants.

Generates N random (diff, narrative) pairs with varied complexity and asserts
every invariant holds for each one. Cheap insurance against pathological
classifier inputs that crafted tests don't cover (e.g. unicode normalisation
quirks, pathological prefix collisions, mixed inferred/real headers across
many rows).

Hand-rolled (no Hypothesis dependency). Seed is fixed so failures reproduce.

Run from the bin/ directory:
    cd plugins/noteplan-manager/bin
    python3 -m pytest noteplan_sweep/tests/test_invariant_fuzzer.py -v
"""

import random
import sys
from pathlib import Path

import pytest

_BIN = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_BIN))

from noteplan_sweep.sweep_review import (
    _py_classify_all_rows,
    _py_cross_row_issues,
    _py_invariant_violations,
)

from noteplan_sweep.tests.test_invariants import _make_diff


# ---------------------------------------------------------------------------
# Random generators (deterministic via seed)
# ---------------------------------------------------------------------------

_TASK_TEMPLATES = [
    "- [ ] write the {topic} {artifact}",
    "- [ ] review {topic} with {person}",
    "- [ ] follow up on {topic} {artifact}",
    "- [ ] schedule {topic} sync",
    "- [ ] research {topic} options for {project}",
    "- {topic}: https://example.com/{slug}",
    "- [ ] draft {artifact} for {project}",
]
_TOPICS    = ["bikar", "config", "auth", "review", "training", "design", "metrics", "intake"]
_ARTIFACTS = ["plan", "doc", "prd", "spec", "outline", "summary", "notes"]
_PEOPLE    = ["jeff", "ana", "ravi", "sam", "priya"]
_PROJECTS  = ["onboarding", "ai-club", "esgenius", "elgato", "lab", "hardening"]
_SECTIONS  = ["Work", "Goals", "Design", "Bikar", "Config", "Tasks", "Random Plans", "References"]
_DESTS     = ["Plans/Bikar", "Plans/Design", "Plans/Goals", "Plans/Hardening", "Plans/Onboarding"]


def _rand_task(rng: random.Random) -> str:
    tpl = rng.choice(_TASK_TEMPLATES)
    return tpl.format(
        topic=rng.choice(_TOPICS),
        artifact=rng.choice(_ARTIFACTS),
        person=rng.choice(_PEOPLE),
        project=rng.choice(_PROJECTS),
        slug=rng.choice(_PROJECTS) + "-" + rng.choice(_TOPICS),
    )


def _rand_diff_and_narrative(rng: random.Random):
    """Build a synthetic (diff, narrative) pair with random row count and dispositions.

    Distributions are biased to produce a mix of move / went-to / lost / mixed /
    empty rows so the invariants get exercised under variety.
    """
    n_rows = rng.randint(1, 6)
    narrative = []
    files: list[dict] = []
    src_path = f"Calendar/2026{rng.randint(1, 12):02d}{rng.randint(1, 28):02d}.md"
    src_removed: list[str] = []

    for i in range(n_rows):
        section = rng.choice(_SECTIONS) + (f" {i}" if rng.random() < 0.3 else "")
        dest_stem = rng.choice(_DESTS)
        # Source content for this row
        n_lines = rng.randint(0, 4)
        lines = [_rand_task(rng) for _ in range(n_lines)]
        # 50% chance: prefix the section header into source so it's NOT inferred
        if rng.random() < 0.5 and lines:
            src_removed.append(f"## {section}")
        src_removed.extend(lines)

        # Decide where these lines actually go
        for line in lines:
            roll = rng.random()
            if roll < 0.55:
                # move: line lands at breadcrumb dest
                files.append({"path": f"{dest_stem}.md", "removed": [], "added": [line]})
            elif roll < 0.75:
                # went-to: lands at a different file
                other = rng.choice([d for d in _DESTS if d != dest_stem]) or dest_stem
                files.append({"path": f"{other}.md", "removed": [], "added": [line]})
            else:
                # lost: doesn't appear anywhere
                pass

        narrative.append({
            "source_file": src_path,
            "section":     section,
            "destination": f"[[{dest_stem}]]",
            "date":        "2026-04-13",
            "summary":     "",
        })

    files.insert(0, {"path": src_path, "removed": src_removed, "added": []})
    return _make_diff(files), narrative


def _classify(diff_text: str, narrative: list) -> list[dict]:
    return _py_classify_all_rows(diff_text, narrative, Path("/nonexistent"))


# ---------------------------------------------------------------------------
# The fuzzer
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("seed", list(range(50)))
def test_fuzzer_random_diff_satisfies_invariants(seed: int):
    """For each seed, generate a random (diff, narrative) and assert every
    invariant holds. _py_invariant_violations should return [] for any
    well-formed input the classifier produces.
    """
    rng = random.Random(seed)
    diff, narrative = _rand_diff_and_narrative(rng)
    results = _classify(diff, narrative)
    issues = _py_cross_row_issues(results)
    violations = _py_invariant_violations(results, issues)
    assert violations == [], (
        f"seed={seed}: classifier produced result that violates invariants.\n"
        f"violations: {violations[:5]}\n"
        f"narrative: {narrative}\n"
        f"diff snippet: {diff[:400]!r}"
    )


def test_fuzzer_does_not_crash_on_empty_input():
    """Edge case: empty diff + empty narrative produce empty results, no violations."""
    results = _classify("", [])
    assert results == []
    violations = _py_invariant_violations(results, [])
    assert violations == []
