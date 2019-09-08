# focstest

So, you're in Olin's FoCS course and you've started to fill out the functions
for this week's homework assignment. You're looking at the homework document and
you find a bunch of blocks like these:
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

Introducing...
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

> "This program is not signed by a trustworthy source. Are you sure you want to
> run this?"  
> \-Symantec Endpoint Protection

> "How much time did you spend on this?"  
> \-concerned friends and family

## Getting Started

### Installation

The python packages `BeautifulSoup`, `requests`, and `termcolor` are required. Install them with `pip install bs4 requests termcolor`, or `pipenv install`.

### Usage

`focstest` uses a standard python-powered command-line interface. You can always ask it for help with `--help` or `-h`.

```
$ ./focstest.py --help
usage: focstest.py [-h] [-u URL] [-v] [--log-level {debug,info,warning}] [-uc]
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

## Development

Run `pipenv install --dev` to install all of the dev packages.

Build an executable of your own with `pyinstaller -F focstest.py`.
