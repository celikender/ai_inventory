import unittest

from ai.parsing import extract_json_array


class ExtractJsonArrayTests(unittest.TestCase):
    def test_extracts_array_from_markdown_response(self):
        response = 'Result:\n```json\n[{"bin_code":"A-01","qty":2}]\n```'
        self.assertEqual(
            extract_json_array(response),
            '[{"bin_code":"A-01","qty":2}]',
        )

    def test_ignores_brackets_inside_strings(self):
        response = 'prefix [{"description":"box [left]","qty":1}] suffix'
        self.assertEqual(
            extract_json_array(response),
            '[{"description":"box [left]","qty":1}]',
        )

    def test_returns_empty_string_for_incomplete_array(self):
        self.assertEqual(extract_json_array('[{"qty":1}'), "")


if __name__ == "__main__":
    unittest.main()
