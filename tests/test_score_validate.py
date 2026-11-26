"""Tests for @k scoring and the v1 case rules. Run: python3 -m unittest discover tests"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import common  # noqa: E402
import score  # noqa: E402
import validate_cases  # noqa: E402

CASE = {"hidden_facts": [{"id": "c1", "type": "crux"}, {"id": "c2", "type": "crux"},
                         {"id": "t1", "type": "twin"}, {"id": "t2", "type": "twin"}]}


def judged(reveals_per_q):
    return {"rows": [{"q": i + 1, "reveals": r, "generic": False} for i, r in enumerate(reveals_per_q)]}


class ScoreAtKTest(unittest.TestCase):
    def test_at_k_uses_rank_order(self):
        rows = [[], ["t1"], [], ["c1"], [], [], [], [], ["c2"], []]
        s = score.score_run(judged(rows), CASE)
        self.assertEqual(s["crux@3"], 0.0)
        self.assertEqual(s["twin@3"], 0.5)
        self.assertEqual(s["disc@3"], -0.5)
        self.assertEqual(s["crux@5"], 0.5)
        self.assertEqual(s["crux@10"], 1.0)
        self.assertEqual(s["rr"], 1 / 4)

    def test_v0_names_still_present(self):
        s = score.score_run(judged([["c1", "c2"]] + [[]] * 9), CASE)
        self.assertEqual(s["crux_recall"], 1.0)
        self.assertEqual(s["discrimination"], 1.0)

    def test_fewer_than_k_questions(self):
        s = score.score_run(judged([["c1"]]), CASE)
        self.assertEqual(s["crux@10"], 0.5)


def v1_case(**overrides):
    case = {
        "id": "x", "category": "career", "source": "synthetic", "benchmark": "v1", "decision": "d?",
        "options": [{"id": "A", "label": "a"}, {"id": "B", "label": "b"}], "goal": "g",
        "visible_context": "ctx", "lean_without_hidden": "A", "_path": "cases/v1/x.json",
        "hidden_facts": [
            {"id": "c1", "type": "crux", "favors": "B", "text": "The pilot customer measures success differently.",
             "how_to_learn": "Ask the customer's ops lead.", "why": "w"},
            {"id": "t1", "type": "twin", "twin_of": "c1", "text": "The pilot customer uses a different dashboard.",
             "why": "Does not change value."},
        ],
    }
    case.update(overrides)
    return case


class V1RulesTest(unittest.TestCase):
    def test_valid_v1_case(self):
        self.assertEqual(validate_cases.check(v1_case()), [])

    def test_crux_needs_how_to_learn(self):
        c = v1_case()
        del c["hidden_facts"][0]["how_to_learn"]
        self.assertTrue(any("how_to_learn" in e for e in validate_cases.check(c)))

    def test_model_adapted_must_be_private(self):
        errs = validate_cases.check(v1_case(source="model-adapted"))
        self.assertTrue(any("cases/private" in e for e in errs))
        self.assertEqual(validate_cases.check(v1_case(source="model-adapted", _path="cases/private/x.json")), [])

    def test_checklist_word_is_only_a_hint(self):
        c = v1_case()
        c["hidden_facts"][0]["text"] = "The contract has an exit clause."
        errs = validate_cases.check(c)
        self.assertTrue(errs and all(e.startswith("hint:") for e in errs))

    def test_v0_cases_skip_v1_rules(self):
        c = v1_case()
        del c["benchmark"]
        del c["hidden_facts"][0]["how_to_learn"]
        self.assertEqual(validate_cases.check(c), [])


class PrivateRoutingTest(unittest.TestCase):
    def test_private_cases_write_to_ignored_roots(self):
        priv = {"_path": "/x/cases/private/a.json"}
        pub = {"_path": "/x/cases/v1/a.json"}
        self.assertEqual(common.run_root(priv).name, "runs_private")
        self.assertEqual(common.judgment_root(priv).name, "judgments_private")
        self.assertEqual(common.run_root(pub).name, "runs")
        ignored = (common.ROOT / ".gitignore").read_text()
        self.assertIn("runs_private/", ignored)
        self.assertIn("judgments_private/", ignored)


if __name__ == "__main__":
    unittest.main()
