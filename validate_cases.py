"""Check cases against the rules in case.schema.json (no external packages).

Usage: python3 validate_cases.py cases/
"""

from __future__ import annotations

import sys

from common import ROOT, load_cases

CATEGORIES = {"career", "product", "business", "technical", "purchase", "operations", "housing", "education", "other"}
SOURCES = {"synthetic", "human-real", "human-adapted", "model-adapted"}

# Words that mark the stock risk checklist the pilot showed a plain prompt always covers.
CHECKLIST_WORDS = {"runway", "funding round", "contract", "clause", "leaving", "warranty", "budget"}


def check(case: dict) -> list[str]:
    errs = []
    for field in ["id", "category", "source", "decision", "options", "goal", "visible_context",
                  "lean_without_hidden", "hidden_facts"]:
        if not case.get(field):
            errs.append(f"missing {field}")
    if errs:
        return errs
    if case["category"] not in CATEGORIES:
        errs.append(f"unknown category {case['category']}")
    if case["source"] not in SOURCES:
        errs.append(f"unknown source {case['source']}")
    opt_ids = {o["id"] for o in case["options"]}
    if not 2 <= len(opt_ids) <= 4:
        errs.append("need 2-4 options")
    if case["lean_without_hidden"] not in opt_ids:
        errs.append("lean_without_hidden is not an option id")
    facts = case["hidden_facts"]
    ids = [f["id"] for f in facts]
    if len(ids) != len(set(ids)):
        errs.append("duplicate fact ids")
    cruxes = [f for f in facts if f["type"] == "crux"]
    twins = [f for f in facts if f["type"] == "twin"]
    if not cruxes:
        errs.append("no crux facts")
    if not twins:
        errs.append("no twin facts (needed to measure discrimination)")
    for f in cruxes:
        if not f["id"].startswith("c"):
            errs.append(f"{f['id']}: crux ids start with c")
        if f.get("favors") not in opt_ids:
            errs.append(f"{f['id']}: favors must be an option id")
        elif f["favors"] == case["lean_without_hidden"]:
            errs.append(f"{f['id']}: a crux should favor a different option than the visible lean")
    for f in twins:
        if not f["id"].startswith("t"):
            errs.append(f"{f['id']}: twin ids start with t")
        if f.get("twin_of") not in {c["id"] for c in cruxes}:
            errs.append(f"{f['id']}: twin_of must name a crux")
    for f in facts:
        if not f.get("text", "").strip():
            errs.append(f"{f['id']}: empty text")
        if f["text"].strip().lower() in case["visible_context"].lower():
            errs.append(f"{f['id']}: hidden fact appears in visible context")
    if case.get("benchmark") == "v1":
        errs += check_v1(case, cruxes, twins)
    return errs


def check_v1(case: dict, cruxes: list[dict], twins: list[dict]) -> list[str]:
    """Rules from CASES.md that a script can check. Errors start with 'v1:'; hints with 'hint:'."""
    errs = []
    for f in cruxes:
        if not f.get("how_to_learn", "").strip():
            errs.append(f"v1: {f['id']}: crux needs how_to_learn (a crux must be learnable before deciding)")
        if any(w in f["text"].lower() for w in CHECKLIST_WORDS):
            errs.append(f"hint: {f['id']}: crux uses a stock checklist word; the pilot found these too easy")
    for f in twins:
        if not f.get("why", "").strip():
            errs.append(f"v1: {f['id']}: twin needs why (why it does not change the decision)")
    if len(twins) < len(cruxes):
        errs.append("v1: at least one twin per crux")
    if case["source"] == "model-adapted" and "private" not in case.get("_path", ""):
        errs.append("v1: model-adapted cases belong in cases/private/ (never published)")
    return errs


def main() -> None:
    path = sys.argv[1] if len(sys.argv) > 1 else "cases/"
    cases = load_cases(ROOT / path)
    bad = 0
    for case in cases:
        errs = check(case)
        if any(not e.startswith("hint:") for e in errs):
            bad += 1
        if errs:
            print(f"{case.get('id', '?')}:")
            for e in errs:
                print(f"  - {e}")
    by_source: dict[str, int] = {}
    for c in cases:
        by_source[c["source"]] = by_source.get(c["source"], 0) + 1
    print(f"\n{len(cases)} cases, {bad} with problems. By source: {by_source}")
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
