import six
import inspect
from .misc import Metaclass, Descriptor

class Action(object):

    order = {None: None}
    passover = []

    def __init__(self):
        self._statuses = []
        state = self.after(None)
        while state is not None:
            self._statuses.append(state)
            state = self.after(state)

    @property
    def statuses(self):
        return self._statuses[:]

    @classmethod
    def after(cls, state):
        for c in cls.mro():
            if state in getattr(c, "order", ()):
                return c.order[state]

    def __call__(self, *args, **kwargs):
        self.status = None
        for s in self.statuses:
            self.status = s
            method = getattr(self, s, None)
            if method is not None:
                yield method(*args, **kwargs)
        self.status = None


if six.PY3:
    
    import asyncio

    class AsyncAction(Action):

        def __call__(self, *args, **kwargs):
            for result in super().__call__(*args, **kwargs):
                if inspect.iscoroutine(result):
                    asyncio.get_event_loop().create_task(result)
                yield result


def between(after, before):
    frame = inspect.currentframe().f_back
    frame.f_locals.setdefault("order", {})
    order = frame.f_locals["order"]

    def setup(method):
        name = method.__name__
        order[after] = method.__name__
        order[method.__name__] = before
        return method

    return setup


def after(name):
    frame = inspect.currentframe().f_back
    frame.f_locals.setdefault("order", {})
    order = frame.f_locals["order"]

    def setup(method):
        order[name] = method.__name__
        return method

    return setup


def _after(order, name, method):
    order[name] = method


def before(name):
    frame = inspect.currentframe().f_back
    frame.f_locals.setdefault("order", {})
    order = frame.f_locals["order"]

    def setup(method):
        order[method.__name__] = name
        return method

    return setup


def _before(order, name, method):
    order[method] = name


class Stage(Action):
    """A simple class for managing the state of an :class:`Action`

    All public attributes (those without a preceding "_") that
    are defined after the creation of an instance can be parsed
    into a dictionary by wrapping a :class:`Stage` with ``dict``
    (e.g ``dict(my_event)``). However those same attributes and
    value pairs can also be iterated over with ``iter``.

    Notes
    -----
    The names of attributes that are to be ignored when iterating
    are stored in the `Stage._reserved` attribute of each instance.
    """

    def __new__(cls, *args, **kwargs):
        new = super(Stage, cls).__new__
        if new is not object.__new__:
            self = new(cls, *args, **kwargs)
        else:
            self = new(cls)
        self._reserved = []
        self._reserved.extend(dir(self))
        return self

    def __iter__(self):
        """iterator over non-reserved attributes and their values"""
        return ((n, getattr(self, n)) for n in
            dir(self) if n not in self._reserved
            and not n.startswith("_"))

    def __repr__(self):
        """Returns a simple representation of the event's state"""
        c = type(self).__name__
        d = repr(dict(self))[1:-1]
        return c + "(" + d + ")"
