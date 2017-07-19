import sys
import copy
import inspect
import functools
import traceback
from .text import describe, describe_them, fullname, conjunction
from future.utils import raise_ as raises


def dictmerge(dicts, reverse=False):
    new = {}
    if reverse:
        dicts = reversed(tuple(dicts))
    for d in dicts:
        new.update(d)
    return new


def flatten(iterable, depth=1):
    for x in iterable:
        if depth > 0:
            yield from flatten(x, depth - 1)
        else:
            yield x


def str_to_bool(s):
    s = s.lower()
    if s in ("true", "1"):
        return True
    elif s in ("false", "0"):
        return False
    else:
        raise ValueError("Expected 'true', 'false', '1', '0' not %r" % s)


def class_attribute_lineage(cls, name, base=None):
    for c in cls.mro():
        if name is not None:
            if name in vars(c):
                yield c, getattr(c, name)
        elif name in vars(c):
            yield c, getattr(c, name)


def copy_mapping(m):
    _type = type(m)
    new = copy.copy(m)
    for k, v in d.items():
        if isinstance(v, _type):
            v = copy_mapping(v)
        new[k] = v
    return new


class ErrorGroup(object):

    def __init__(self):
        self.tracebacks = []

    def add(self):
        self.tracebacks.append(traceback.format_exc())

    def throw(self):
        msg = "The following exceptions occured:\n\n"
        msg += "\n".join(self.tracebacks)
        raise Exception(msg)

    def __len__(self):
        return len(self.tracebacks)


class Sentinel(object):

    def __init__(self, name, help=None, module=None):
        if module is None:
            module = inspect.currentframe().f_back.f_locals["__name__"]
        self.module = module
        if help:
            self.__doc__ = help
        self.name = name

    def __repr__(self):
        return self.module + '.' + self.name

    def __str__(self):
        return self.name


def decoration(function):
    @functools.wraps(function)
    def wrapper(*args, **kwargs):
        def setup(thing):
            return function(thing, *args, **kwargs)
        return setup
    return wrapper
