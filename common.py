"""Shared helpers for the Crux benchmark (Phaenarete). Standard library only."""

from __future__ import annotations

import json
import os
import random
import re
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PROMPTS = ROOT / "prompts"
API_URL = "https://api.anthropic.com/v1/messages"
API_VERSION = "2023-06-01"

DEFAULT_GENERATOR = "claude-sonnet-5-5"
DEFAULT_JUDGE = "claude-opus-5-5"


# ---------- cases ----------

def load_cases(path: str | Path) -> list[dict]:
    """Load cases from a JSON file (list or single object) or a directory of JSON files.

    Directories are read recursively, so cases/ includes the git-ignored cases/private/.
    """
    p = Path(path)
    files = sorted(p.rglob("*.json")) if p.is_dir() else [p]
    cases: list[dict] = []
    for f in files:
        if f.name.upper().startswith("TEMPLATE"):
            continue
        data = json.loads(f.read_text(encoding="utf-8"))
        cases.extend(data if isinstance(data, list) else [data])
    ids = [c["id"] for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate case ids: {sorted(dupes)}")
    return cases


def case_brief(case: dict) -> str:
    """The part of a case the question generator may see. Never includes hidden facts."""
    lines = [f"Decision: {case['decision']}", "Options:"]
    for o in case["options"]:
        desc = f" - {o['description']}" if o.get("description") else ""
        lines.append(f"- {o['label']}{desc}")
    lines.append(f"Goal: {case['goal']}")
    if case.get("constraints"):
        lines.append(f"Constraints: {case['constraints']}")
    lines.append(f"Context: {case['visible_context']}")
    return "\n".join(lines)


def neutral_facts(case: dict, seed: int = 0) -> tuple[str, dict[str, str]]:
    """Shuffle hidden facts and relabel them f1..fn so the judge cannot see crux/twin labels.

    Returns the text block for the prompt and a map neutral_id -> original_id.
    """
    facts = list(case["hidden_facts"])
    rng = random.Random(f"{case['id']}:{seed}")
    rng.shuffle(facts)
    mapping, lines = {}, []
    for i, fact in enumerate(facts, 1):
        nid = f"f{i}"
        mapping[nid] = fact["id"]
        lines.append(f"{nid}: {fact['text']}")
    return "\n".join(lines), mapping


def fill(template: str, **values: str) -> str:
    """Replace {name} placeholders without touching other braces (prompts contain JSON)."""
    for key, val in values.items():
        template = template.replace("{" + key + "}", val)
    return template


def load_prompt(name: str) -> str:
    return (PROMPTS / f"{name}.txt").read_text(encoding="utf-8")


# ---------- API ----------

def call_claude(prompt: str, model: str, max_tokens: int = 2000, system: str | None = None,
                retries: int = 4) -> str:
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not set (use --dry-run to test without the API)")
    body = {"model": model, "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}]}
    if system:
        body["system"] = system
    data = json.dumps(body).encode("utf-8")
    headers = {"x-api-key": key, "anthropic-version": API_VERSION, "content-type": "application/json"}
    delay = 2.0
    for attempt in range(retries + 1):
        req = urllib.request.Request(API_URL, data=data, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=180) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
            return "".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
        except urllib.error.HTTPError as e:
            detail = e.read().decode("utf-8", "replace")[:500]
            if e.code in (429, 500, 502, 503, 529) and attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise RuntimeError(f"API error {e.code}: {detail}") from None
        except urllib.error.URLError:
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
                continue
            raise
    raise RuntimeError("unreachable")


def extract_json(text: str) -> dict:
    """Parse the first JSON object in a model reply (tolerates code fences and prose)."""
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text
    start = candidate.find("{")
    if start == -1:
        raise ValueError("no JSON object in reply")
    depth, in_str, esc = 0, False, False
    for i, ch in enumerate(candidate[start:], start):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
        elif ch == '"':
            in_str = True
        elif ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(candidate[start:i + 1])
    raise ValueError("unbalanced JSON in reply")


def write_json(path: Path, obj: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def slug(model: str) -> str:
    return re.sub(r"[^a-zA-Z0-9.-]+", "_", model)
