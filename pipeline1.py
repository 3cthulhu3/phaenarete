"""Phaenarete pipeline v1: map -> ask.

Two model calls per case.
- map: the leaning option, a premortem (five specific ways the lean fails) and the
  load-bearing beliefs behind it, each with what it rests on and how that source could
  be wrong now.
- ask: ten questions that check those sources directly, most decision-changing first.

What changed from v0 (pipeline.py), after the pilot and the v1 difficulty checks:
- No operator quota and no coverage rule. v0 spread its ten slots over seven question
  types and lost to a single prompt at every k.
- The map asks for the source behind each belief, because the cruxes models miss sit
  behind an impression or a figure (a reassurance resting on a broken instrument).
- The model's own order is kept: no re-ranking by self-reported scores.

Used by run_arm.py when --arm phaenarete1.
"""

from __future__ import annotations

import hashlib
import json
from typing import Callable

from common import case_brief, extract_json, fill, load_prompt

STAGES = ["pipeline1/map", "pipeline1/ask"]
K = 10

Call = Callable[[str, int], str]


def prompt_fingerprint() -> str:
    text = "".join(load_prompt(s) for s in STAGES)
    return hashlib.sha256(text.encode()).hexdigest()[:12]


def map_decision(case: dict, call: Call) -> dict:
    m = extract_json(call(fill(load_prompt("pipeline1/map"), case_brief=case_brief(case)), 4000))
    if not isinstance(m.get("beliefs"), list) or not m["beliefs"]:
        raise ValueError("map: no beliefs")
    return m


def ask(case: dict, m: dict, call: Call) -> list[dict]:
    prompt = fill(load_prompt("pipeline1/ask"), case_brief=case_brief(case), map=json.dumps(m, indent=1, ensure_ascii=False))
    items = extract_json(call(prompt, 3000))["questions"]
    out = []
    for it in items:
        if isinstance(it, str):
            it = {"question": it}
        q = str(it.get("question", "")).strip()
        if q:
            out.append({**it, "question": q})
    return out


def run(case: dict, call: Call) -> tuple[list[str], dict]:
    m = map_decision(case, call)
    items = ask(case, m, call)
    trace = {"map": m, "questions": items[:K]}
    return [it["question"] for it in items[:K]], trace


def mock_call(case: dict) -> Call:
    """A fake model that returns well-formed JSON for each stage, for testing the plumbing."""

    def call(prompt: str, max_tokens: int) -> str:
        if "Do not write questions yet" in prompt:
            return json.dumps({"lean": {"option": case["options"][0]["id"], "reasons": "mock"},
                               "premortem": [f"mock story {i}" for i in range(1, 6)],
                               "beliefs": [{"id": f"b{i}", "belief": f"mock belief {i}", "rests_on": "mock",
                                            "how_wrong": "mock", "impact": 5 - i % 5, "checked": 1 + i % 5}
                                           for i in range(1, 8)]})
        if "Write the 10 questions" in prompt:
            return json.dumps({"questions": [{"question": f"[mock] check source of b{i % 7 + 1}?", "targets": f"b{i % 7 + 1}",
                                              "impact": 3, "checked": 2} for i in range(12)]})
        raise ValueError("mock: unknown stage")

    return call
