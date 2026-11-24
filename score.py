"""Score judged runs and compare arms.

Metrics per run (10 questions):
  crux_recall      share of crux facts revealed by any question
  twin_rate        share of twin facts revealed by any question
  discrimination   crux_recall - twin_rate   (the headline metric)
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

from common import ROOT, load_cases

METRICS = ["discrimination", "crux_recall", "twin_rate", "rr", "generic_rate"]


def score_run(judged: dict, case: dict) -> dict:
    cruxes = {f["id"] for f in case["hidden_facts"] if f["type"] == "crux"}
    twins = {f["id"] for f in case["hidden_facts"] if f["type"] == "twin"}
    revealed, first_crux = set(), None
    for row in judged["rows"]:
        hits = set(row["reveals"])
        revealed |= hits
        if first_crux is None and hits & cruxes:
            first_crux = row["q"]
    rows = judged["rows"]
    crux_recall = len(revealed & cruxes) / len(cruxes) if cruxes else 0.0
    twin_rate = len(revealed & twins) / len(twins) if twins else 0.0
    return {
        "crux_recall": crux_recall, "twin_rate": twin_rate,
        "discrimination": crux_recall - twin_rate,
        "rr": 1 / first_crux if first_crux else 0.0,
        "generic_rate": sum(r["generic"] for r in rows) / len(rows) if rows else 0.0,
    }


def collect(cases: dict) -> dict:
    """{(arm, gen_model, judge_model): {case_id: [scores per sample]}}"""
    out: dict = defaultdict(lambda: defaultdict(list))
    for f in sorted((ROOT / "judgments").glob("*/*/*/*.json")):
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

    print(f"{'arm':6} {'generator':22} {'judge':18} {'n':>3}  " + "  ".join(f"{m[:8]:>8}" for m in METRICS))
    for (arm, gen, judge), per_case in sorted(data.items()):
        cm = case_means(per_case)
        row = "  ".join(f"{pct(mean(v[m] for v in cm.values())):>8}" for m in METRICS)
        print(f"{arm:6} {gen:22} {judge:18} {len(cm):>3}  {row}")
        if args.by_category:
            groups = defaultdict(list)
            for cid, v in cm.items():
                groups[cases[cid]["category"]].append(v)
            for cat, vs in sorted(groups.items()):
                row = "  ".join(f"{pct(mean(v[m] for v in vs)):>8}" for m in METRICS)
                print(f"{'':6} {'  ' + cat:22} {'':18} {len(vs):>3}  {row}")
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
