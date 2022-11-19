#!/usr/bin/env python3
"""focstest: CLI test runner for Olin College's Foundations of Computer Science class (FoCS).

Focstest automagically finds the "doctests" from homework assignments and runs them for you.

See README.md or run `focstest -h` for help.
"""
# TABLE OF CONTENTS
# 1. Global configuration
# 2. Shared Types
# 3. High-level CLI
# 4. Errors
# 5. Test Fetching
# 6. Test Parsing
# 7. Test Running
# 8. Utilities

import argparse
from dataclasses import dataclass
from functools import lru_cache
import itertools
import logging
import os
from pathlib import Path, PurePath
from pkg_resources import get_distribution, DistributionNotFound
import re
import subprocess
import sys
import tempfile
import time
import urllib.parse
from urllib.parse import urljoin, urlunparse, ParseResult as Url

import bs4
import requests
from termcolor import colored

from typing import Optional, List, Tuple, Iterable, NamedTuple, Union, TypeVar, Callable, Any, TextIO, Pattern, cast


#
# GLOBAL CONFIGURATION
#


logger = logging.getLogger(name=__name__)  # create logger in order to change level later
logger.setLevel(logging.INFO)
logger.addHandler(logging.StreamHandler())

# get version from setuptools installation
try:
    __version__ = get_distribution('focstest').version
except DistributionNotFound:
    # not installed
    # TODO: try git directly
    __version__ = 'unknown, try `git describe`'


CACHE_TIMEOUT = 1800  # time to keep using cached files, in seconds

# default url matching
BASE_URL = "https://rpucella.net/courses/focs-sp22/homeworks/"  # default website and path to fetch from
HTML_FILE_TEMPLATE = "{}/index.html"  # template string for the html filename given a homework number
OCAML_FILE_RE = re.compile(r"homework(\d{1,2}).ml")  # pattern to extract homework number from the user-given ocaml file

# css selectors for parsing html
# for info on supported selectors, see:
# - <https://www.crummy.com/software/BeautifulSoup/bs4/doc/#css-selectors>
# - <https://facelessuser.github.io/soupsieve/>
CODE_BLOCK_SELECTOR = ', '.join((
    # these are individual patterns (OR'd together w/ ',')
    # ideally, only add new selectors to keep it backwards compatible
    'div.code pre',  # Fall 2018
    'pre code',  # Fall 2019
))


#
# SHARED TYPES
#


T = TypeVar('T')
PathLike = Union[str, os.PathLike]
UrlLike = Union[str, Url]
Numeric = Union[int, float]


class FilePos(NamedTuple):
    """A (1-based) line and column pair in a piece of text."""
    line: int
    col: Optional[int]
    file: Optional[PathLike]

    def __str__(self) -> str:
        """Format as `[file:]line[:col]`"""
        s = ''
        if self.file:
            s += str(self.file)
            s += ':'
        s += str(self.line)
        if self.col:
            s += ':'
            s += str(self.col)
        return s


class Test(NamedTuple):
    """A parsed test case.

    Attributes:
        input: The input text for the OCaml repl, including the trailing `;;` but not the prompt's `#`.
        expected: The expected output of the OCaml repl. May contain linebreaks used for formatting.
    """
    input: str
    expected: str


class TestResult(NamedTuple):
    """The result of running a test.

    Attributes:
        success: Whether the test passed with any method of comparison.
        output: The unmodified output text from running the input expression in the OCaml repl.
        error: An error parsed from `output`, if any.
    """
    success: bool
    output: str
    error: Optional['OcamlError']


TestSuite = List[Test]


#
# HIGH-LEVEL CLI
#


def main() -> None:
    set_log_level_from_env()
    args = parse_args()

    try:
        focstest(args)
    except FocstestError as e:
        exception_handler(e)


@dataclass
class Args:
    """Typed representation of commandline arguments for focstest.

    See `parse_args` for the meaning of these attributes.
    """
    ocaml_file: PurePath
    url: Optional[Url]
    html_file: Optional[PurePath]
    use_suites: List[int]
    skip_suites: List[int]
    verbose: bool = False
    ignore_cache: bool = False


def focstest(args: Args) -> None:
    """Run focstest with a custom set of arguments.


    Raises:
        FocstestError: If an unrecoverable error is encountered.
    """
    html, source_file = get_html(args.ocaml_file,
                                 html_file=args.html_file,
                                 url=args.url,
                                 use_cache=(not args.ignore_cache))

    # parse code blocks for tests (skipping empty suites)
    test_suites = list(parse_html_tests(html, source_file))
    num_tests = sum([len(suite) for suite in test_suites])
    logger.info("Found %s test suites and %s tests total", len(test_suites), num_tests)
    # TODO: save parsed tests to file

    # select test suites based on args
    runner = PrintingTestRunner(test_suites,
                                args.ocaml_file,
                                verbose=args.verbose,
                                skip_unimplemented_suites=True)

    if args.use_suites:
        runner.skip_if(lambda i, _: i not in args.use_suites)
    elif args.skip_suites:
        runner.skip_if(lambda i, _: i in args.skip_suites)

    logger.debug('Starting tests')
    runner.run()
    logger.debug('Finished testing')


def set_log_level_from_env(name: str = 'LOG_LEVEL') -> None:
    LEVELS = ('DEBUG', 'INFO', 'WARN', 'ERROR')

    log_level = os.getenv(name)
    if log_level is None:
        return

    log_level = log_level.upper()

    if log_level not in LEVELS:
        logger.warning("Found %r env var, but log level was not one of %r: %r", name, LEVELS, log_level)
        return

    numeric_level = getattr(logging, log_level)
    logger.setLevel(numeric_level)
    logger.debug('Set logging level to %r (%s) from env var', log_level, numeric_level)


def parse_args(args: Optional[List[str]] = None) -> Args:
    """Parse commandline arguments.

    This function will exit() when handling certain flags like --help or --version, or parsing errors.
    See the `argparse` module for more information.

    Args:
        args: Manual arguments to parse. If None, uses sys.argv. Similar behavior to
            `argparse.ArgumentParser.parse_args`.
    """
    # validation functions

    def existing_file(p: str) -> Path:
        file = Path(p)
        if not file.exists():
            raise argparse.ArgumentTypeError('path {!r} does not exist'.format(p))
        if not file.is_file():
            raise argparse.ArgumentTypeError('path {!r} is not a file'.format(p))
        return file

    def valid_url(u: str) -> Url:
        url = urlparse(u)
        print(repr(url))
        if not url.netloc:
            raise argparse.ArgumentTypeError('url {!r} has no domain'.format(u))
        return url

    # build arguments

    parser = argparse.ArgumentParser(
        description='Run ocaml "doctests".',
        epilog='Submit bugs to <https://github.com/olin/focstest/issues/>.')

    # explicitly add version handler to save -v for verbose below
    # NOTE: this is not passed to the args object
    parser.add_argument('--version', action='version', version=__version__)

    input_types = parser.add_mutually_exclusive_group(required=False)
    input_types.add_argument('--url', type=valid_url,
                             help='a url to scrape tests from (usually automagically guessed from ocaml_file)')
    input_types.add_argument('--from-html', type=existing_file, dest='html_file',
                             help='a local html file to scrape tests from')

    parser.add_argument('ocaml_file', type=existing_file,
                        help='the ocaml file to test against')
    parser.add_argument('-v', '--verbose', action='store_true',
                        help='increase test output verbosity')
    parser.add_argument('--ignore-cache', action='store_true',
                        help='ignore cached files')

    test_selection = parser.add_mutually_exclusive_group(required=False)
    test_selection.add_argument('-u', '--use-suites', metavar='N', type=int, nargs='*',
                                help='test suites to use exclusively, indexed from 1')
    test_selection.add_argument('-s', '--skip-suites', metavar='N', type=int, nargs='*',
                                help='test suites to skip, indexed from 1')

    parsed_args = parser.parse_args(args=args)

    # convert to typed object

    try:
        typed_args = Args(**vars(parsed_args))
    except TypeError as e:
        logger.exception((
            "Internal error while converting parsed arguments, "
            "check for discrepancies between 'parse_args()' and 'Arg' object"))
        raise e

    return typed_args


#
# ERRORS
#


class FocstestError(Exception):
    """Base class for all Focstest-related exceptions.

    Attributes:
        exit_code: An integer exit code to return with `exit()` if this error
            stops the program.
    """
    _template: str = ''
    _hint: Optional[str] = None
    exit_code: int = 1

    def __str__(self) -> str:
        return self._template.format(**vars(self))

    def hint(self) -> Optional[str]:
        """An optional message to print to a CLI user that suggests a fix."""
        return self._hint


class UrlInferenceError(FocstestError):
    """Homework URL could not be inferred from OCaml filename."""
    _template = 'Unable to infer FoCS homework url from OCaml filename {ocaml_file!r}'
    _hint = 'Specify a url (with --url) or a local html file (with --from-html)'

    def __init__(self, ocaml_file: PathLike):
        self.ocaml_file = _pathlike_to_str(ocaml_file)


class InputFileError(FocstestError):
    """Error while accessing an input file.

    Raised from e.g. `OSError`.
    """
    _template = 'Error accessing {file_description} {filename!r}'
    exit_code = 66  # EX_NOINPUT

    def __init__(self, file_name: PathLike, file_description: str = 'file'):
        self.file_name = _pathlike_to_str(file_name)
        self.file_description = file_description


class FetchError(FocstestError):
    """Error while fetching a url.

    Raised from e.g. `requests.RequestException`.
    """
    _template = 'Error fetching url {url!r}'

    def __init__(self, url: UrlLike):
        self.url = _urllike_to_str(url)

    def hint(self) -> Optional[str]:
        if isinstance(self.__cause__, requests.ConnectionError):
            return 'Your internet connection may be down, or the website may not exist'
        return None


class OcamlError(FocstestError):
    """An OCaml error returned by the interpreter."""

    def __init__(self, error: str):
        self.error = error

    def __str__(self) -> str:
        return self.error


class OcamlException(OcamlError):
    """An OCaml exception returned by the interpreter."""
    pass


class UnimplementedException(OcamlException):
    """An exception commonly raised by unfinished template homework code."""
    pass


class OcamlFileError(FocstestError):
    """An OCamlError returned while loading a file in the interpreter.

    __cause__ is set to the encountered OCamlError.
    """
    _template = 'OCaml returned an error while loading {ocaml_file!r}'
    _hint = 'Fix the error to continue'

    def __init__(self, ocaml_file: PathLike):
        self.ocaml_file = _pathlike_to_str(ocaml_file)


def exception_handler(e: FocstestError) -> None:
    """Print a FocstestError and any context, then exit."""
    try:
        name = PurePath(sys.argv[0]).name
    except IndexError:
        name = 'focstest'

    msg = name + ': Error: '
    msg += str(e)
    msg = colored(msg, 'red', attrs=['bold'])

    if e.__cause__:
        msg += ': '
        msg += str(e.__cause__)

    print(msg, file=sys.stderr)

    hint = e.hint()
    if hint:
        print(colored('Hint: ' + hint, attrs=['bold']), file=sys.stderr)

    exit(e.exit_code)


#
# TEST FETCHING
#


def get_html(ocaml_file: PathLike,
             html_file: Optional[PathLike] = None,
             url: Optional[UrlLike] = None,
             use_cache: bool = True) -> Tuple[str, PurePath]:
    """
    Raises:
        UrlInferenceError: `url` was not provided and could not infer url from `ocaml_file`.
        FetchError: Errors from trying to fetch from `url`.
        OSError: Errors from reading `html_file` if provided.
    """
    if html_file:
        try:
            with open(html_file) as f:
                return f.read(), PurePath(html_file)
        except OSError as e:
            raise InputFileError(html_file, 'html file') from e

    if not url:
        url = infer_url(ocaml_file)
        if not url:  # break if filename can't be matched
            raise UrlInferenceError(ocaml_file)

    try:
        return fetch_url(url, use_cache)
    except requests.RequestException as e:
        raise FetchError(url) from e


def urlparse(url: str, scheme: str = 'https', allow_fragments: bool = True) -> Url:
    """Wrapper of `urllib.parse.urlparse`.

    Defaults to https and allows netloc/domain to be specified without a leading '//'.

    urllib considers domain as part of path if no scheme or leading '//' is present:
    >>> urllib.parse.urlparse('example.com')
    ParseResult(scheme='', netloc='', path='example.com', params='', query='', fragment='')

    This implementation does not:
    >>> urlparse('example.com')
    ParseResult(scheme='https', netloc='example.com', path='', params='', query='', fragment='')

    This implementation defaults to https:
    >>> urlparse('//example.com') == urllib.parse.urlparse('//example.com', scheme='https')
    True

    Otherwise, it returns the same results as the urllib version:
    >>> urlparse('//example.com') == urllib.parse.urlparse('//example.com', scheme='https')
    True
    >>> urlparse('https://example.com') == urllib.parse.urlparse('https://example.com')
    True
    >>> urlparse('https://example.com/foo/index.html') == urllib.parse.urlparse('https://example.com/foo/index.html')
    True
    """
    parsed = urllib.parse.urlparse(url, scheme, allow_fragments)
    if not parsed.netloc:
        if not url.startswith('//'):
            url = '//' + url
        parsed = urllib.parse.urlparse(url, scheme, allow_fragments)
    return parsed


def infer_url(filepath: PathLike) -> Optional[Url]:
    """Infer the relevant FoCS website url from an OCaml homework file.

    Returns: None if the filename could not be parsed

    >>> infer_url('foo/bar/homework1.ml') == urlparse('https://rpucella.net/courses/focs-sp22/homeworks/1/index.html')
    True
    >>> infer_url('foo/bar.ml') is None
    True
    """
    if not isinstance(filepath, PurePath):
        filepath = PurePath(filepath)

    mtch = OCAML_FILE_RE.match(filepath.name)
    if not mtch:
        return None

    hw_num = mtch.group(1)
    url = urlparse(urljoin(BASE_URL, HTML_FILE_TEMPLATE.format(hw_num)))
    return url


def fetch_url(url: UrlLike, use_cached: bool = False) -> Tuple[str, PurePath]:
    """Get the html text from a url, optionally with a filesystem cache.

    Args:
        url: The url to fetch from.
        use_cached: Use a previously-cached version, if it exists.

    Returns: The contents of the html file and its cache location.

    Raises:
        requests.HTTPError: The webserver returned an error
        requests.ConnectionError: An error occured trying to fetch url, and a
            cached version does not exist or use_cached is False
    """
    url = _urllike_to_url(url)

    cache_dir = get_cache_dir()

    page_name = get_cache_filename(url)
    html_filepath = Path(cache_dir) / page_name  # local filepath

    def read_cached_file() -> str:
        with open(html_filepath, 'r') as htmlcache:
            html = htmlcache.read()
            return html

    # get webpage if cached version doesn't already exist

    cached_file_exists = html_filepath.exists()
    # only try to access file time if file exists
    cached_file_is_fresh = cached_file_exists and time.time() - os.path.getmtime(html_filepath) < CACHE_TIMEOUT

    if use_cached and cached_file_exists and cached_file_is_fresh:
        logger.debug("Using cached version of page at %r", html_filepath)
        return read_cached_file(), html_filepath

    try:
        logger.info("Fetching %r", _urllike_to_str(url))
        response = requests.get(urlunparse(url))
        response.raise_for_status()  # break if webserver returns error (raises HTTPError)
    except requests.ConnectionError as e:
        if not use_cached or not cached_file_exists:
            raise e

        # fall back to cached version

        logger.warning('Unable to connect to %r, using cached version at %r: %s', url.geturl(), html_filepath, e)
        return read_cached_file(), html_filepath

    html = response.text
    with open(html_filepath, 'w') as htmlcache:
        htmlcache.write(html)
    logger.debug("Saved %r to cache at %r", url.geturl(), html_filepath)

    return html, html_filepath


def get_cache_dir() -> PurePath:
    """Determine the path of a valid cache directory.

    Creates the returned directory if it does not already exist.
    """
    temp_dir = Path(tempfile.gettempdir())  # most likely /tmp/ on Linux
    cache_dir = temp_dir / 'focstest-cache'
    if not cache_dir.exists():
        cache_dir.mkdir()
        logger.info('Created cache directory at %r', str(cache_dir))
    return cache_dir


def get_cache_filename(url: UrlLike) -> PurePath:
    """Get a filesystem-safe filename based on a url

    >>> get_cache_filename('http://foo.bar/baz/qux/') == PurePath('foo_bar_baz_qux.html')
    True

    normalizes protocol
    >>> get_cache_filename('http://foo.bar/baz/qux') == get_cache_filename('https://foo.bar/baz/qux')
    True

    normalizes trailing slashes
    >>> get_cache_filename('http://foo.bar/baz/qux') == get_cache_filename('http://foo.bar/baz/qux/')
    True

    normalizes directory names and index.html
    >>> get_cache_filename('http://foo.bar/baz/qux') == get_cache_filename('http://foo.bar/baz/qux/index.html')
    True
    >>> get_cache_filename('http://foo.bar/baz/qux/') == get_cache_filename('http://foo.bar/baz/qux/index.html')
    True

    two different homeworks end up with different filenames
    >>> hw1 = infer_url('homework1.ml'); hw2 = infer_url('homework2.ml')
    >>> get_cache_filename(hw1) != get_cache_filename(hw2)
    True
    """
    BAD_CHARS = {'\0', '\\', '/', ':', '*', '?', '"', '>', '<', '|', ':'}

    url = _urllike_to_url(url)

    # if Riccardo switches to php and the urls are query-encoded like 'homework.php?id=9', this will need to be updated
    filename = url.netloc.replace('.', '_') + url.path
    # normalize trailing / and /index.html
    filename = filename.rstrip('/')
    if filename.endswith('/index.html'):
        filename = filename[:-len('/index.html')]
    filename = ''.join(c if c not in BAD_CHARS else '_' for c in filename)
    # default to .html extension
    path, ext = os.path.splitext(filename)
    if ext == '':
        filename += '.html'
    return PurePath(filename)


#
# TEST PARSING
#


def parse_html_tests(html: str, filename: Optional[PathLike] = None) -> Iterable[TestSuite]:
    return filter(None, (parse_tests(b, pos) for b, pos in get_blocks(html, filename)))


def get_blocks(html: str, filename: Optional[PathLike] = None) -> List[Tuple[str, Optional[FilePos]]]:
    """Parse code blocks with ocaml tests from html.

    Args:
        html: HTML text.
        filename: The name of the file `html` originates from, used for debugging.

    Returns:
        A list of strings of code blocks and their position in the html text.
    """

    page = bs4.BeautifulSoup(html, 'html.parser')
    code_blocks = page.select(CODE_BLOCK_SELECTOR)
    if len(code_blocks) == 0:
        logger.error('Code block selector %r returned no matches', CODE_BLOCK_SELECTOR)

    def get_pos(block: bs4.Tag) -> Optional[FilePos]:
        if block.sourceline is None:
            return None
        line = block.sourceline
        # bs4 with html.parser returns 0-based columns
        col = block.sourcepos + 1 if block.sourcepos is not None else 1

        return FilePos(line, col, file=filename)

    return [(block.get_text(), get_pos(block)) for block in code_blocks]


def parse_tests(text: str, pos: Optional[FilePos] = None) -> TestSuite:
    """Parse OCaml doctests from text.

    Returns:
        A list of test tuples with format (input, expected)
    """

    pattern = _regex_by_surrounds('# ', ';;')

    def process_input(start: Optional[int], end: Optional[int]) -> str:
        input = text[start: end]
        input = input.rstrip()
        input = _removeprefix(input, '# ')
        return input

    def process_output(start: Optional[int], end: Optional[int]) -> str:
        output = text[start:end]
        output = _removeprefix(output, '\n')
        return output

    inputs = list(pattern.finditer(text))
    if len(inputs) == 0:
        logger.debug("No tests found for block at %s", pos if pos else 'unknown position')
        return []

    # outputs are the text between inputs
    outputs = []
    for input, next in _pairwise(inputs):
        start = input.end()
        end = next.start()
        outputs.append(process_output(start, end))

    last_output = process_output(inputs[-1].end(), None)
    outputs.append(last_output)

    inputs = [process_input(*mtch.span()) for mtch in inputs]

    tests = [Test(input, expected) for input, expected in zip(inputs, outputs)]
    return tests


#
# TEST RUNNING
#


class BaseTestSuiteRunner(object):
    """Callback-based interface for running test suites with `run_test`.

    Extend the class and override any of the `on_*` methods, then call `run`.

    On completion the `total_run`, `total_failed`, and `total_skipped`
    attributes hold the total counts of their respective test outcomes.
    """

    suite_num: int
    suite: TestSuite
    test_num: int
    test: Test

    total_run: int
    total_failed: int
    total_skipped: int

    def __init__(self, suites: Iterable[TestSuite], ocaml_file: PathLike, skip_unimplemented_suites: bool):
        self.suites = list(enumerate(suites, start=1))
        self.ocaml_file = ocaml_file
        self.skip_unimplemented = skip_unimplemented_suites

        self.total_run = 0
        self.total_failed = 0
        self.total_skipped = 0

    def skip_if(self, predicate: Callable[[int, TestSuite], Any]) -> None:
        """Skip suites based on a predicate, preserving their original ordering and number."""
        skipped = []
        for i in range(len(self.suites)):
            suite_num, suite = self.suites[i]
            if predicate(suite_num, suite):
                self.total_skipped += len(suite)
                skipped.append(i)

        # remove from list backwards to preserve indices
        skipped.reverse()
        for i in skipped:
            del self.suites[i]

    def on_start(self) -> None:
        """Called once at the beginning of `run`."""
        pass

    def on_complete(self) -> None:
        """Called once at the end of `run`."""
        pass

    def on_suite_start(self) -> None:
        """Called at the beginning of each suite that is run.

        The `suite_num` and `suite` attributes are available.
        """
        pass

    def on_suite_complete(self) -> None:
        """Called at the end of each suite that is run.

        See `on_suite_start` for avaiable attributes.
        """
        pass

    def on_test_start(self) -> None:
        """Called at the beginning of each test that is run.

        The `test_num`, `test`, `suite_num`, and `suite` attributes are available.
        """
        pass

    def on_test_error(self, e: Exception) -> None:
        """Called when a test cannot be evaluated and will be skipped.

        The `test_num`, `test`, `suite_num`, and `suite` attributes are available.
        """
        pass

    def on_test_unimplemented(self) -> None:
        """Called when a test raises an `UnimplementedException`, and will be skipped.

        The `test_num`, `test`, `suite_num`, and `suite` attributes are available.
        """
        pass

    def on_test_complete(self, result: TestResult) -> None:
        """Called after a test is run.

        The `test_num`, `test`, `suite_num`, and `suite` attributes are available.
        """
        pass

    def run(self) -> None:
        """Run the suites of tests in the OCaml REPL.

        Raises:
            OcamlFileError: If OCaml returns an error while executing `ocaml_file`.
        """
        self.on_start()

        for suite_num, suite in self.suites:
            self.suite_num = suite_num
            self.suite = suite
            self.on_suite_start()

            for test_num, test in enumerate(suite, 1):
                self.test_num = test_num
                self.test = test

                try:
                    result = run_test(test.input, test.expected, file=self.ocaml_file)
                except ValueError as e:
                    # skip tests that can't be run
                    self.on_test_error(e)

                    self.total_skipped += 1
                    continue
                # OcamlFileErrors are left to bubble up

                did_pass, output, error = result

                if isinstance(error, UnimplementedException):
                    self.on_test_unimplemented()
                    self.total_skipped += 1

                    if self.skip_unimplemented:
                        self.total_skipped += len(suite) - test_num
                        break
                    else:
                        continue

                self.on_test_complete(result)

                if not did_pass:
                    self.total_failed += 1
                self.total_run += 1

            self.on_suite_complete()

        self.on_complete()


class PrintingTestRunner(BaseTestSuiteRunner):
    """Run suites of tests and print the results."""

    SUITE_SEP = '-'*80

    def __init__(self,
                 suites: Iterable[TestSuite],
                 ocaml_file: PathLike,
                 output_file: TextIO = sys.stdout,
                 verbose: bool = False,
                 skip_unimplemented_suites: bool = False):
        super().__init__(suites, ocaml_file, skip_unimplemented_suites)

        self.verbose = verbose
        self.output_file = output_file

    def cprint(self,
               color: Optional[str],
               *values: Any,
               attrs: Optional[List[str]] = None) -> None:
        msg = ' '.join(map(str, values))
        print(colored(msg, color=color, attrs=attrs), file=self.output_file)

    @staticmethod
    def format_test_output(test: Test, result: TestResult, indent: str = '  ') -> str:
        """Create an explanatory str about a test for printing."""
        def format_info(kind: str, value: str) -> str:
            return indent+kind.upper()+':\t'+repr(value)
        lines = [
            format_info('input', test.input),
            format_info('expected', test.expected),
            format_info('output', result.output),
        ]
        return '\n'.join(lines)

    def current_test_description(self) -> str:
        return 'test {} of {} in {}'.format(self.test_num, len(self.suite), self.current_suite_description())

    def current_suite_description(self) -> str:
        # for each test:
        function = self.suite[0].input.split(maxsplit=1)[0]
        return 'suite {} ({!r})'.format(self.suite_num, function)

    def on_suite_start(self) -> None:
        if self.verbose:
            print('Testing suite', self.suite_num)

    def on_suite_complete(self) -> None:
        if self.verbose:
            self.cprint(None, self.SUITE_SEP)

    def on_complete(self) -> None:
        failed = self.total_failed
        run = self.total_run
        skipped = self.total_skipped

        self.cprint('red' if failed > 0 else 'green', failed, 'of', run, 'tests failed')
        self.cprint('yellow' if skipped > 0 else None, skipped, 'tests skipped')

    def on_test_error(self, e: Exception) -> None:
        self.cprint('yellow', 'Unable to run test {!r}: {}'.format(self.test.input, e))

    def on_test_unimplemented(self) -> None:
        if self.verbose:
            self.cprint('yellow', 'Unimplemented', self.current_test_description())
            print(self.test.input)
        if self.skip_unimplemented:
            self.cprint('yellow', 'Skipped unimplemented', self.current_suite_description())

    def on_test_complete(self, result: TestResult) -> None:
        test_str = self.format_test_output(self.test, result)

        if not result.success:
            self.cprint('red', 'Failed', self.current_test_description())
            self.cprint(None, test_str)
        elif self.verbose:
            self.cprint('green', 'Passed', self.current_test_description())
            self.cprint(None, test_str)


# text normalization techniques

def equivalent(text: str) -> str:
    return text


def strip_whitespace(text: str) -> str:
    return text.strip()


def normalize_whitespace(text: str) -> str:
    """Replace instances of whitespace with ' '.

    >>> normalize_whitespace(' a\\n b c \td\\n')
    'a b c d'
    """
    return ' '.join(text.split())


def run_test(input: str, expected_out: str, file: Optional[PathLike] = None) -> TestResult:
    """Run an OCaml expression in the interpreter and compare the output against an expected value.

    Attempts are made to account for whitespace differences between the expected and real output.

    Args:
        input: The OCaml expression to run.
        expected_out: The expected output of `input` to compare against.
        file: The path to an OCaml file to load in the interpreter before running `input`.

    Returns:
        A tuple of a boolean indicating whether the test passed or not, the
        output of the test, and any errors detected in the output.

    Raises:
        ValueError: If `input` is not a complete OCaml expression.
        OcamlFileError If an OCaml error occurs or exception raised during the execution of `file`.
    """

    # TODO: expose steps?
    # TODO: make returned method optional?

    steps = [
        equivalent,
        strip_whitespace,
        normalize_whitespace
    ]

    output = run_ocaml_code(input, files=(file,) if file else ())
    for step in steps:
        function = input.split()[0]  # grab the first word of the command (probably the function name)
        method = step.__name__
        result = step(output) == step(expected_out)
        if result is True:
            logger.debug('Test %r passed with method %r', function, method)
            break

    error = parse_ocaml_error(output)

    return TestResult(result, output, error)


def run_ocaml_code(code: str, files: Iterable[PathLike] = ()) -> str:
    """Run OCaml code in the interpreter.

    Args:
        code: A complete OCaml expression to run.
        files: Paths of files to load in the interpreter before running `code`.

    Returns: The parsed output of `code`, which should include any printed
        output and the type for each expression of input.

    Raises:
        ValueError: If `code` is an incomplete expression or cannot be evaluated.
        OcamlFileError: If an OCaml error occurs or exception is raised during
            the execution of `files`.
    """
    files = tuple(files)
    if not code.rstrip().endswith(';;'):
        raise ValueError('code is not a complete ocaml expression')
    cmds = [code]
    for file in files:
        cmds.insert(0, '#use "{}";;'.format(file))
    cmds.append('#quit;;\n')  # add a quit command at the end to exit from the repl

    outs, errs = _exec_ocaml_interpreter('\n'.join(cmds), 5)
    # Before each line of input, ocaml spits out a `# ` (the interactive prompt).
    # Here, it is used to separate prints/return values from statements.
    # TODO: split only after newline
    matches = [m.strip() for m in outs.split('# ')]
    # matches should line up to be:
    # startup text | [ file output | ... ] code output | quit whitespace
    # first match is everything printed on startup, generally just version info
    # last match is the remaining whitespace after the `#quit;;` command, unless
    # something went wrong]
    expected = 1 + len(files) + 2
    logger.debug('Found %s matches, expected %s', len(matches), expected)

    if len(matches) != expected:
        # look for reasons why it failed
        # the issue should be with the code statement
        # #use statements may return errors, but they should still evaluate
        raise ValueError("Couldn't evaluate code {!r}: {!r}".format(code, matches[-1]))

    # check for errors, exceptions in file outputs
    for i, file in enumerate(files, start=1):
        output = matches[i]
        err = parse_ocaml_error(output)
        if err is not None:
            raise OcamlFileError(file) from err

    code_output = matches[-2]

    return code_output


def _exec_ocaml_interpreter(code: str, timeout: Numeric) -> Tuple[str, str]:
    """Run OCaml code with the REPL and capture the output.

    `code` should generally cause the REPL to exit, or a TimeoutExpired
    exception will be raised.

    Args:
        code: The expressions of code to run.
        timeout: The max time in seconds to wait for the code to run.

    Returns:
        A tuple of raw stdout and stderr strings (output, errors)

    Raises:
        subprocess.TimeoutExpired: If `timeout` is reached.
    """
    # '-noinit' disables loading the init file
    # '-color never' stops ocaml from returning terminal escape characters (color/formatting, etc)
    with subprocess.Popen(['ocaml', '-noinit', '-color', 'never'],
                          stdin=subprocess.PIPE,
                          stdout=subprocess.PIPE,
                          stderr=subprocess.PIPE,
                          universal_newlines=True) as p:
        try:
            outs, errs = p.communicate(code, timeout)
        except subprocess.TimeoutExpired as e:
            p.kill()
            outs, errs = p.communicate()
            raise e
    return (outs, errs)


def parse_ocaml_error(output: str) -> Optional[Union[OcamlError, OcamlException, UnimplementedException]]:
    """Parse OCaml errors and exceptions from REPL output."""
    exception = _parse_exception(output)
    if exception is not None:
        return exception

    error = _parse_error(output)
    return error


def _parse_exception(output: str) -> Optional[Union[OcamlException, UnimplementedException]]:
    pattern = _regex_by_surrounds('Exception:', r'\.')

    mtch = pattern.search(output)
    if mtch is None:
        return None
    start, end = mtch.span()

    error = output[start:end].strip()

    # catch a variety of `unimplemented`-like `failwith`s
    if 'Failure' in error and 'implemented' in error.lower():
        return UnimplementedException(error)
    return OcamlException(error)


def _parse_error(output: str) -> Optional[OcamlError]:
    pattern = _regex_by_surrounds('Error:', '')
    mtch = pattern.search(output)
    if mtch is None:
        return None
    start, end = mtch.span()

    error = output[start: end].strip()

    # TODO: look for hint, location

    return OcamlError(error)


#
# UTILITIES
#


@lru_cache
def _regex_by_surrounds(beginning: str, ending: str) -> Pattern[str]:
    # matches the smallest string that:
    # - starts with `beginning` at the beginning of a line
    # - ends with `ending` and any trailing whitespace at the end of a line
    #
    # see <https://rexegg.com/regex-quantifiers.html#greedytrap>
    pattern = r'^{}.*?{}\s*$'.format(beginning, ending)
    return re.compile(pattern, re.DOTALL | re.MULTILINE)


def _urllike_to_url(url: UrlLike) -> Url:
    if isinstance(url, str):
        return urlparse(url)
    return url


def _urllike_to_str(url: UrlLike) -> str:
    if isinstance(url, Url):
        return urlunparse(url)
    return url


def _pathlike_to_str(path: PathLike) -> str:
    if isinstance(path, str):
        return path
    return cast(str, path.__fspath__())


def _pairwise(iterable: Iterable[T]) -> Iterable[Tuple[T, T]]:
    """
    >>> list(_pairwise(range(4)))
    [(0, 1), (1, 2), (2, 3)]
    """
    a, b = itertools.tee(iterable)
    next(b, None)
    return zip(a, b)


def _removesuffix(s: str, suffix: str) -> str:
    if s.endswith(suffix):
        return s[:-len(suffix)]
    return s


def _removeprefix(s: str, prefix: str) -> str:
    if s.startswith(prefix):
        return s[len(prefix):]
    return s


if __name__ == "__main__":
    main()
