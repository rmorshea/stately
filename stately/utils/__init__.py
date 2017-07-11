import sys
import inspect
import functools
from .interpret import describe
from future.utils import raise_ as raises


def last_traceback():
    return sys.exc_info()[2]


class Exceptions(Exception):

    def __init__(self, *errors, **kwargs):
        prefix = kwargs.get("prefix", "")
        strings = ("%s(%s)" % (type(e).__name__, str(e)) for e in errors)
        super(Exceptions, self).__init__(prefix + ", ".join(strings))


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
