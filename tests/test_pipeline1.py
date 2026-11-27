import unittest

import pipeline1
from common import load_cases, ROOT


class Pipeline1Test(unittest.TestCase):
    def setUp(self):
        self.case = load_cases(ROOT / "cases/seed.json")[0]

    def test_mock_run_returns_ten_questions(self):
        qs, trace = pipeline1.run(self.case, pipeline1.mock_call(self.case))
        self.assertEqual(len(qs), pipeline1.K)
        self.assertEqual(len(trace["questions"]), pipeline1.K)
        self.assertIn("beliefs", trace["map"])

    def test_string_questions_accepted(self):
        def call(prompt, mt):
            if "Do not write questions yet" in prompt:
                return '{"lean": {}, "premortem": [], "beliefs": [{"id": "b1"}]}'
            return '{"questions": ["first?", " ", "second?"]}'
        qs, _ = pipeline1.run(self.case, call)
        self.assertEqual(qs, ["first?", "second?"])

    def test_empty_map_rejected(self):
        with self.assertRaises(ValueError):
            pipeline1.run(self.case, lambda p, mt: '{"beliefs": []}')

    def test_prompts_have_placeholders(self):
        from common import load_prompt
        self.assertIn("{case_brief}", load_prompt("pipeline1/map"))
        self.assertIn("{map}", load_prompt("pipeline1/ask"))


if __name__ == "__main__":
    unittest.main()
