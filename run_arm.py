"""Generate questions for every case with one arm (b0, b1, ...).

Usage:
  python3 run_arm.py --arm b0 --cases cases/seed.json
  python3 run_arm.py --arm b1 --cases cases/ --samples 3
  python3 run_arm.py --arm b0 --cases cases/seed.json --dry-run   # no API calls

Output: runs/<arm>/<model>/<case_id>__s<k>.json
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib

from common import (DEFAULT_GENERATOR, ROOT, call_claude, case_brief, extract_json, fill,
                           load_cases, load_prompt, slug, write_json)

N_QUESTIONS = 10


def mock_questions(case: dict, k: int) -> list[str]:
    opts = case["options"]
    return [f"[mock {k}.{i}] What would make '{opts[i % len(opts)]['label']}' the wrong choice?"
            for i in range(N_QUESTIONS)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", required=True, help="prompt name in prompts/ (b0, b1, ...)")
    ap.add_argument("--cases", default="cases/seed.json")
    ap.add_argument("--model", default=DEFAULT_GENERATOR)
    ap.add_argument("--samples", type=int, default=1, help="runs per case (to measure variance)")
    ap.add_argument("--only", nargs="*", help="case ids to run")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="use mock questions, no API")
    args = ap.parse_args()

    template = load_prompt(args.arm)
    prompt_hash = hashlib.sha256(template.encode()).hexdigest()[:12]
    cases = load_cases(ROOT / args.cases if not args.cases.startswith("/") else args.cases)
    if args.only:
        cases = [c for c in cases if c["id"] in set(args.only)]

    model_dir = "mock" if args.dry_run else slug(args.model)
    out_dir = ROOT / "runs" / args.arm / model_dir
    done = skipped = failed = 0
    for case in cases:
        prompt = fill(template, case_brief=case_brief(case))
        for k in range(args.samples):
            out = out_dir / f"{case['id']}__s{k}.json"
            if out.exists() and not args.overwrite:
                skipped += 1
                continue
            try:
                if args.dry_run:
                    raw, questions = "(dry run)", mock_questions(case, k)
                else:
                    raw = call_claude(prompt, args.model)
                    questions = [q.strip() for q in extract_json(raw)["questions"] if str(q).strip()]
            except Exception as e:  # keep going; report at the end
                failed += 1
                print(f"FAIL {case['id']} s{k}: {e}")
                continue
            if len(questions) != N_QUESTIONS:
                print(f"note {case['id']} s{k}: got {len(questions)} questions, keeping first {N_QUESTIONS}")
            write_json(out, {
                "case_id": case["id"], "arm": args.arm, "model": model_dir, "sample": k,
                "prompt_sha": prompt_hash, "created": dt.datetime.now(dt.timezone.utc).isoformat(),
                "questions": questions[:N_QUESTIONS], "raw": raw,
            })
            done += 1
            print(f"ok   {case['id']} s{k}")
    print(f"\n{done} written, {skipped} skipped (exist), {failed} failed -> {out_dir.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
