"""Tests for focstest.py, from the creators of focstest.py"""
import unittest
import doctest

import focstest
from focstest import equivalent, strip_whitespace, normalize_whitespace


def load_tests(loader, tests, ignore):
    # run doctests from within unittest
    # see: <https://docs.python.org/3/library/doctest.html#unittest-api>
    tests.addTests(doctest.DocTestSuite(focstest))
    return tests


class TestTextNormalization(unittest.TestCase):
    """Test text normalization techniques with real-world examples."""

    def test_normalize_whitespace(self):
        # add examples here in the format (expected output, generated output)
        cases = [
            ('- : int list =\n[19; 58; 29; 88; 44; 22; 11; 34; 17; 52; 26; 13; 40; 20; 10; 5; 16; 8; 4; 2; 1]',
            '- : int list =\n[19; 58; 29; 88; 44; 22; 11; 34; 17; 52; 26; 13; 40; 20; 10; 5; 16; 8; 4; 2;\n 1]\n')
        ]
        for expected, generated in cases:
            self.assertEqual(
                normalize_whitespace(expected),
                normalize_whitespace(generated))


if __name__ == '__main__':
    unittest.main()
