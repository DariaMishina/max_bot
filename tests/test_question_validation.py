import unittest

from main.question_validation import InvalidQuestionError, validate_question_text


class QuestionValidationTests(unittest.TestCase):
    def test_rejects_non_meaningful_input(self):
        for value in ("", "   ", "!", "???", "🔮", "123", "а", "аааа", "xxx", "\u200b!"):
            with self.subTest(value=value), self.assertRaises(InvalidQuestionError):
                validate_question_text(value)

    def test_accepts_questions_and_short_topics(self):
        for value in ("Работа", "Любовь?", "Что дальше?", "Стоит ли менять работу"):
            with self.subTest(value=value):
                self.assertEqual(validate_question_text(value), value)

    def test_normalizes_unicode_whitespace_and_controls(self):
        self.assertEqual(validate_question_text("  Что\n\u200b дальше?  "), "Что дальше?")

    def test_checks_length_after_normalization(self):
        with self.assertRaises(InvalidQuestionError):
            validate_question_text("аб" * 501)


if __name__ == "__main__":
    unittest.main()
