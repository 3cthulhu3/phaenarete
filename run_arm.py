"""Generate questions for every case with one arm.

Arms: b0, b1 (single prompt from prompts/<arm>.txt) and phaenarete (the multi-stage
pipeline in pipeline.py).

Usage:
  python3 run_arm.py --arm b0 --cases cases/seed.json
  python3 run_arm.py --arm phaenarete --cases cases/seed.json
  python3 run_arm.py --arm b1 --cases cases/ --samples 3
  python3 run_arm.py --arm phaenarete --dry-run      # no API calls

Output: runs/<arm>/<model>/<case_id>__s<k>.json  (phaenarete runs also store a full trace)
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib

import pipeline
from common import (DEFAULT_GENERATOR, ROOT, run_root, Pending, cached_call, call_claude, case_brief, extract_json, fill,
                    load_cases, load_prompt, slug, write_json)

PIPELINE_ARM = "phaenarete"

N_QUESTIONS = 10


def mock_questions(case: dict, k: int) -> list[str]:
    opts = case["options"]
    return [f"[mock {k}.{i}] What would make '{opts[i % len(opts)]['label']}' the wrong choice?"
            for i in range(N_QUESTIONS)]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--arm", required=True, help="b0, b1, ... (a prompt in prompts/) or phaenarete")
    ap.add_argument("--cases", default="cases/seed.json")
    ap.add_argument("--model", default=DEFAULT_GENERATOR)
    ap.add_argument("--samples", type=int, default=1, help="runs per case (to measure variance)")
    ap.add_argument("--only", nargs="*", help="case ids to run")
    ap.add_argument("--overwrite", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="use mock questions, no API")
    ap.add_argument("--backend", choices=["api", "cache"], default="api",
                    help="cache: look replies up in cache/, write missing prompts to cache/pending/ (see pilot.py)")
    args = ap.parse_args()
    llm = cached_call if args.backend == "cache" else call_claude

    is_pipeline = args.arm == PIPELINE_ARM
    if is_pipeline:
        template, prompt_hash = "", pipeline.prompt_fingerprint()
    else:
        template = load_prompt(args.arm)
        prompt_hash = hashlib.sha256(template.encode()).hexdigest()[:12]
    cases = load_cases(ROOT / args.cases if not args.cases.startswith("/") else args.cases)
    if args.only:
        cases = [c for c in cases if c["id"] in set(args.only)]

    model_dir = "mock" if args.dry_run else slug(args.model)
    out_dirs = set()
    done = skipped = failed = pending = 0
    for case in cases:
        prompt = fill(template, case_brief=case_brief(case))
        for k in range(args.samples):
            out_dir = run_root(case) / args.arm / model_dir
            out_dirs.add(str(out_dir.relative_to(ROOT)))
            out = out_dir / f"{case['id']}__s{k}.json"
            if out.exists() and not args.overwrite:
                skipped += 1
                continue
            trace = None
            try:
                if is_pipeline:
                    call = (pipeline.mock_call(case) if args.dry_run
                            else lambda p, mt: llm(p, args.model, max_tokens=mt))
                    questions, trace = pipeline.run(case, call)
                    raw = "(pipeline: see trace)"
                elif args.dry_run:
                    raw, questions = "(dry run)", mock_questions(case, k)
                else:
                    raw = llm(prompt, args.model)
                    questions = [q.strip() for q in extract_json(raw)["questions"] if str(q).strip()]
            except Pending:
                pending += 1
                continue
            except Exception as e:  # keep going; report at the end
                failed += 1
                print(f"FAIL {case['id']} s{k}: {e}")
                continue
            if len(questions) != N_QUESTIONS:
                print(f"note {case['id']} s{k}: got {len(questions)} questions, keeping first {N_QUESTIONS}")
            record = {
                "case_id": case["id"], "arm": args.arm, "model": model_dir, "sample": k,
                "prompt_sha": prompt_hash, "created": dt.datetime.now(dt.timezone.utc).isoformat(),
                "questions": questions[:N_QUESTIONS], "raw": raw,
            }
            if trace is not None:
                record["trace"] = trace
            write_json(out, record)
            done += 1
            print(f"ok   {case['id']} s{k}")
    print(f"\n{done} written, {skipped} skipped (exist), {failed} failed, {pending} waiting for replies"
          f" -> {', '.join(sorted(out_dirs)) or '(nothing)'}")


if __name__ == "__main__":
    main()
