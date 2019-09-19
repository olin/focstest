# focstest
_(you can skip to [Getting Started](#getting-started))_

So, you're in Olin's FoCS (Foundations of Computer Science) course and you've
started to fill out the functions for this week's homework assignment. You're
looking at the homework document and you find a bunch of blocks of example
outputs like these:
```
# expt 1 0;;
- : int = 1
# expt 1 3;;
- : int = 1
# expt 2 3;;
- : int = 8
```
Sure, you could type those in one-by-one into the `ocaml` (or
[`utop`](https://github.com/ocaml-community/utop)) interpreter and check them
yourself, but this is a computer science course! There's got to be a slightly
faster way that may or may not have taken more development time to create than
it saved...

Introducing:
```
  __                _            _
 / _| ___   ___ ___| |_ ___  ___| |_
| |_ / _ \ / __/ __| __/ _ \/ __| __|
|  _| (_) | (__\__ \ ||  __/\__ \ |_
|_|  \___/ \___|___/\__\___||___/\__|
```
Finally, the doctest-ish ocaml program that you've always wanted!

Replace those tedious seconds of typing with a simple
`focstest homework1.ml` and watch your productivity soar!

`focstest` is packed with many useful features, including:
- colors!
- 

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

You'll need Python 3.5+ and `pip`.

The `ocaml` interpreter needs to be installed and on your PATH (you can run it
from a terminal).

### Installation

#### Pip

The recommended way to install `focstest` is through `pip`, which will install the
necessary package requirements and add `focstest` to your terminal. You can do
this by cloning the source repository to somewhere on your machine and running
`pip install`:

```shell
git clone https://github.com/olin/focstest.git
pip install focstest/
```

You should now be able to run `focstest --help` and see the
[usage message below](#usage).

#### Manual

Alternatively, you can run the `focstest.py` script directly after installing
the necessary requirements:

The python packages `BeautifulSoup`, `requests`, and `termcolor` are required.
Install them with `pip install bs4 requests termcolor`, or `pipenv install`.

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
The html files are _cached locally_ to reduce the number of network requests. If
the website has been updated with corrections or additions and you want to
refresh `focstest`'s copy, use the `--update-cache` flag:
```
focstest homework2.ml --update-cache
```


`focstest` uses a standard python-powered command-line interface. You can always
ask it for help with `--help` or `-h`.

```
$ focstest --help
usage: focstest [-h] [-u URL] [-v] [--log-level {debug,info,warning}] [-uc]
                   [-U [N [N ...]] | -S [N [N ...]]]
                   ocaml-file

Run ocaml "doctests".

positional arguments:
  ocaml-file            the ocaml file to test against

optional arguments:
  -h, --help            show this help message and exit
  -u URL, --url URL     a url to scrape tests from
  -v, --verbose         increase test output verbosity
  --log-level {debug,info,warning}
                        the program log level
  -uc, --update-cache   update cached files
  -U [N [N ...]], --use-suites [N [N ...]]
                        test suites to use exclusively, indexed from 1
  -S [N [N ...]], --skip-suites [N [N ...]]
                        test suites to skip, indexed from 1
```

For most homeworks, the workflow that I've used is going question by question
with the `-U` flag (each "test suite" is a parsed block of code, which generally
corresponds to the homework questions):
```shell
$ # work on question 1
$ focstest h1.ml -U 1
$ # work more on question 1
$ focstest h1.ml -U 1
$ # finish and start question 2
$ focstest h1.ml -U 2
$ # start to doubt that focstest works and want more explicit output
$ focstest h1.ml -U 2 -v
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

Run `pipenv install --dev` to install all of the dev packages.

Run tests with `python -m unittest discover`.

Want to use it while you hack on it? Install it with `pip install -e`.
