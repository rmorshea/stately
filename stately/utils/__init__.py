import sys
import inspect
from .interpret import describe


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


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Python < 3.6 - PEP 487 Descriptor Compatibility - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


if sys.version_info >= (3, 6):
    Metaclass = type
else:
    class Metaclass(type):
        def __init__(cls, name, bases, classdict):
            for k, v in classdict.items():
                if isinstance(v, Descriptor):
                    v.__set_name__(cls, k)


class Descriptor(object):

    def __set_name__(self, cls, name):
        self.owner = cls
        self.name = name
