"""Tests for the deterministic parts of the pipeline. Run: python3 -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import pipeline  # noqa: E402
from common import load_cases  # noqa: E402

GRAPH = {"uncertainties": [{"id": "u1"}, {"id": "u2"}, {"id": "u3"}]}


def cand(q, op="discriminate", target="new", impact=4, s=10.0, failed=()):
    return {"question": q, "operator": op, "target": target, "S": s, "failed": list(failed),
            "review": {"impact": impact}, "picked_by": None}


def filler(n, start=0, s=5.0):
    words = ["budget", "deadline", "contract", "supplier", "manager", "battery", "license", "audit",
             "runway", "commute", "warranty", "refund", "headcount", "migration", "latency", "margin"]
    return [cand(f"How does the {words[(start + i) % len(words)]} {i} affect option {i}?", s=s - i * 0.1)
            for i in range(n)]


class ScoreTest(unittest.TestCase):
    def test_formula(self):
        s, failed = pipeline.score({"relevance": 5, "uncertainty": 4, "impact": 5, "answerability": 3, "cost": 2})
        self.assertEqual(s, 5 * 4 * 5 * 3 / 2)
        self.assertEqual(failed, [])

    def test_flags_and_bad_values(self):
        s, failed = pipeline.score({"generic": True, "relevance": "9", "uncertainty": None, "impact": 3,
                                    "answerability": 3, "cost": 0})
        self.assertEqual(failed, ["generic"])
        self.assertEqual(s, 5 * 1 * 3 * 3 / 1)  # clamped to 1..5

    def test_missing_review(self):
        self.assertEqual(pipeline.score({"missing": True}), (0.0, ["missing"]))


class SelectTest(unittest.TestCase):
    def test_returns_k_and_skips_failed(self):
        cands = filler(15) + [cand("Generic but high scoring?", s=999, failed=["generic"])]
        chosen = pipeline.select(cands, GRAPH)
        self.assertEqual(len(chosen), pipeline.K)
        self.assertTrue(all(not c["failed"] for c in chosen))

    def test_coverage_of_uncertainties(self):
        cands = filler(15, s=50) + [cand("Low score on u3 runway question?", target="u3", s=2.0)]
        chosen = pipeline.select(cands, GRAPH)
        self.assertIn("u3", [c["target"] for c in chosen])

    def test_coverage_requires_impact(self):
        cands = filler(15, s=50) + [cand("Low impact u3 question?", target="u3", impact=2, s=2.0)]
        chosen = pipeline.select(cands, GRAPH)
        self.assertNotIn("u3", [c["target"] for c in chosen])

    def test_close_operator_included(self):
        cands = filler(15, s=50) + [cand("What does waiting a month cost you?", op="close", s=1.0)]
        chosen = pipeline.select(cands, GRAPH)
        self.assertIn("close", [c["operator"] for c in chosen])

    def test_near_duplicates_are_not_both_chosen(self):
        dup = "How long is the startup's remaining runway before the next funding round?"
        cands = [cand(dup, s=100), cand(dup + " ", s=99)] + filler(12, s=40)
        chosen = pipeline.select(cands, GRAPH)
        self.assertEqual(sum(c["question"].strip() == dup for c in chosen), 1)

    def test_top_up_never_uses_generic_or_answered(self):
        presupposing = ["Since the landlord refused, where will you charge?",
                        "Given the layoffs, who would replace the lead?",
                        "Because the contract expired, what penalty applies?"]
        cands = filler(4) + [cand(f"Generic {i}?", failed=["generic"]) for i in range(5)] + \
                [cand(q, failed=["presupposes"], s=3) for q in presupposing]
        chosen = pipeline.select(cands, GRAPH)
        self.assertEqual(len(chosen), 7)
        self.assertFalse(any("generic" in c["failed"] for c in chosen))
        self.assertEqual(sum(c["picked_by"] == "top_up" for c in chosen), 3)

    def test_sorted_by_score(self):
        chosen = pipeline.select(filler(15), GRAPH)
        scores = [c["S"] for c in chosen]
        self.assertEqual(scores, sorted(scores, reverse=True))


class MockRunTest(unittest.TestCase):
    def test_full_mock_run(self):
        case = load_cases(Path(__file__).resolve().parent.parent / "cases" / "seed.json")[0]
        questions, trace = pipeline.run(case, pipeline.mock_call(case))
        self.assertEqual(len(questions), pipeline.K)
        self.assertEqual(trace["n_candidates"], len(pipeline.OPERATORS) * 4)
        self.assertEqual(len(trace["chosen"]), pipeline.K)


if __name__ == "__main__":
    unittest.main()
