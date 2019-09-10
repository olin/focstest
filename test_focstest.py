import unittest

from focstest import equivalent, strip_whitespace, normalize_whitespace


class TestTextNormalization(unittest.TestCase):
    """Test text normalization techniques with real-world examples."""

    def test_normalize_whitespace(self):
        cases = [
            ('- : int list =\n[19; 58; 29; 88; 44; 22; 11; 34; 17; 52; 26; 13; 40; 20; 10; 5; 16; 8; 4  2; 1]',
            '- : int list =\n[19; 58; 29; 88; 44; 22; 11; 34; 17; 52; 26; 13; 40; 20; 10; 5; 16; 8; 4; 2;\n 1]\n')
        ]
        for expected, given in cases:
            self.assertEqual(
                normalize_whitespace(expected),
                normalize_whitespace(given))


if __name__ == '__main__':
    unittest.main()
