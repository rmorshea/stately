import sys
import inspect
from .descriptions import describe


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


class Bunch(dict):
    """A dict with attribute access"""

    def __contains__(self, key):
        return hasattr(self, key)

    def __getattr__(self, key):
        try:
            return self.__getitem__(key)
        except KeyError:
            raise AttributeError(key)
    
    def __setattr__(self, key, value):
        self.__setitem__(key, value)
    
    def __dir__(self):
        names = dir(type(self))
        names.extend(self.keys())
        return names
