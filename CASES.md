# Writing Crux cases (v1)

A Crux case is a decision frozen at the moment it was made. The question generator sees only what the decider knew. Hidden facts sit behind it: **cruxes**, which make a different option best for the stated goal, and **twins**, which look just as relevant and change nothing.

The v0 pilot taught three things: a plain prompt finds every crux taken from a standard risk checklist; twins like "the vendor changed its logo" are ignored by every system; and with 10 questions there is no room left to rank. v1 cases are written against those three failures.

## The rules

1. **Freeze the moment.** Visible context ends where the decision was made. Nothing learned afterwards leaks into it, not even as a hint.
2. **The visible context leans.** A reader who sees only the visible context should pick `lean_without_hidden`. Every crux favours a different option.
3. **A crux must be learnable in time.** Write `how_to_learn`: whom the decider could have asked, or what they could have checked, before deciding. A fact that only luck or hindsight could reveal is not a crux (judging decisions by outcomes is "resulting"; see Annie Duke).
4. **Prefer cruxes outside the checklist.** Runway, contract clauses, a key person leaving, warranties: a plain prompt asks about all of them. Good cruxes are specific to the situation: what the customer actually measures, which step a process really depends on, a second-order effect of the obvious choice.
5. **Write twins a careful advisor would ask about.** Same topic, same shape, same apparent weight as the crux, and still no effect on the decision given the goal. If nobody would ever ask about the twin, it measures nothing. Explain in `why` why it does not matter.
6. **One twin per crux at least,** linked with `twin_of`.
7. **Goal first.** Cruxes and twins are judged against `goal`. If a twin would matter under a different goal, that is fine; it must not matter under this one.
8. **Famous cases change domain.** Models know Challenger, Everest and *12 Angry Men*. Keep the structure and change the domain, the people and the numbers.
9. **Privacy and provenance.**
   - `human-real`: a real decision, anonymised. Remove names, employers, places and dates that identify anyone.
   - `human-adapted`: a real decision with details changed by a person.
   - `model-adapted`: a public account (a post-mortem, a forum post) adapted by a model.
   - `synthetic`: invented.

   Everything except `synthetic` goes in `cases/private/`, which git ignores. Keep the source link in `notes` only there. The public seed set holds synthetic cases only. Runs and judgments of private cases are written to `runs_private/` and `judgments_private/`, which git also ignores: judge notes quote the hidden facts.
10. **Set `"benchmark": "v1"`** and run `python3 validate_cases.py cases/`. Errors must be fixed; `hint:` lines are worth a second look.

## Difficulty check

A v1 case is kept for the test set only if a plain prompt (B0) and the one-prompt taxonomy (B1) do not both find every crux within their first 5 questions. Cases both find are moved to a `too-easy` list: they still work as smoke tests, but they cannot separate systems.

Run it with `python3 difficulty.py --gen-model <generator label> --judge-model <judge label>` after judging both arms.

This filter makes the set harder for B0 and B1 specifically. Report results with that caveat, and re-check difficulty with any new baseline.

## Headline metrics

`disc@3` and `disc@5`: crux recall minus twin rate within the first 3 and 5 questions. `crux@10` stays as a secondary metric. See `score.py`.

## Template

Copy `cases/TEMPLATE.json`, add `"benchmark": "v1"` and a `how_to_learn` line to each crux.
