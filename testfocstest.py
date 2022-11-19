"""Tests for focstest.py, from the creators of focstest.py"""
import unittest
import doctest
import shutil
import subprocess

import focstest
from focstest import (
    parse_ocaml_error,
    parse_tests,
    normalize_whitespace,
    run_ocaml_code,
    _exec_ocaml_interpreter,
    OcamlError,
    OcamlException,
    UnimplementedException,
)


def load_tests(loader, tests, ignore):
    # run doctests from within unittest
    # see: <https://docs.python.org/3/library/doctest.html#unittest-api>
    tests.addTests(doctest.DocTestSuite(focstest))
    return tests


class TestTestParsing(unittest.TestCase):

    FUNKY_TEST = text = '\n'.join((
        '# run tm_q2_not "0#1";; ',
        'start  [>] 0  #  1',
        '- : bool = true',
        '# run tm_q2_not "000#111";;',
        'start  [>] 0  0  0  #  1  1  1',
        '- : bool = true',
        '',
    ))

    def test_funky_tests(self):
        res = parse_tests(self.FUNKY_TEST)
        self.assertEqual(2, len(res))
        self.assertEqual(
            ('run tm_q2_not "0#1";;', 'start  [>] 0  #  1\n- : bool = true\n'),
            res[0]
        )
        self.assertEqual(
            ('run tm_q2_not "000#111";;', 'start  [>] 0  0  0  #  1  1  1\n- : bool = true\n'),
            res[1]
        )


class TestTextNormalization(unittest.TestCase):
    """Test text normalization techniques with real-world examples."""

    def test_normalize_whitespace(self):
        cases = [
            ('list broken over multiple lines',
             '- : int list =\n[19; 58; 29; 88; 44; 22; 11; 34; 17; 52; 26; 13; 40; 20; 10; 5; 16; 8; 4; 2; 1]',
             '- : int list =\n[19; 58; 29; 88; 44; 22; 11; 34; 17; 52; 26; 13; 40; 20; 10; 5; 16; 8; 4; 2;\n 1]\n')
        ]
        for desc, expected, generated in cases:
            with self.subTest(desc):
                self.assertEqual(
                    normalize_whitespace(expected),
                    normalize_whitespace(generated))


class TestOcamlReplParsing(unittest.TestCase):
    error = \
        "Characters 0-9:\n" \
        "failworth \"Not implemented\"\n" \
        "^^^^^^^^^\n" \
        "Error: Unbound value failworth\n" \
        "Hint: Did you mean failwith?"
    exception = "Exception: Failure \"Not Implemented\"."
    printed = "foo\nbar\n- : unit = ()"
    unknown = "foo\nbar"

    def test_is_error(self):
        are_errors = (self.error, self.exception)
        not_errors = (self.printed, self.unknown)
        for case in are_errors:
            self.assertIsNotNone(parse_ocaml_error(case))
        for case in not_errors:
            self.assertIsNone(parse_ocaml_error(case))


@unittest.skipIf(shutil.which('ocaml') is None, 'ocaml binary not available')
class TestRunOcaml(unittest.TestCase):
    """Test return values from running Ocaml.

    Note: these require `ocaml` to be installed on the system.
    """

    ERROR_EXPRESSIONS = [
        ('[1;2;;',         OcamlError, 'incomplete expression (syntax)'),
        ("'str';;",        OcamlError, 'string with single quotes (syntax)'),
        ("a;;",            OcamlError, 'unbound value'),
        ('failwith "a";;', OcamlException, 'Failure exception'),
        ('1 / 0;;',        OcamlException, 'Division_by_zero exception'),
        ('assert false;;', OcamlException, 'Assert_failure exception'),
        # and now a variety of user-defined unimplemented exceptions
        *(('failwith "{}";;'.format(s), UnimplementedException, s) for s in
            ('Unimplemented', 'unimplemented', 'Not implemented', 'Not Implemented')),
    ]

    def test_invalid_ocaml_code(self):
        for code, error, desc in self.ERROR_EXPRESSIONS:
            with self.subTest(desc):
                output = run_ocaml_code(code)
                maybe_error = parse_ocaml_error(output)
                self.assertIsInstance(maybe_error, error)

    def test_incomplete_statement(self):
        with self.assertRaises(ValueError):
            run_ocaml_code('[1;2]')

    def test_valid_ocaml(self):
        for code, output in (
            ('1;;',     '- : int = 1'),
            ('"foo";;', '- : string = "foo"'),
            ('[1;2];;', '- : int list = [1; 2]'),
        ):
            self.assertEqual(output, run_ocaml_code(code))

    def test_timeout(self):
        with self.assertRaises(subprocess.TimeoutExpired):
            _exec_ocaml_interpreter('#load "unix.cma";;\nUnix.sleep 5;;', timeout=0.3)


if __name__ == '__main__':
    unittest.main()
