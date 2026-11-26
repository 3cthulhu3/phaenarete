"""Phaenarete pipeline v0: parse -> generate -> critic (filter + score) -> select.

Three model calls per case (critic may be split into chunks), then a deterministic
selection step in plain Python. The critic never sees what the generator was thinking,
only the decision and the candidate questions.

Used by run_arm.py when --arm phaenarete.
"""

from __future__ import annotations

import hashlib
import json
import random
import re
from typing import Callable

from common import Pending, case_brief, extract_json, fill, load_prompt

STAGES = ["pipeline/parse", "pipeline/generate", "pipeline/critic"]
OPERATORS = ["discriminate", "surface", "test", "bound", "expand", "close", "calibrate"]
FLAGS = ["generic", "presupposes", "answered", "no_path"]
SCALES = ["relevance", "uncertainty", "impact", "answerability", "cost"]

K = 10                 # questions returned (same as the baselines)
CRITIC_CHUNK = 20      # candidates per critic call
MMR_LAMBDA = 0.7       # weight of score vs. novelty when filling the portfolio
MAX_COVERAGE = K - 3   # slots reserved for one-per-uncertainty coverage
MIN_IMPACT_FOR_COVERAGE = 4
DUP_THRESHOLD = 0.75   # similarity at or above this to a chosen question = duplicate, never picked

STOP = set("""a an the and or but if then than that this these those to of in on at for with from by as is are was
were be been being do does did have has had will would should could can may might must you your yours i me my we our
it its they them their what which who whom whose when where why how any some all each every there here about into
over under more most less much many not no yes so just also only very""".split())

Call = Callable[[str, int], str]


def prompt_fingerprint() -> str:
    text = "".join(load_prompt(s) for s in STAGES)
    return hashlib.sha256(text.encode()).hexdigest()[:12]


# ---------- stages ----------

def parse(case: dict, call: Call) -> dict:
    graph = extract_json(call(fill(load_prompt("pipeline/parse"), case_brief=case_brief(case)), 2500))
    graph.setdefault("uncertainties", [])
    graph.setdefault("assumptions", [])
    return graph


def generate(case: dict, graph: dict, call: Call) -> list[dict]:
    prompt = fill(load_prompt("pipeline/generate"), case_brief=case_brief(case),
                  graph=json.dumps(graph, indent=2, ensure_ascii=False))
    cands = extract_json(call(prompt, 8000))["candidates"]
    out = []
    for c in cands:
        q = str(c.get("question", "")).strip()
        if q:
            out.append({"operator": str(c.get("operator", "")).lower(), "target": str(c.get("target", "new")),
                        "question": q, "why": c.get("why", ""), "answer_path": c.get("answer_path", "")})
    return out


def critique(case: dict, candidates: list[dict], call: Call) -> list[dict]:
    template = load_prompt("pipeline/critic")
    reviews: list[dict] = []
    pending: Pending | None = None
    for start in range(0, len(candidates), CRITIC_CHUNK):
        chunk = candidates[start:start + CRITIC_CHUNK]
        block = "\n".join(f"{i}. {c['question']}" for i, c in enumerate(chunk, 1))
        try:
            reply = extract_json(call(fill(template, case_brief=case_brief(case), candidates=block), 4000))
        except Pending as e:  # cache backend: record every chunk before stopping
            pending = e
            continue
        by_id = {int(r["id"]): r for r in reply.get("reviews", []) if "id" in r}
        for i in range(1, len(chunk) + 1):
            reviews.append(by_id.get(i, {"missing": True}))
    if pending:
        raise pending
    return reviews


# ---------- scoring and selection (deterministic) ----------

def clamp(v, lo=1, hi=5) -> int:
    try:
        return max(lo, min(hi, int(v)))
    except (TypeError, ValueError):
        return lo


def score(review: dict) -> tuple[float, list[str]]:
    """Return (S, failed_flags). S = relevance * uncertainty * impact * answerability / cost."""
    if review.get("missing"):
        return 0.0, ["missing"]
    failed = [f for f in FLAGS if review.get(f)]
    r, u, i, a, c = (clamp(review.get(s)) for s in SCALES)
    return r * u * i * a / c, failed


def tokens(text: str) -> set[str]:
    return {w for w in re.findall(r"[a-z0-9']+", text.lower()) if len(w) > 2 and w not in STOP}


def similarity(x: dict, y: dict) -> float:
    a, b = tokens(x["question"]), tokens(y["question"])
    jac = len(a & b) / len(a | b) if a | b else 0.0
    same_target = x["target"] == y["target"] and x["target"] not in ("", "new")
    return min(1.0, jac + (0.15 if same_target else 0.0))


def select(cands: list[dict], graph: dict, k: int = K) -> list[dict]:
    """Pick a portfolio of k questions.

    1. Hard filter: drop candidates that fail any check.
    2. Coverage: for each uncertainty, the best passing question that targets it (impact >= 4).
    3. Make sure at least one 'close' question is in.
    4. Fill the rest by maximal marginal relevance (score vs. similarity to what is chosen).
    5. If fewer than k pass, top up with the best non-generic, not-already-answered rejects.
    At every step a near-duplicate of a chosen question is skipped.
    Output is ordered by score, best first.
    """
    passing = [c for c in cands if not c["failed"]]
    top = max((c["S"] for c in passing), default=1.0) or 1.0
    chosen: list[dict] = []

    def open_(c: dict) -> bool:
        return c not in chosen and all(similarity(c, s) < DUP_THRESHOLD for s in chosen)

    def take(c: dict, why: str) -> None:
        if len(chosen) < k:
            c["picked_by"] = why
            chosen.append(c)

    for u in graph.get("uncertainties", []):
        if sum(c["picked_by"] == "coverage" for c in chosen) >= MAX_COVERAGE:
            break
        pool = [c for c in passing if c["target"] == u.get("id")
                and clamp(c["review"].get("impact")) >= MIN_IMPACT_FOR_COVERAGE and open_(c)]
        if pool:
            take(max(pool, key=lambda c: c["S"]), "coverage")

    if not any(c["operator"] == "close" for c in chosen):
        closes = [c for c in passing if c["operator"] == "close" and open_(c)]
        if closes:
            take(max(closes, key=lambda c: c["S"]), "close")

    def mmr(c: dict) -> float:
        redundancy = max((similarity(c, s) for s in chosen), default=0.0)
        return MMR_LAMBDA * c["S"] / top - (1 - MMR_LAMBDA) * redundancy

    while len(chosen) < k:
        pool = [c for c in passing if open_(c)]
        if not pool:
            break
        take(max(pool, key=mmr), "mmr")

    if len(chosen) < k:
        rejects = [c for c in cands if not {"generic", "answered", "missing"} & set(c["failed"])]
        for c in sorted(rejects, key=lambda c: c["S"], reverse=True):
            if len(chosen) >= k:
                break
            if open_(c):
                take(c, "top_up")

    return sorted(chosen, key=lambda c: c["S"], reverse=True)


# ---------- orchestration ----------

def run(case: dict, call: Call) -> tuple[list[str], dict]:
    graph = parse(case, call)
    cands = generate(case, graph, call)
    reviews = critique(case, cands, call)
    for c, r in zip(cands, reviews):
        c["review"] = r
        c["S"], c["failed"] = score(r)
        c["picked_by"] = None
    chosen = select(cands, graph)
    trace = {
        "graph": graph,
        "n_candidates": len(cands),
        "n_passing": sum(not c["failed"] for c in cands),
        "fail_counts": {f: sum(f in c["failed"] for c in cands) for f in FLAGS + ["missing"]},
        "operator_counts_chosen": {op: sum(c["operator"] == op for c in chosen) for op in OPERATORS},
        "chosen": [{k: c[k] for k in ("question", "operator", "target", "S", "picked_by", "why", "answer_path")}
                   for c in chosen],
        "candidates": cands,
    }
    return [c["question"] for c in chosen], trace


# ---------- dry-run mock ----------

def mock_call(case: dict) -> Call:
    """A fake model that returns well-formed JSON for each stage, for testing the plumbing."""
    rng = random.Random(case["id"])

    def call(prompt: str, max_tokens: int) -> str:
        if "Build a map of the decision" in prompt:
            return json.dumps({"criteria": ["goal met"], "stated_facts": [],
                               "assumptions": [{"id": "a1", "text": "mock assumption"}],
                               "uncertainties": [{"id": f"u{i}", "text": f"mock unknown {i}", "if_resolved": "..."}
                                                 for i in range(1, 5)]})
        if "Write questions with each of these operators" in prompt:
            cands = []
            for op in OPERATORS:
                for j in range(4):
                    tgt = rng.choice(["u1", "u2", "u3", "u4", "a1", "new"])
                    cands.append({"operator": op, "target": tgt,
                                  "question": f"[mock] {op} question {j} about {tgt} {rng.choice(['cost', 'timing', 'people', 'contract', 'risk'])}?",
                                  "why": "mock", "answer_path": "mock"})
            return json.dumps({"candidates": cands})
        if "You review candidate questions" in prompt:
            n = len(re.findall(r"^\d+\. ", prompt, re.M))
            return json.dumps({"reviews": [{
                "id": i, "generic": rng.random() < 0.15, "presupposes": rng.random() < 0.08,
                "answered": rng.random() < 0.05, "no_path": rng.random() < 0.05,
                **{s: rng.randint(1, 5) for s in SCALES}} for i in range(1, n + 1)]})
        raise ValueError("mock_call: unknown stage")

    return call
