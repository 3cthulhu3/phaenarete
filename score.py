"""Score judged runs and compare arms.

Metrics per run (questions are ranked, best first):
  crux@k           share of crux facts revealed by the first k questions (k = 3, 5, 10)
  twin@k           share of twin facts revealed by the first k questions
  disc@k           crux@k - twin@k   (disc@3 and disc@5 are the v1 headline metrics)
  rr               1 / rank of the first question that reveals a crux (0 if none)
  generic_rate     share of questions the judge marked generic

Usage:
  python3 score.py                                   # every arm/model/judge found under judgments/
  python3 score.py --compare b0 b1                   # paired difference with a bootstrap 95% CI
  python3 score.py --by-category
"""

from __future__ import annotations

import argparse
import json
import random
from collections import defaultdict
from statistics import mean

from common import JUDGMENT_ROOTS, ROOT, load_cases

KS = (3, 5, 10)
METRICS = ["disc@3", "disc@5", "crux@3", "crux@5", "crux@10", "twin@5", "rr", "generic_rate"]


def score_run(judged: dict, case: dict) -> dict:
    """Metrics for one judged run. Questions are in rank order, so @k uses the first k."""
    cruxes = {f["id"] for f in case["hidden_facts"] if f["type"] == "crux"}
    twins = {f["id"] for f in case["hidden_facts"] if f["type"] == "twin"}
    rows = judged["rows"]
    out: dict = {}
    for k in KS:
        revealed = set().union(*(set(r["reveals"]) for r in rows[:k])) if rows[:k] else set()
        crux = len(revealed & cruxes) / len(cruxes) if cruxes else 0.0
        twin = len(revealed & twins) / len(twins) if twins else 0.0
        out[f"crux@{k}"], out[f"twin@{k}"], out[f"disc@{k}"] = crux, twin, crux - twin
    first_crux = next((r["q"] for r in rows if set(r["reveals"]) & cruxes), None)
    out["rr"] = 1 / first_crux if first_crux else 0.0
    out["generic_rate"] = sum(r["generic"] for r in rows) / len(rows) if rows else 0.0
    # v0 names, kept so older notes stay readable
    out["crux_recall"], out["twin_rate"], out["discrimination"] = out["crux@10"], out["twin@10"], out["disc@10"]
    return out


def collect(cases: dict) -> dict:
    """{(arm, gen_model, judge_model): {case_id: [scores per sample]}}"""
    out: dict = defaultdict(lambda: defaultdict(list))
    for f in sorted(f for r in JUDGMENT_ROOTS for f in (ROOT / r).glob("*/*/*/*.json")):
        judged = json.loads(f.read_text(encoding="utf-8"))
        case = cases.get(judged["case_id"])
        if case is None:
            continue
        key = (judged["arm"], judged["gen_model"], judged["judge_model"])
        out[key][case["id"]].append(score_run(judged, case))
    return out


def case_means(per_case: dict) -> dict:
    return {cid: {m: mean(s[m] for s in samples) for m in METRICS} for cid, samples in per_case.items()}


def bootstrap_ci(diffs: list[float], n: int = 10000, seed: int = 0) -> tuple[float, float]:
    rng = random.Random(seed)
    stats = sorted(mean(rng.choice(diffs) for _ in diffs) for _ in range(n))
    return stats[int(0.025 * n)], stats[int(0.975 * n) - 1]


def pct(x: float) -> str:
    return f"{100 * x:6.1f}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cases", default="cases/seed.json")
    ap.add_argument("--compare", nargs=2, metavar=("ARM_A", "ARM_B"))
    ap.add_argument("--by-category", action="store_true")
    args = ap.parse_args()

    cases = {c["id"]: c for c in load_cases(ROOT / args.cases)}
    data = collect(cases)
    if not data:
        raise SystemExit("no judgments found; run judge.py first")

    print(f"{'arm':11} {'generator':22} {'judge':18} {'n':>3}  " + "  ".join(f"{m[:8]:>8}" for m in METRICS))
    for (arm, gen, judge), per_case in sorted(data.items()):
        cm = case_means(per_case)
        row = "  ".join(f"{pct(mean(v[m] for v in cm.values())):>8}" for m in METRICS)
        print(f"{arm:11} {gen:22} {judge:18} {len(cm):>3}  {row}")
        if args.by_category:
            groups = defaultdict(list)
            for cid, v in cm.items():
                groups[cases[cid]["category"]].append(v)
            for cat, vs in sorted(groups.items()):
                row = "  ".join(f"{pct(mean(v[m] for v in vs)):>8}" for m in METRICS)
                print(f"{'':11} {'  ' + cat:22} {'':18} {len(vs):>3}  {row}")
    print("(values in percentage points; rr is mean reciprocal rank x100)")

    if args.compare:
        a, b = args.compare
        keys_a = [k for k in data if k[0] == a]
        keys_b = [k for k in data if k[0] == b]
        for ka in keys_a:
            for kb in keys_b:
                if ka[1:] != kb[1:]:
                    continue  # compare only same generator and judge
                ma, mb = case_means(data[ka]), case_means(data[kb])
                shared = sorted(set(ma) & set(mb))
                if len(shared) < 2:
                    continue
                print(f"\n{b} minus {a}  (generator {ka[1]}, judge {ka[2]}, {len(shared)} paired cases)")
                for m in METRICS:
                    diffs = [mb[c][m] - ma[c][m] for c in shared]
                    lo, hi = bootstrap_ci(diffs)
                    print(f"  {m:15} {pct(mean(diffs))}   95% CI [{pct(lo)}, {pct(hi)}]")


if __name__ == "__main__":
    main()
