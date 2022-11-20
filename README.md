# focstest

_(you can skip to [Getting Started](#getting-started))_

_If you're looking to update this for a new semester, see [Development](#development)._

So, you're in Olin's FoCS (Foundations of Computer Science) course and you've
started to fill out the functions for this week's homework assignment. You're
looking at the homework document and you find a bunch of blocks of example
outputs like these:
```
# splits [];;
- : ('a list * 'a list) list = [([], [])]
# splits [1];;
- : (int list * int list) list = [([], [1]); ([1], [])]
# splits [1; 2; 3; 4];;
- : (int list * int list) list =
[([], [1; 2; 3; 4]); ([1], [2; 3; 4]); ([1; 2], [3; 4]); ([1; 2; 3], [4]);
 ([1; 2; 3; 4], [])]
```

Sure, you could copy those in one-by-one into the `ocaml` (or
[`utop`](https://github.com/ocaml-community/utop)) interpreter and check them
yourself with your tired eyes, but this is a computer science course! There's
got to be a slightly faster way that may or may not have taken more development
time to create than it saved...

Introducing focstest: the doctest-ish ocaml program that you've always wanted!

Replace those tedious seconds of typing with a simple
`focstest homework1.ml` and watch your productivity soar!

`focstest` is packed with many useful features, including:
- colors!
- test selection!
- error parsing!
- cache invalidation!

Just read these (mostly real) testimonials:

> "I already made one of those"  
> \-Nathan Yee

> "Wow, thanks"  
> \-Matt Brucker

> "Why are you doing this?"  
> \-Sarah Barden

> "Oh, yeah, Nathan made one of those"  
> \-Taylor Sheneman

> "For a small project like this, I'd give it like, a 7"  
> \-Adam Novotny

> "This program is not signed by a trustworthy source. Are you sure you want to
> run this?"  
> \-Symantec Endpoint Protection

> "How much time did you spend on this?"  
> \-concerned friends and family

## Getting Started

### Prerequisites

You'll need Python 3.7+ and `pip`.

The `ocaml` interpreter needs to be installed and on your PATH (i.e. you can run it
from a terminal).

### Installation

#### Pip

The recommended way to install and upgrade `focstest` is through `pip`,
which will install the necessary package requirements and add the `focstest`
command to your terminal. _(Note that depending on your system, you may
need to run `pip3` or `python3 -m pip` instead)_:
```shell
pip3 install git+https://github.com/olin/focstest.git
```

You should now be able to run `focstest --help` and see the
[usage message below](#usage).

#### Pip (local)

You can also install it by cloning the source repository to somewhere on
your machine and running `pip install`

```shell
git clone https://github.com/olin/focstest.git
pip install focstest/
```

To update to the latest version, pull from the remote and install again:
```shell
cd focstest/
git pull
pip install .
```

#### Manual

Alternatively, you can download and run the `focstest.py` script directly
after installing the necessary requirements:

The python packages `beautifulsoup4`, `requests`, and `termcolor` are required.
Install them with `pip install bs4 requests termcolor`.

### Usage

**Note/Disclaimer: `focstest` only compares the given output with your code's output.
Generally, the FoCS examples are not exhaustive and are often more nuanced than
a direct comparison. You'll still need to understand _what the problem is asking_
and _whether your output makes sense_.**

`focstest` works by parsing doctest-like blocks of ocaml code from a website,
and then running them with your provided ocaml file loaded to compare the
outputs. If you give it a homework file, it can infer the relevant webpage to
scrape tests from:
```
focstest homework2.ml
```
but you can also give it a url directly:
```
focstest homework2.ml --url http://rpucella.net/courses/focs-fa19/homeworks/homework2.html
```
The html files are _cached locally_ for 30 minutes to reduce the number of
network requests. If the website has been updated with corrections or additions
and you want to refresh `focstest`'s copy, use the `--ignore-cache` flag:
```
focstest homework2.ml --ignore-cache
```

`focstest` uses a standard python-powered command-line interface. You can always
ask it for help with `--help` or `-h`.

```
$ focstest --help
usage: focstest [-h] [--version] [--url URL | --from-html HTML_FILE] [-v] [--ignore-cache] [-u [N [N ...]] | -s [N [N ...]]] ocaml_file

Run ocaml "doctests".

positional arguments:
  ocaml_file            the ocaml file to test against

optional arguments:
  -h, --help            show this help message and exit
  --version             show program's version number and exit
  --url URL             a url to scrape tests from (usually automagically guessed from ocaml_file)
  --from-html HTML_FILE
                        a local html file to scrape tests from
  -v, --verbose         increase test output verbosity
  --ignore-cache        ignore cached files
  -u [N [N ...]], --use-suites [N [N ...]]
                        test suites to use exclusively, indexed from 1
  -s [N [N ...]], --skip-suites [N [N ...]]
                        test suites to skip, indexed from 1

Submit bugs to <https://github.com/olin/focstest/issues/>.
```

For most homeworks, the workflow that I've used is going question by question
with the `-u` flag (each "test suite" is a parsed block of code, which generally
corresponds to the homework questions):
```shell
$ # work on question 1
$ focstest h1.ml -u 1
$ # work more on question 1
$ focstest h1.ml -u 1
$ # finish and start question 2
$ focstest h1.ml -u 2
$ # start to doubt that focstest works and check each test output
$ focstest h1.ml -u 2 -v
$ # ...eventually finish the homework and run everything to double-check
$ focstest h1.ml
$ # become increasingly paranoid that focstest isn't finding my mistakes and
$ # inspect each test one-by-one
$ focstest h1.ml -v
```

### What It Can't Do (Yet?)

- Detect syntax errors/typos in expected cases (comparing an expected `[4  2; 1]` to your program's output `[4; 2; 1]` will tell you that your output is wrong).
- Check if the same items exist in the output, regardless of order (if you need to build a set of items and the printed output is in a different order than the expected, it will still fail).
- Submit the assignment via email for you.

## Development

Issues and Pull Requests are welcome!

If you're interested in maintaining focstest, reach out to [any contributors](https://github.com/olin/focstest/graphs/contributors),
or if that fails, a [member of the olin org](https://github.com/orgs/olin/people)
for repo edit access.

With the repository cloned to your machine:
- Run `pipenv install --dev` to install all of the dev packages.
- Run tests with `python -m unittest discover`.
- Want to use it while you hack on it? Install it with `pip install -e`.

You can set `focstest`'s logging level with the `LOG_LEVEL` environment variable.
The possible values are all of python's [usual logging levels](https://docs.python.org/3/library/logging.html#levels), set it to `DEBUG` for more output.

```shell
$ LOG_LEVEL=DEBUG focstest homework3.ml
```

### Semesterly Updates

With each new semester, the class url for homeworks changes and the webpage
format may change.

To update the url/filename formats, the relevant pieces to change are the function `infer_url` and the
related variables for parsing filenames and creating the url: 
`BASE_URL`, `OCAML_FILE_PATTERN`, `HTML_FILE_TEMPLATE`.

To update the parsing of html files, the `get_blocks` function and `CODE_BLOCK_SELECTOR` variable is probably what you want. Ideally the selector can remain general enough to work with past and present pages.

### Releases

To release a new version of `focstest`:
1. Make sure it really works and isn't broken (wait for the CI tests on github to pass).
2. Create a new "tag" with `git tag v0.Y.Z`, where `v0.Y.Z` is the new version number. If you're not familiar with [semantic versioning](https://semver.org/), the TL;DR is:
    - keeping the first number `0` communicates a certain amount of instability and under-development-ness, and is what all the cool projects do
    - the second number `Y` is incremented when a breaking change is made, e.g. some cli flags have been changed or removed, or you feel like it (set `Z` back to 0 when you increment `Y`)
    - the third number `Z` is incremented when there are only smaller changes or bugfixes
3. Push the new tag to the github repo with `git push --tags`
4. Create a new "release" by going to https://github.com/olin/focstest/releases/new>. Write some info about what's changed.

That's it! The latest git tag is detected by pip automatically when installed.
