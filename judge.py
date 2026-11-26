"""Judge generated questions against each case's hidden facts.

The judge sees hidden facts under neutral ids (f1, f2, ...) in shuffled order, so it
cannot tell cruxes from twins. Results are mapped back to the original ids.

Usage:
  python3 judge.py --arm b0 --gen-model claude-sonnet-5-5
  python3 judge.py --arm b0 --gen-model mock --dry-run

Output: judgments/<arm>/<gen_model>/<judge_model>/<case_id>__s<k>.json
"""

from __future__ import annotations

import argparse
import json
import random

from common import (DEFAULT_JUDGE, ROOT, RUN_ROOTS, judgment_root, Pending, cached_call, call_claude, case_brief, extract_json, fill, load_cases,
                           load_prompt, neutral_facts, slug, write_json)


def mock_judgments(n_questions: int, neutral_ids: list[str], seed: str) -> list[dict]:
    rng = random.Random(seed)
    out = []
    for q in range(1, n_questions + 1):
        reveals = [f for f in neutral_ids if rng.random() < 0.12]
        out.append({"q": q, "reveals": reveals, "generic": rng.random() < 0.2, "note": "mock"})
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", required=True)
    ap.add_argument("--gen-model", required=True, help="model folder under runs/<arm>/ (e.g. claude-sonnet-5-5, mock)")
    ap.add_argument("--cases", default="cases/seed.json")
    ap.add_argument("--judge-model", default=DEFAULT_JUDGE)
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--backend", choices=["api", "cache"], default="api")
    args = ap.parse_args()
    llm = cached_call if args.backend == "cache" else call_claude

    cases = {c["id"]: c for c in load_cases(ROOT / args.cases)}
    template = load_prompt("judge")
    judge_dir = "mock" if args.dry_run else slug(args.judge_model)
    runs = sorted(f for r in RUN_ROOTS for f in (ROOT / r / args.arm / args.gen_model).glob("*.json"))
    if not runs:
        raise SystemExit(f"no runs for arm {args.arm} / {args.gen_model}; run run_arm.py first")
    out_dirs = set()

    done = skipped = failed = pending = 0
    for run_file in runs:
        run = json.loads(run_file.read_text(encoding="utf-8"))
        case = cases.get(run["case_id"])
        if case is None:
            print(f"skip {run_file.name}: case not in {args.cases}")
            continue
        out_dir = judgment_root(case) / args.arm / args.gen_model / judge_dir
        out_dirs.add(str(out_dir.relative_to(ROOT)))
        out = out_dir / run_file.name
        if out.exists() and not args.overwrite:
            skipped += 1
            continue
        facts_block, mapping = neutral_facts(case, seed=run["sample"])
        questions = run["questions"]
        q_block = "\n".join(f"{i}. {q}" for i, q in enumerate(questions, 1))
        prompt = fill(template, case_brief=case_brief(case), facts=facts_block, questions=q_block)
        try:
            if args.dry_run:
                raw = "(dry run)"
                judgments = mock_judgments(len(questions), list(mapping), f"{args.arm}:{run_file.name}")
            else:
                raw = llm(prompt, args.judge_model, max_tokens=3000)
                judgments = extract_json(raw)["judgments"]
        except Pending:
            pending += 1
            continue
        except Exception as e:
            failed += 1
            print(f"FAIL {run_file.name}: {e}")
            continue

        by_q = {int(j["q"]): j for j in judgments}
        rows = []
        for i in range(1, len(questions) + 1):
            j = by_q.get(i, {"reveals": [], "generic": False, "note": "missing from judge reply"})
            unknown = [f for f in j.get("reveals", []) if f not in mapping]
            if unknown:
                print(f"note {run_file.name} q{i}: judge used unknown ids {unknown}")
            rows.append({
                "q": i, "question": questions[i - 1],
                "reveals": [mapping[f] for f in j.get("reveals", []) if f in mapping],
                "generic": bool(j.get("generic", False)), "note": j.get("note", ""),
            })
        write_json(out, {"case_id": case["id"], "arm": args.arm, "gen_model": args.gen_model,
                         "judge_model": judge_dir, "sample": run["sample"], "mapping": mapping,
                         "rows": rows, "raw": raw})
        done += 1
        print(f"ok   {run_file.name}")
    print(f"\n{done} judged, {skipped} skipped (exist), {failed} failed, {pending} waiting for replies"
          f" -> {', '.join(sorted(out_dirs)) or '(nothing)'}")


if __name__ == "__main__":
    main()
