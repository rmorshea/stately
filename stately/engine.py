import six
import inspect
from contextlib import contextmanager

if six.PY3:
    import asyncio


class EngineConstructor(type):

    def __init__(cls, name, bases, classdict):
        cls._cycle = []
        rotation = cls.next_rotation(None)
        while rotation is not None:
            cls._cycle.append(rotation)
            rotation = cls.next_rotation(rotation)

    def next_rotation(cls, rotation):
        for c in cls.mro():
            if hasattr(c, "blueprint") and rotation in c.blueprint:
                return c.blueprint[rotation]


class Engine(object, metaclass=EngineConstructor):

    status = None
    blueprint = {None: None}

    @property
    def cycle(self):
        return self._cycle[:]

    def crank(self, *args, **kwargs):
        generator = self(*args, **kwargs)
        def turn(*data):
            return generator.send(data)
        next(generator)
        return turn

    if six.PY3:

        async def future(self, *args, **kwargs):
            outcome = []
            for result in self(*args, **kwargs):
                if inspect.iscoroutine(result):
                    result = await result
                outcome.append(result)
            return outcome

    def __call__(self, *args, **kwargs):
        if self.status is None:
            for status in self.cycle:
                self.status = status
                method = getattr(self, status, None)
                if method is not None:
                    args = ((yield method(*args, **kwargs)) or args)
            self.status = None
        else:
            raise RuntimeError("%r is already in progress." % self)


def between(after, before):
    frame = inspect.currentframe().f_back
    frame.f_locals.setdefault("blueprint", {})
    blueprint = frame.f_locals["blueprint"]

    def setup(method):
        name = method.__name__
        blueprint[after] = method.__name__
        blueprint[method.__name__] = before
        return method

    return setup


def after(name):
    frame = inspect.currentframe().f_back
    frame.f_locals.setdefault("blueprint", {})
    blueprint = frame.f_locals["blueprint"]

    def setup(method):
        blueprint[name] = method.__name__
        return method

    return setup


def before(name):
    frame = inspect.currentframe().f_back
    frame.f_locals.setdefault("blueprint", {})
    blueprint = frame.f_locals["blueprint"]

    def setup(method):
        blueprint[method.__name__] = name
        return method

    return setup


def _after(blueprint, name, method):
    blueprint[name] = method


def _before(blueprint, name, method):
    blueprint[method] = name


def run(engine, *args, **kwargs):
    result = None
    for _result in engine(*args, **kwargs):
        if _result is not None:
            result = _result
    return result


@contextmanager
def locked(engine):
    hold = lock(engine)
    try:
        yield
    except:
        raise
    finally:
        unlock(engine, hold)


def lock(engine):
    hold = engine.__class__
    engine.__class__ = Locker
    return hold

def unlock(engine, etype):
    engine.__dict__["__class__"] = etype


class Locker(object):

    def __setattr__(self, name, value):
        raise AttributeError("%r has been locked" % self)

    def __delattr__(self, name):
        raise AttributeError("%r has been locked" % self)
