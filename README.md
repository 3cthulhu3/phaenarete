# Phaenarete · Crux benchmark (Phase 0)

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
validate_cases.py    checks cases (no external packages)
run_arm.py           generates questions for one arm
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
python3 judge.py --arm b0 --gen-model claude-sonnet-5-5 --cases cases/   # judge: claude-opus-5-5
python3 judge.py --arm b1 --gen-model claude-sonnet-5-5 --cases cases/
python3 score.py --cases cases/ --compare b0 b1 --by-category
```

Add `--dry-run` to any of the first three commands to test the plumbing without API calls. Use `--samples 3` on `run_arm.py` to measure run-to-run variance.

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

- One-shot questions only; no dialogue yet.
- The judge is a model. Check its calls by hand on at least 3 cases per arm before trusting the numbers.
- 12 to 30 cases give wide confidence intervals; read the CI, not just the mean.
