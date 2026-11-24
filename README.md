# Phaenarete · Crux benchmark (Phase 1)

Phaenarete finds the questions worth answering before a decision. The name is Socrates' mother, a midwife: in Plato's *Theaetetus* he calls his method midwifery, helping others give birth to ideas rather than handing them answers.

**Crux** is the benchmark. In textual criticism a *crux interpretum* is the point on which a whole reading turns; here a crux is a hidden fact that turns a decision. This repo holds the benchmark that decides whether it is worth building: does a question pipeline find **decision-changing facts (cruxes)** better than a plain prompt, without chasing **equally plausible but irrelevant facts (twins)**?

The design is adapted from Ask2Decide (arXiv 2611.13015), which uses zero-value "twins" to test whether an agent asks about what matters or about everything.

## Layout

```
case.schema.json     case format (cruxes, twins, visible context)
cases/seed.json      12 synthetic seed cases (English)
cases/TEMPLATE.json  copy this to write a case from a real decision
cases/private/       your human-written cases (git-ignored)
prompts/b0.txt       plain baseline: "10 most important questions"
prompts/b1.txt       same model, operator taxonomy in one prompt
prompts/judge.txt    judge prompt (sees hidden facts under neutral ids)
prompts/pipeline/    parse, generate and critic prompts of the Phaenarete pipeline
pipeline.py          the Phaenarete pipeline (three model stages + deterministic selection)
validate_cases.py    checks cases (no external packages)
run_arm.py           generates questions for one arm (b0, b1, phaenarete)
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
python3 run_arm.py --arm b0 --cases cases/            # generator: claude-sonnet-5-5 by default
python3 run_arm.py --arm b1 --cases cases/
python3 run_arm.py --arm phaenarete --cases cases/
python3 judge.py --arm b0 --gen-model claude-sonnet-5-5 --cases cases/   # judge: claude-opus-5-5
python3 judge.py --arm b1 --gen-model claude-sonnet-5-5 --cases cases/
python3 judge.py --arm phaenarete --gen-model claude-sonnet-5-5 --cases cases/
python3 score.py --cases cases/ --compare b0 phaenarete --by-category
python3 inspect_run.py runs/phaenarete/claude-sonnet-5-5/<case_id>__s0.json --rejects
```

Add `--dry-run` to `run_arm.py` and `judge.py` to test the plumbing without API calls (mock numbers mean nothing). Use `--samples 3` on `run_arm.py` to measure run-to-run variance. Unit tests: `python3 -m unittest discover tests`.

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
