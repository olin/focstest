import logging
import os
import re
import subprocess
import sys
from urllib.parse import urlparse

from bs4 import BeautifulSoup
import requests


logging.basicConfig(level=logging.DEBUG)

FILE = 'homework1.ml'
URL = "http://rpucella.net/courses/focs-fa18/homeworks/h1.html"

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
        logging.error('Code block selector {!r} returned no matches'.format(
            CODE_BLOCK_SELECTOR))
    return [block.get_text() for block in code_blocks]


def get_tests(text):
    """Parse Ocaml tests from text.

    :returns: list of test tuples with format (input, expected output)
    """
    tests = TEST_COMP.findall(text)
    if len(tests) == 0:
        logging.error('Test/response pattern {!r} returned no matches'.format(
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
            logging.warning('Ocaml process timed out: {} {}'.format(outs, errs))
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
        logging.error("Expected 2 matches, got {}".format(len(matches)))
    elif len(matches) != 2 and file is None:
        logging.error("Expected 1 , got {}".format(len(matches)))
    else:
        output = matches[-2]  # don't use empty final match from #quit;;
        return (output == expected_out, output)


if __name__ == "__main__":
    # get and cache webpage
    CACHE_DIR = 'focstest-cache/'
    if not os.path.exists(CACHE_DIR):
        os.makedirs(CACHE_DIR)
        logging.info('Created cache directory at {!r}'.format(CACHE_DIR))
    page_name = os.path.basename(urlparse(URL).path)  # get page name from url
    html_filepath = os.path.join(CACHE_DIR, page_name)  # local filepath

    # get webpage if cached version doesn't already exist
    if not os.path.isfile(html_filepath):
        response = requests.get(URL)
        if response.status_code != 200:  # break if webpage can't be fetched
            logging.critical("Unable to fetch url {}: Status {}: {}".format(
                URL,
                response.status_code,
                response.reason))
            sys.exit(1)
        # write to file and continue
        html = response.text
        with open(html_filepath, 'w') as htmlcache:
            htmlcache.write(html)
            logging.debug("Saved {!r} to cache at {!r}".format(URL, html_filepath))
    else:
        logging.debug("Found cached version at {!r}".format(html_filepath))
        with open(html_filepath, 'r') as htmlcache:
            html = htmlcache.read()

    # parse for code blocks
    # TODO: get titles/descriptions from code blocks
    blocks = get_blocks(html)
    # parse code blocks for tests
    test_suites = [get_tests(block) for block in blocks]
    logging.info("Found {} test suites and {} tests total".format(
        len(test_suites),
        sum([len(suite) for suite in test_suites])))
    # TODO: save tests to file

    # run tests
    # TODO: check for "not implemented" error
    for suite in test_suites:
        for test, expected_output in suite:
            result, output = run_test(test, expected_output, file=FILE)
            if result is False:
                print("Test failed.\n\tINPUT: {!r}\n\tEXPECTED: {!r}\n\tOUTPUT: {!r}".format(
                    test,
                    expected_output,
                    output))
