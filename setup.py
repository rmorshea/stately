from __future__ import print_function

# the name of the project
name = "stately"

#-----------------------------------------------------------------------------
# Minimal Python version sanity check
#-----------------------------------------------------------------------------

import sys

if sys.version_info < (3, 3):
    error = "ERROR: %s requires Python version 3.3 or above." % name
    print(error, file=sys.stderr)
    sys.exit(1)

PY3 = (sys.version_info[0] >= 3)

#-----------------------------------------------------------------------------
# get on with it
#-----------------------------------------------------------------------------

import os
import os.path as osp
from glob import glob
from distutils.core import setup


here = osp.abspath(osp.dirname(__file__))
root = osp.join(here, name)

packages = []
for d, _, _ in os.walk(root):
    if osp.exists(osp.join(d, '__init__.py')):
        packages.append(d[len(here)+1:].replace(osp.sep, '.'))

version_ns = {}
with open(osp.join(root, 'version.py')) as f:
    exec(f.read(), {}, version_ns)

with open("summary.rst", "r") as f:
    long_description = f.read()

setup_args = dict(
    name = name,
    version = version_ns['__version__'],
    scripts = glob(osp.join('scripts', '*')),
    packages = packages,
    description = "stately",
    long_description = long_description,
    author = "Ryan Morshead",
    author_email = "ryan.morshead@gmail.com",
    url = "https://github.com/rmorshea/stately",
    liscence = "MIT",
    platforms = "Linux, Mac OS X, Windows",
    keywords = ["events", "async", "state"],
    classifiers = [
        'Intended Audience :: Developers',
        'Programming Language :: Python :: 3.5',
        ],
)

if __name__ == '__main__':
    setup(**setup_args)
