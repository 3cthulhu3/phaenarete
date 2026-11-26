"""Move prompts out of and replies into the prompt cache, for running without an API key.

Flow:
  python3 run_arm.py --arm b0 --backend cache --model manual-sonnet   # records pending prompts
  python3 pilot.py export --name b0 --parts 1                          # -> pilot/b0_part1.json  {key: prompt}
  ... answer every prompt (another chat, a person, ...) into a file {key: reply}
  python3 pilot.py ingest pilot/b0_replies.json                        # -> cache/<key>.json
  python3 run_arm.py --arm b0 --backend cache --model manual-sonnet   # now completes
The pipeline arm needs several rounds (parse, generate, critic): repeat until nothing is pending.

  python3 pilot.py status
"""

from __future__ import annotations

import argparse
import json

from common import CACHE_DIR, PENDING_DIR, ROOT, extract_json, write_json

EXPORTED_DIR = CACHE_DIR / "exported"   # prompts handed out, waiting for replies

PILOT_DIR = ROOT / "pilot"


def export(name: str, parts: int, contains: str | None = None) -> None:
    files = sorted(PENDING_DIR.glob("*.txt")) if PENDING_DIR.exists() else []
    if not files:
        print("nothing pending")
        return
    prompts = {f.stem: f.read_text(encoding="utf-8") for f in files}
    if contains:
        prompts = {k: v for k, v in prompts.items() if contains in v}
    if not prompts:
        print("nothing pending that matches")
        return
    keys = list(prompts)
    size = -(-len(keys) // parts)
    for i in range(parts):
        chunk = keys[i * size:(i + 1) * size]
        if not chunk:
            continue
        out = PILOT_DIR / f"{name}_part{i + 1}.json"
        write_json(out, {k: prompts[k] for k in chunk})
        print(f"{out.relative_to(ROOT)}: {len(chunk)} prompts")
    EXPORTED_DIR.mkdir(parents=True, exist_ok=True)
    for k in keys:  # exported prompts leave the pending list, so the next export does not repeat them
        (PENDING_DIR / f"{k}.txt").replace(EXPORTED_DIR / f"{k}.txt")


def ingest(paths: list[str]) -> None:
    stored = bad = unknown = 0
    for path in paths:
        replies = json.loads((ROOT / path).read_text(encoding="utf-8"))
        for key, reply in replies.items():
            text = reply if isinstance(reply, str) else json.dumps(reply, ensure_ascii=False)
            try:
                extract_json(text)
            except Exception as e:
                bad += 1
                print(f"skip {key}: reply is not valid JSON ({e})")
                continue
            pending = PENDING_DIR / f"{key}.txt"
            if not pending.exists():
                pending = EXPORTED_DIR / f"{key}.txt"
            if not pending.exists() and not (CACHE_DIR / f"{key}.json").exists():
                unknown += 1
                print(f"note {key}: no matching pending prompt")
            prompt = pending.read_text(encoding="utf-8") if pending.exists() else None
            write_json(CACHE_DIR / f"{key}.json", {"key": key, "prompt": prompt, "reply": text})
            if pending.exists():
                pending.unlink()
            stored += 1
    print(f"{stored} stored, {bad} rejected, {unknown} without a pending prompt")


def status() -> None:
    n_pending = len(list(PENDING_DIR.glob("*.txt"))) if PENDING_DIR.exists() else 0
    n_cached = len(list(CACHE_DIR.glob("*.json"))) if CACHE_DIR.exists() else 0
    n_out = len(list(EXPORTED_DIR.glob("*.txt"))) if EXPORTED_DIR.exists() else 0
    print(f"{n_cached} cached replies, {n_pending} pending prompts, {n_out} exported and awaiting replies")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--name", required=True)
    e.add_argument("--parts", type=int, default=1)
    e.add_argument("--contains", help="only prompts containing this text")
    i = sub.add_parser("ingest")
    i.add_argument("files", nargs="+")
    sub.add_parser("status")
    args = ap.parse_args()
    if args.cmd == "export":
        export(args.name, args.parts, args.contains)
    elif args.cmd == "ingest":
        ingest(args.files)
    else:
        status()


if __name__ == "__main__":
    main()
