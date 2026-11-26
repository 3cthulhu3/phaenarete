"""Difficulty check for v1 cases (see CASES.md).

A case is "too easy" when every baseline arm finds all of its cruxes within the first K questions.
Per case it prints crux@K and twin@K for each arm and the verdict.

Usage:
  python3 difficulty.py --gen-model v1-sonnet --judge-model v1-opus
  python3 difficulty.py --gen-model v1-sonnet --judge-model v1-opus --arms b0 b1 --k 5 --cases cases/
"""

from __future__ import annotations

import argparse
import json

from common import JUDGMENT_ROOTS, ROOT, load_cases
from score import score_run


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default="cases/")
    ap.add_argument("--arms", nargs="+", default=["b0", "b1"])
    ap.add_argument("--gen-model", required=True)
    ap.add_argument("--judge-model", required=True)
    ap.add_argument("--k", type=int, default=5, choices=[3, 5, 10])
    args = ap.parse_args()

    cases = {c["id"]: c for c in load_cases(ROOT / args.cases)}
    table: dict[str, dict[str, dict]] = {}
    for arm in args.arms:
        files = [f for r in JUDGMENT_ROOTS for f in (ROOT / r / arm / args.gen_model / args.judge_model).glob("*.json")]
        for f in sorted(files):
            j = json.loads(f.read_text(encoding="utf-8"))
            if j["case_id"] in cases:
                table.setdefault(j["case_id"], {})[arm] = score_run(j, cases[j["case_id"]])

    k = args.k
    head = "  ".join(f"{a + ' crux/twin':>16}" for a in args.arms)
    print(f"{'case':42} {head}  verdict")
    easy = 0
    for cid in sorted(table):
        row = table[cid]
        if set(row) != set(args.arms):
            print(f"{cid:42} (missing arms: {sorted(set(args.arms) - set(row))})")
            continue
        cells = "  ".join(f"{100 * row[a][f'crux@{k}']:>8.0f}/{100 * row[a][f'twin@{k}']:<7.0f}" for a in args.arms)
        too_easy = all(row[a][f"crux@{k}"] == 1.0 for a in args.arms)
        easy += too_easy
        print(f"{cid:42} {cells}  {'too easy' if too_easy else 'keep'}")
    print(f"\n{easy} of {len(table)} cases too easy at k={k} (every arm found every crux).")


if __name__ == "__main__":
    main()
