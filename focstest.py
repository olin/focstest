#!/usr/bin/env python3
import argparse
import logging
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests


logger = logging.getLogger(name=__name__)  # create logger in order to change level later
logger.setLevel(logging.DEBUG)
logger.addHandler(logging.StreamHandler())


# selectors for parsing html
CODE_BLOCK_SELECTOR = 'div.code pre'  # css selector to get code blocks

# regex patterns for parsing text
TEST_PATTERN = "^# (.+;;)\n(.+)\n"  # pattern to get input and output
OCAML_PATTERN = "^# (.*)$"  # pattern to grab output of lines

# compile regexes ahead of time
OCAML_COMP = re.compile(OCAML_PATTERN, re.MULTILINE)
TEST_COMP = re.compile(TEST_PATTERN, re.MULTILINE)


def get_blocks(html):
    """Parse code blocks from html.

    :param html: html text
    :returns: list of strings of code blocks
    """
    page = BeautifulSoup(html, 'html.parser')
    code_blocks = page.select(CODE_BLOCK_SELECTOR)
    if len(code_blocks) == 0:
        logger.error('Code block selector {!r} returned no matches'.format(
            CODE_BLOCK_SELECTOR))
    return [block.get_text() for block in code_blocks]


def get_tests(text):
    """Parse Ocaml tests from text.

    :returns: list of test tuples with format (input, expected output)
    """
    tests = TEST_COMP.findall(text)
    if len(tests) == 0:
        logger.error('Test/response pattern {!r} returned no matches'.format(
            TEST_PATTERN))
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


def run_test(code: str, expected_out: str, file: str = None):
    """Check the output of a line of code against an expected value.

    :param code: code to run
    :param expected_out: the expected output of the code
    :param file: the path to a file to load in the interpreter before running
        the code
    :returns: tuple of a boolean indicating the results of the test and the
        output of the command
    """
    if file is not None:
        command = '#use "{}";;\n'.format(file) + code
    else:
        command = code
    command += "\n#quit;;"
    outs, errs = _run_ocaml_code(command)
    matches = OCAML_COMP.findall(outs)
    if len(matches) != 3 and file is not None:
        logger.error("Expected 2 matches, got {}".format(len(matches)))
    elif len(matches) != 2 and file is None:
        logger.error("Expected 1 , got {}".format(len(matches)))
    else:
        output = matches[-2]  # don't use empty final match from #quit;;
        return (output == expected_out, output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Run ocaml "doctests".')
    input_types = parser.add_mutually_exclusive_group(required=True)
    input_types.add_argument('-u', '--url', type=str,
                             help='a url to scrape tests from')
    # input_types.add_argument('-f', '--file', type=str,
    #                          help='a file to load tests from')
    parser.add_argument('ocaml-file', type=str,
                        help='the ocaml file to test against')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='increase test output verbosity')
    parser.add_argument('--log-level', choices=['debug', 'info', 'warning'],
                        help='the program log level')
    parser.add_argument('-uc', '--update-cache', action='store_true',
                        help='update cached files')
    args = parser.parse_args()
    if args.log_level:
        numeric_level = getattr(logging, args.log_level.upper(), None)
        logger.setLevel(numeric_level)

    URL = args.url
    FILE = getattr(args, 'ocaml-file')

    # get and cache webpage
    CACHE_DIR = 'focstest-cache/'
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        logger.info('Created cache directory at {!r}'.format(CACHE_DIR))
    page_name = os.path.basename(urlparse(URL).path)  # get page name from url
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
        logger.debug("Using cached version at {!r}".format(html_filepath))
        with open(html_filepath, 'r') as htmlcache:
            html = htmlcache.read()

    # parse for code blocks
    # TODO: get titles/descriptions from code blocks
    blocks = get_blocks(html)
    # parse code blocks for tests
    test_suites = [get_tests(block) for block in blocks]
    num_tests = sum([len(suite) for suite in test_suites])
    logger.info("Found {} test suites and {} tests total".format(
        len(test_suites),
        num_tests))
    # TODO: save tests to file

    # run tests
    if not os.path.exists(FILE):
        logger.critical("File {} does not exist".format(FILE))
        sys.exit(1)
    num_failed = 0
    num_skipped = 0
    for i, suite in enumerate(test_suites):
        if args.verbose:
            print('Testing suite {} of {}.'.format(i+1, len(test_suites)))
        for j, (test, expected_output) in enumerate(suite):
            result, output = run_test(test, expected_output, file=FILE)
            if result is False:
                if output.lower() == 'exception: failure "not implemented".':
                    num_skipped += len(suite) - (j + 1)
                    print('Skipped suite {}'.format(i + 1))
                    break
                num_failed += 1
                print("Test failed.\n  INPUT:\t{!r}\n  EXPECTED:\t{!r}\n  OUTPUT:\t{!r}".format(
                    test,
                    expected_output,
                    output))
    print('Finished testing.')
    print('{} of {} tests failed.'.format(num_failed, num_tests))
    print('{} tests skipped.'.format(num_skipped))
