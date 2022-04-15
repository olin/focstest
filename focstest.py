#!/usr/bin/env python3
import argparse
import logging
import os
from pkg_resources import get_distribution, DistributionNotFound
import re
import subprocess
import sys
import tempfile
import urllib.parse

from bs4 import BeautifulSoup
import requests
from termcolor import colored


logger = logging.getLogger(name=__name__)  # create logger in order to change level later
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


# get version from setuptools installation
try:
    __version__ = get_distribution('focstest').version
except DistributionNotFound:
    # not installed
    # TODO: try git directly
    __version__ = 'unknown, try `git describe`'


# default url matching
BASE_URL = "http://rpucella.net/courses/focs-fa20/homeworks/"  # default website and path to fetch from
OCAML_FILE_PATTERN = r"homework(\d{1,2}).ml"  # pattern to extract homework number from the user-given ocaml file
HTML_FILE_TEMPLATE = "homework{}.html"  # template to build the html filename given a homework number

# selectors for parsing html
CODE_BLOCK_SELECTOR = 'pre code'  # css selector to get code blocks

# regex patterns for parsing text
TEST_PATTERN = r"^(.+;;)\n(.*)$"  # pattern to get input and output
OCAML_PATTERN = r"^(.*)"  # pattern to grab output of lines

# compile regexes ahead of time
OCAML_FILE_COMP = re.compile(OCAML_FILE_PATTERN)
TEST_COMP = re.compile(TEST_PATTERN, re.MULTILINE + re.DOTALL)
OCAML_COMP = re.compile(OCAML_PATTERN, re.MULTILINE + re.DOTALL)


def get_blocks(html):
    """Parse code blocks from html.

    :param html: html text
    :returns: list of strings of code blocks
    """
    page = BeautifulSoup(html, 'html.parser')
    code_blocks = page.select(CODE_BLOCK_SELECTOR)
    if len(code_blocks) == 0:
        logger.error('Code block selector {!r} returned no matches'.format(CODE_BLOCK_SELECTOR))
    return [block.get_text() for block in code_blocks]


def get_tests(text):
    """Parse Ocaml tests from text.

    :returns: list of test tuples with format (input, expected, output)
    """
    def get_test(text):
        return TEST_COMP.match(text)
    test_strs = text.split('# ')[1:]
    tests = []
    for test_str in test_strs:
        test = get_test(test_str)
        if test is None:
            logger.error(
                'Test/response pattern {!r} returned no matches from string {!r}'.format(TEST_PATTERN, test_str))
        else:
            tests.append((test.group(1).strip(), test.group(2).strip()))
    return tests


def _run_ocaml_code(code):
    """Run a line of ocaml with the REPL and capture the output.

    :param code: string of code to run
    :returns: tuple of strings with format (output, errors)
    """
    with subprocess.Popen(['ocaml'],
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          universal_newlines=True) as p:
        try:
            outs, errs = p.communicate(code, timeout=5)
        except subprocess.TimeoutExpired:
            p.kill()
            outs, errs = p.communicate()
            logger.warning('Ocaml process timed out: {} {}'.format(outs, errs))
    return (outs, errs)


# text normalization techniques

def equivalent(text):
    return text


def strip_whitespace(text):
    return text.strip()


def normalize_whitespace(text):
    """Replace instances of whitespace with ' '.

    >>> normalize_whitespace(' a\\n b c \td\\n')
    'a b c d'
    """
    return ' '.join(text.split())


def run_test(code: str, expected_out: str, file: str = None):
    """Check the output of a line of code against an expected value.

    :param code: code to run
    :param expected_out: the expected output of the code
    :param file: the path to a file to load in the interpreter before running
        the code
    :returns: tuple of a boolean indicating the results of the test and the
        output of the command
    """

    steps = [
        equivalent,
        strip_whitespace,
        normalize_whitespace
    ]
    if file is not None:
        command = '#use "{}";;\n'.format(file) + code
    else:
        command = code
    command += "\n#quit;;"
    outs, errs = _run_ocaml_code(command)
    matches = outs.split('# ')[1:]  # TODO: check if this should change based on the presence of a file
    if len(matches) != 3 and file is not None:
        logger.warning("Unable to parse ocaml output, expected 2 matches, got {}".format(len(matches)))
    elif len(matches) != 2 and file is None:
        logger.error("Unable to parse ocaml output, expected 1 match, got {} ".format(len(matches)))
    else:
        # compare strings
        output = matches[-2]  # don't use empty final match from #quit;;
        for step in steps:
            function = code.split()[0]  # grab the first word of the command (probably the function name)
            method = step.__name__
            result = step(output) == step(expected_out)
            if result is True:
                logger.debug('Test {!r} passed with method {!r}'.format(function, method))
                break
        return (result, output, method)


def get_test_str(test_input: str, test_output: str, expected: str,
                 use_color=True, indent='  '):
    """Create an explanatory str about a test for printing."""
    def format_info(kind, value):
        return indent+kind.upper()+':\t'+repr(value)
    lines = [
        format_info('input', test_input),
        format_info('expected', expected),
        format_info('output', test_output),
    ]
    return '\n'.join(lines)


def infer_url(filepath):
    """Infer a url based on a filename.

    Basically connects 'homeworkX.ml' -> 'http://.../hX.html'

    Returns: False if the filename could not be named

    >>> infer_url('foo/bar.ml')
    False

    >>> infer_url('foo/bar/homework1.ml')
    'http://rpucella.net/courses/focs-fa20/homeworks/homework1.html'
    """
    filename = os.path.basename(filepath)
    match = OCAML_FILE_COMP.match(filename)
    if not match:
        return False
    hw_num = match.group(1)
    url = urllib.parse.urljoin(BASE_URL, HTML_FILE_TEMPLATE.format(hw_num))
    return url


def main():
    parser = argparse.ArgumentParser(
        description='Run ocaml "doctests".',
        epilog='Submit bugs to <https://github.com/olin/focstest/issues/>.')
    parser.add_argument('--version', action='version', version=__version__)
    input_types = parser.add_mutually_exclusive_group(required=False)
    input_types.add_argument('--url', type=str,
                             help='a url to scrape tests from (usually automagically guessed from ocaml-file)')
    parser.add_argument('ocaml-file', type=str,
                        help='the ocaml file to test against')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='increase test output verbosity')
    parser.add_argument('-uc', '--update-cache', action='store_true',
                        help='update cached files')
    test_selection = parser.add_mutually_exclusive_group(required=False)
    test_selection.add_argument('-u', '--use-suites', metavar='N', type=int, nargs='*',
                                help='test suites to use exclusively, indexed from 1')
    test_selection.add_argument('-s', '--skip-suites', metavar='N', type=int, nargs='*',
                                help='test suites to skip, indexed from 1')
    args = parser.parse_args()

    # check environment var for logging level
    log_level = os.getenv('LOG_LEVEL')
    if log_level is not None:
        log_level = log_level.upper()
        try:
            numeric_level = getattr(logging, os.getenv('LOG_LEVEL'))
        except AttributeError as e:
            logging.warning("Found 'LOG_LEVEL' env var, but was unable to parse: {}".format(e))
        else:
            logger.setLevel(numeric_level)
            logger.debug('Set logging level to {!r} ({}) from env var'.format(log_level, numeric_level))

    URL = args.url
    FILE = getattr(args, 'ocaml-file')

    if not args.url:
        url_guess = infer_url(FILE)
        if not url_guess:  # break if filename can't be matched
            logger.critical((
                'Could not infer url from filename {!r}. '
                'Try passing a url manually with the `--url` flag.').format(FILE))
            sys.exit(1)
        else:
            URL = url_guess

    # get and cache webpage
    temp_dir = tempfile.gettempdir()  # most likely /tmp/ on Linux
    CACHE_DIR = os.path.join(temp_dir, 'focstest-cache')
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        logger.info('Created cache directory at {!r}'.format(CACHE_DIR))
    page_name = os.path.basename(urllib.parse.urlparse(URL).path)  # get page name from url
    html_filepath = os.path.join(CACHE_DIR, page_name)  # local filepath

    # get webpage if cached version doesn't already exist
    if not os.path.isfile(html_filepath) or args.update_cache:
        response = requests.get(URL)
        if response.status_code != 200:  # break if webpage can't be fetched
            logger.critical("Unable to fetch url {}: Status {}: {}".format(
                URL,
                response.status_code,
                response.reason))
            sys.exit(1)
        # write to file and continue
        html = response.text
        with open(html_filepath, 'w') as htmlcache:
            htmlcache.write(html)
            logger.debug("Saved {!r} to cache at {!r}".format(URL, html_filepath))
    else:
        logger.debug("Using cached version of page at {!r}".format(html_filepath))
        with open(html_filepath, 'r') as htmlcache:
            html = htmlcache.read()

    # parse for code blocks
    # TODO: get titles/descriptions from code blocks
    blocks = get_blocks(html)
    # parse code blocks for tests
    # list of suites and indices (starting at 1) (skipping empty suites)
    test_suites = list(enumerate(filter(None, (get_tests(b) for b in blocks)), 1))
    num_tests = sum([len(suite) for j, suite in test_suites])
    logger.info("Found {} test suites and {} tests total".format(
        len(test_suites), num_tests))
    # TODO: save tests to file

    # run tests
    if not os.path.exists(FILE):
        logger.critical("File {} does not exist".format(FILE))
        sys.exit(1)
    num_failed = 0
    num_skipped = 0

    # select test suites based on args
    # i is indexed from 0, j is indexed from 1
    if args.use_suites:
        skipped_suites = [suite for j, suite in test_suites if j not in args.use_suites]
        for suite in skipped_suites:
            num_skipped += len(suite)
        test_suites = [test_suites[j-1] for j in args.use_suites]
    elif args.skip_suites:
        skipped_suites = [test_suites[j-1][1] for j in args.skip_suites]
        for suite in skipped_suites:
            num_skipped += len(suite)
        test_suites = [(j, suite) for j, suite in test_suites if j not in args.skip_suites]

    print('Starting tests')
    for j, suite in test_suites:
        if args.verbose:
            print('Testing suite {}'.format(j))
        for k, (test, expected_output) in enumerate(suite):
            res = run_test(test, expected_output, file=FILE)
            header_temp = ' test {} of {} in suite {}'.format(k+1, len(suite), j)
            if res is None:  # skip unparsable texts
                print(colored('Skipped'+header_temp+': Unable to parse output', 'yellow'))
                continue
            else:
                result, output, method = res
            test_str = get_test_str(test, output, expected_output)
            function = test.split()[0]
            if result is False:
                if output.strip().lower() == 'exception: failure "not implemented".':
                    if args.verbose:
                        print(colored('Unimplemented'+header_temp, 'yellow'))
                        print(test_str)
                    num_skipped += len(suite) - (k + 1)
                    print(colored('Skipped unimplemented suite {} {!r}'.format(j, function), 'yellow'))
                    break
                num_failed += 1
                print(colored('Failed'+header_temp, 'red'))
                print(test_str)
            elif args.verbose:
                header = 'Passed'+header_temp
                if method not in ['equivalent', 'strip_whitespace']:
                    header += ' w/ method '+method
                print(colored(header, 'green'))
                print(test_str)
        if args.verbose:
            print('-'*80)
    print('Finished testing')
    fail_summary = '{} of {} tests failed'.format(num_failed, num_tests - num_skipped)
    if num_failed > 0:
        print(colored(fail_summary, 'red'))
    else:
        print(colored(fail_summary, 'green'))
    skip_summary = '{} tests skipped'.format(num_skipped)
    if num_skipped > 0:
        print(colored(skip_summary, 'yellow'))
    else:
        print(skip_summary)


if __name__ == "__main__":
    main()
