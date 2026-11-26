"""Print a readable view of one run, with judge results if they exist. For error analysis.

Usage:
  python3 inspect_run.py runs/phaenarete/claude-sonnet-5-5/career-startup-lead__s0.json
  python3 inspect_run.py runs/phaenarete/claude-sonnet-5-5/career-startup-lead__s0.json --rejects
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from common import JUDGMENT_ROOTS, ROOT, load_cases


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("run")
    ap.add_argument("--cases", default="cases/")
    ap.add_argument("--rejects", action="store_true", help="also list candidates that failed a check")
    args = ap.parse_args()

    run_path = Path(args.run)
    run = json.loads(run_path.read_text(encoding="utf-8"))
    case = {c["id"]: c for c in load_cases(ROOT / args.cases)}[run["case_id"]]
    facts = {f["id"]: f for f in case["hidden_facts"]}

    judged = {}
    for j in (f for r in JUDGMENT_ROOTS for f in (ROOT / r / run["arm"] / run["model"]).glob(f"*/{run_path.name}")):
        judged = {r["q"]: r for r in json.loads(j.read_text(encoding="utf-8"))["rows"]}
        break

    print(f"# {case['id']}  ({run['arm']}, {run['model']}, sample {run['sample']})\n")
    print(case["decision"])
    print("\nHidden facts:")
    for f in case["hidden_facts"]:
        print(f"  {f['id']} [{f['type']}] {f['text']}")

    trace = run.get("trace")
    if trace:
        print(f"\nCandidates: {trace['n_candidates']}, passing checks: {trace['n_passing']}, "
              f"failed: {trace['fail_counts']}")
        print("Uncertainties found by parse:")
        for u in trace["graph"].get("uncertainties", []):
            print(f"  {u.get('id')}: {u.get('text')}")

    print("\nQuestions:")
    chosen = trace["chosen"] if trace else [{"question": q} for q in run["questions"]]
    for i, c in enumerate(chosen, 1):
        hits = judged.get(i, {}).get("reveals", [])
        tag = " ".join(f"{h}[{facts[h]['type']}]" for h in hits) if hits else ""
        meta = f"  ({c['operator']}, {c['target']}, S={c['S']:.0f}, {c['picked_by']})" if trace else ""
        generic = " GENERIC" if judged.get(i, {}).get("generic") else ""
        print(f"{i:2}. {c['question']}{meta}{'  -> ' + tag if tag else ''}{generic}")

    if args.rejects and trace:
        print("\nRejected candidates:")
        for c in trace["candidates"]:
            if c["failed"]:
                print(f"  - {c['question']}  [{', '.join(c['failed'])}]")


if __name__ == "__main__":
    main()
