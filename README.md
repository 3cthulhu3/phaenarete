# Phaenarete · Crux benchmark (Phase 1)

Phaenarete finds the questions worth answering before a decision. The name is Socrates' mother, a midwife: in Plato's *Theaetetus* he calls his method midwifery, helping others give birth to ideas rather than handing them answers.

**Crux** is the benchmark. In textual criticism a *crux interpretum* is the point on which a whole reading turns; here a crux is a hidden fact that turns a decision. This repo holds the benchmark that decides whether it is worth building: does a question pipeline find **decision-changing facts (cruxes)** better than a plain prompt, without chasing **equally plausible but irrelevant facts (twins)**?

The design is adapted from Ask2Decide (arXiv 2611.13015), which uses zero-value "twins" to test whether an agent asks about what matters or about everything.

## Status (pilot, November 2026)

**The v0 pipeline lost to a plain prompt, and the seed benchmark turned out too easy to tell good systems apart.**

| Arm | Crux recall @3 | @5 | @10 | Twin rate @10 | MRR x100 |
| --- | --- | --- | --- | --- | --- |
| B0: plain prompt | 58 | 79 | 100 | 4 | 63 |
| B1: one prompt + operator taxonomy | **71** | 79 | 96 | 0 | 82 |
| Phaenarete v0 pipeline | 17 | 46 | 79 | 4 | 42 |

Pipeline minus B0 on discrimination: -21 points (95% bootstrap CI -33 to -8). 12 synthetic seed cases, one sample per arm; Sonnet-class generator, Opus-class judge. Outputs are in `runs/` and `judgments/`.

What it shows:
- **Ceiling.** With 10 questions and 2 cruxes per case, a plain prompt finds every crux; the seed cruxes sit in standard risk checklists (runway, contracts, key people). Twins are too obviously irrelevant, so no arm asks about them and discrimination collapses into recall.
- **Why v0 lost.** Of 5 missed cruxes, 2 were never generated; 3 were generated and then dropped by selection. Coverage slots tied to the parse step's uncertainty map and a score that rewards cheap, easy questions push decisive questions out of the top 3. The critic passed 87% of candidates.
- **Reading.** This falsifies the v0 design, not the idea. A single well-built prompt (B1) is the bar any multi-stage system has to clear.

### v1 difficulty check (first 6 cases)

v1 moves the headline to `disc@3` and `disc@5` and adds writing rules in [CASES.md](CASES.md). The first six v1 cases (3 synthetic in `cases/v1/`, 3 adapted from public post-mortems and kept private) were run against B0 and B1, same setup as the pilot.

| Arm | Crux @3 | @5 | @10 | Twin rate @5 | disc@3 | disc@5 |
| --- | --- | --- | --- | --- | --- | --- |
| B0 | 56 | 78 | 100 | 17 | 56 | 61 |
| B1 | 53 | 78 | 78 | 17 | 36 | 61 |

- **Twins now work.** Both arms asked about a twin in some cases (who holds the backup login, whether historical data exists): plausible advisor questions that do not move the decision. In v0 no arm ever did, so discrimination could not move.
- **Cruxes are still findable.** Every one of the 13 cruxes was found by at least one arm within 10 questions; 2 of 6 cases are too easy at 5 questions. Even a crux outside the usual checklist (users rewarded for speed while the product slows them down) was found by both arms. Cruxes a model writes are cruxes a model can think of.
- **Consequence.** The hard part of the test set has to come from people's own decisions, where the crux was idiosyncratic enough that they missed it themselves. Model-written cases are useful for development and for twins.

### v1 difficulty check, second batch (10 cases)

Four more cases, sourced from public investigation and audit reports (NTSB, CSB, GAO): three adapted and kept private, one public synthetic case (`personal-mountain-summit-push`) that keeps the structure of a well-known maritime investigation in a different domain. All 10 cases, same setup:

| Arm | Crux @3 | @5 | @10 | Twin rate @5 | disc@3 | disc@5 |
| --- | --- | --- | --- | --- | --- | --- |
| B0 | 48 | 77 | 95 | 10 | 48 | 67 |
| B1 | 47 | 77 | 82 | 10 | 37 | 67 |

- **The new batch is harder early, not late.** Over the 4 new cases, crux@3 is 38 for both arms (the first 6 cases: 56 and 53), but crux@10 is still 88. Cruxes that depend on a physical check (how the vessel is loaded, who stands next to a tank) come at questions 4 to 9.
- **First crux that no arm found.** In the mountain case, both arms found the stale forecast with their first question but neither found that the wind gauge was broken. B1 came close: it questioned the "stable season" impression but not the instrument behind it. A crux hidden behind someone's reassurance is the pattern worth writing more of.
- **B1 is not ahead of B0** on these 10 cases (paired difference in disc@3 −12, 95% CI [−40, 17]). The pilot's B1 lead does not carry over to v1.

### Pipeline v1 (14 cases)

Pipeline v1 ([pipeline1.py](pipeline1.py), arm `phaenarete1`) makes two calls. The first maps the decision: the leaning option, a premortem (five ways it fails) and the load-bearing beliefs, each with what it rests on and how that source could be wrong now. The second writes ten questions that check those sources, most decision-changing first. There is no operator quota and no coverage rule. Four held-out cases (`cases/v1/v1-heldout.json`) were written before pipeline v1 was run on anything; B0 and B1 were run on them too.

| Arm | Crux @3 | @5 | @10 | Twin rate @5 | disc@3 | disc@5 |
| --- | --- | --- | --- | --- | --- | --- |
| B0 | 52 | 80 | 93 | 11 | 49 | 69 |
| B1 | 55 | 76 | 87 | 11 | 44 | 65 |
| Phaenarete v1 | 42 | 56 | 68 | 7 | 38 | 49 |

- **Pipeline v1 loses to both baselines.** B0 minus v1: disc@5 +20 (95% CI [2, 39]), crux@10 +25 (95% CI [7, 46]). This is the second pipeline design to lose to a single prompt.
- **Why it loses: the premortem turns questions into mitigation.** Once the map takes the leaning option as given, the questions go into how to make that option safe (containment checks, load tests, rollback switches, lead times for parts) instead of what would change the choice. In the tank case, B0 asks what the inspection report itself concludes; v1 asks an engineer to compute the remaining life again and never finds either crux.
- **It did not fix what it was built for.** The broken wind gauge in the mountain case was still missed, and so was the crash dashboard that leaves out the oldest OS version (held out).
- **What holds.** B0 and B1 are close to each other: B0 minus B1, disc@3 +5 (95% CI [−17, 29]). On these cases a plain prompt finds 93% of cruxes within ten questions, so the remaining headroom is at 3 and 5 questions and in a small set of cruxes no arm finds.

Next: stop adding stages in front of the question writer. Two options to test against B0 at 3 and 5 questions: re-rank B0's own questions by how directly an answer would change the choice, and add a second pass that asks only about the source behind each reassurance in the context.

## Layout

```
case.schema.json     case format (cruxes, twins, visible context)
cases/seed.json      12 synthetic seed cases (English)
cases/v1/            v1 synthetic cases, including 4 held out from pipeline design
cases/TEMPLATE.json  copy this to write a case from a real decision
cases/private/       your human-written cases (git-ignored)
prompts/b0.txt       plain baseline: "10 most important questions"
prompts/b1.txt       same model, operator taxonomy in one prompt
prompts/judge.txt    judge prompt (sees hidden facts under neutral ids)
prompts/pipeline/    parse, generate and critic prompts of the Phaenarete pipeline
prompts/pipeline1/   map and ask prompts of pipeline v1
pipeline.py          the Phaenarete pipeline (three model stages + deterministic selection)
pipeline1.py         pipeline v1 (map -> ask, two model stages)
validate_cases.py    checks cases (no external packages)
run_arm.py           generates questions for one arm (b0, b1, phaenarete, phaenarete1)
pilot.py             export prompts / ingest replies for the prompt-cache backend
inspect_run.py       readable view of one run with its judge results (for error analysis)
tests/               unit tests for scoring and selection
judge.py             judges which hidden facts each question would reveal
score.py             metrics, per-category view, paired comparison with bootstrap CI
```

Python 3.10+, standard library only.

## Run

```bash
export ANTHROPIC_API_KEY=...
python3 validate_cases.py cases/
python3 run_arm.py --arm b0 --cases cases/            
python3 run_arm.py --arm b1 --cases cases/
python3 run_arm.py --arm phaenarete --cases cases/
python3 judge.py --arm b0 --gen-model claude-sonnet-5-5 --cases cases/   # judge: claude-opus-5-5
python3 judge.py --arm b1 --gen-model claude-sonnet-5-5 --cases cases/
python3 judge.py --arm phaenarete --gen-model claude-sonnet-5-5 --cases cases/
python3 score.py --cases cases/ --compare b0 phaenarete --by-category
python3 inspect_run.py runs/phaenarete/claude-sonnet-5-5/<case_id>__s0.json --rejects
```

Add `--dry-run` to `run_arm.py` and `judge.py` to test the plumbing without API calls (mock numbers mean nothing). Use `--samples 3` on `run_arm.py` to measure run-to-run variance. Unit tests: `python3 -m unittest discover tests`.

### Without an API key (prompt cache)

Add `--backend cache` to `run_arm.py` and `judge.py`. Each missing model reply is written to `cache/pending/`; `python3 pilot.py export --name <name>` collects them into `pilot/<name>_part1.json` ({key: prompt}). Answer the prompts by any means (another chat, a person), save `{key: reply}` as JSON, run `python3 pilot.py ingest <file>`, and re-run the same command. The pipeline arm needs three rounds (parse, generate, critic). The cache is keyed by prompt text only, so label runs with `--model`, e.g. `--model manual-sonnet`.

On Windows PowerShell: set the key with `$env:ANTHROPIC_API_KEY="..."` and use `python` instead of `python3`.

## The Phaenarete pipeline (v0)

1. **Parse** (model): map the decision into criteria, stated facts, assumptions and 4-7 uncertainties that could change which option is best.
2. **Generate** (model): 4-6 candidate questions for each of seven operators: discriminate, surface, test, bound, expand, close, calibrate. Each names the uncertainty it targets and how to get the answer.
3. **Critic** (model, separate call that only sees the decision and the questions): four pass/fail checks (generic, presupposes, already answered, no answer path) and five 1-5 scores.
4. **Select** (plain Python): S = relevance x uncertainty x impact x answerability / cost. Failed candidates are dropped; one strong question per uncertainty is kept for coverage; at least one `close` question; the rest by maximal marginal relevance; near-duplicates are never picked twice. Ten questions, best first.

Every run stores the full trace (map, all candidates, reviews, why each question was picked), so failures can be traced to a stage.

Three to four model calls per case instead of one: the pipeline costs several times what B0 costs per case.

## Development discipline

Tune the pipeline on `cases/seed.json` only. The human cases in `cases/private/` are the test set: run them when a version is frozen, and do not change prompts because of what you saw there. The seed cases and the first pipeline prompts were written by the same model, so seed-set results are optimistic.

## Metrics

| Metric | Meaning |
| --- | --- |
| discrimination | crux recall minus twin rate (headline) |
| crux_recall | share of cruxes revealed by the 10 questions |
| twin_rate | share of twins revealed |
| rr | 1 / rank of the first crux-revealing question |
| generic_rate | share of questions that would fit any decision |

**Gate B (week 4):** the Phaenarete pipeline must beat B0 on discrimination by at least 15 points. Below 5 points, change direction.

## Writing a case

1. Copy `cases/TEMPLATE.json` to `cases/private/<id>.json`. That folder is git-ignored: human cases stay off GitHub and out of future training data.
2. Use a decision you or someone you know actually faced. Remove names and identifying details.
3. Write the visible context so a reader leans towards one option.
4. Add at least two cruxes (facts that make another option best for the stated goal) and, for each, a twin with the same shape and topic that does not change anything.
5. Run `python3 validate_cases.py cases/`.

At least 18 of the 30 cases should be human-written (`source: human-real` or `human-adapted`). Model-written cases can inflate model scores.

## Known limits

- One-shot questions only; the pipeline does not yet update its map from the decider's answers.
- The judge is a model. Check its calls by hand on at least 3 cases per arm before trusting the numbers.
- 12 to 30 cases give wide confidence intervals; read the CI, not just the mean.
