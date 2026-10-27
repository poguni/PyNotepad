import unittest

from pynotepad import search as S

TEXT = "Cat cat catalog CAT"


class FindTests(unittest.TestCase):
    def test_down_case_insensitive(self):
        self.assertEqual(S.find(TEXT, "cat", 1), (4, 7))

    def test_match_case(self):
        self.assertEqual(S.find(TEXT, "CAT", 0, match_case=True), (16, 19))

    def test_whole_word(self):
        self.assertIsNone(S.find("catalog", "cat", 0, whole_word=True))
        self.assertEqual(S.find(TEXT, "cat", 5, whole_word=True), (16, 19))

    def test_up(self):
        self.assertEqual(S.find(TEXT, "cat", 7, down=False), (4, 7))

    def test_wrap_around(self):
        self.assertIsNone(S.find(TEXT, "Cat", 17, match_case=True))
        self.assertEqual(S.find(TEXT, "Cat", 17, match_case=True, wrap_around=True), (0, 3))
        self.assertEqual(S.find(TEXT, "CAT", 2, down=False, match_case=True, wrap_around=True), (16, 19))

    def test_korean(self):
        self.assertEqual(S.find("가나다 나", "나", 2), (4, 5))

    def test_replace_all(self):
        self.assertEqual(S.replace_all(TEXT, "cat", "dog", whole_word=True), ("dog dog catalog dog", 3))
        self.assertEqual(S.replace_all("a.b", ".", "-"), ("a-b", 1))  # regex characters are literal
        self.assertEqual(S.replace_all("x", "x", r"\1"), (r"\1", 1))  # replacement is literal too


if __name__ == "__main__":
    unittest.main()
