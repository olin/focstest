import configparser
import setuptools


def read_pipfile():
    """Parses package requirements from a Pipfile.

    Reformats them to match a pip-style specifier, e.g. `"bs4" = "*"` -> `bs4`,
    and `termcolor = ">=1.23"` -> `termcolor>=1.23`.
    """
    pfile = configparser.ConfigParser()
    pfile.read('Pipfile')
    req_specifiers = []
    for package, version in pfile['packages'].items():
        # normalize strings, since Pipenv likes to add quotes on some things
        package = package.strip('\'"')
        version = version.strip('\'"')
        spec = package + ('' if version == '*' else version)
        req_specifiers.append(spec)
    return req_specifiers


req_specifiers = read_pipfile()

setuptools.setup(
    name='focstest',
    url='https://github.com/olin/focstest/',
    use_scm_version=True,
    setup_requires=['setuptools_scm'],
    # packages=setuptools.find_packages(),
    install_requires=req_specifiers,
    py_modules=['focstest'],
    package_data={
        'focstest': ['py.typed'],
    },
    entry_points={
        'console_scripts': [
            'focstest = focstest:main',
        ],
    },
)
