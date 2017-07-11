import six
import inspect
from contextlib import contextmanager

if six.PY3:
    import asyncio


class MetaEngine(type):

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


class Engine(object, metaclass=MetaEngine):

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


async def run_futures(engine, *args, **kwargs):
    result = None
    for _result in engine(*args, **kwargs):
        if inspect.iscoroutine(_result):
            result = await _result
    return result


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Events Objects  - - - - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class MetaEvent(MetaEngine):

    def __init__(cls, name, bases, classdict):
        super(MetaEvent, cls).__init__(name, bases, classdict)
        if "subtypename" in classdict and classdict["subtypename"] is not None:
            cls.subtypename_lineage = cls.subtypename_lineage + [classdict["subtypename"]]
        cls.typename_lineage = tuple(" ".join(reversed(cls.subtypename_lineage[:i]))
            for i in range(1, len(cls.subtypename_lineage) + 1))
        cls.typename = cls.typename_lineage[-1]


class Event(Engine, metaclass=MetaEvent):
    
    blueprint = {
        None: "pending",
        "pending": "working",
        "working": "done",
        "done": None
    }

    subtypename = "event"
    subtypename_lineage = []

    def __init__(self, data, **attrs):
        self.data = data
        for k, v in attrs.items():
            setattr(self, k, v)

    @property
    def get_value(self):
        return self.data.get_value

    @property
    def set_value(self):
        return self.data.set_value

    @property
    def del_value(self):
        return self.data.del_value

    @property
    def get_value_or(self):
        return self.data.get_value_or

    def rollback(self):
        pass

    def __repr__(self):
        info = {}
        for k, v in self.__dict__.items():
            if not k.startswith("_"):
                info[k] = v
        cls = type(self)
        name = cls.__module__ + "." + cls.__name__
        return "%s(%s)" % (name, str(info)[1:-1])
