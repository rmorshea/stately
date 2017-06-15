import types
import inspect
import functools
from contextlib import contextmanager
from warnings import warn, WarningMessage

from .traits import Trait, Undefined, Event
from .misc import Metaclass, Sentinel, Bunch, describe


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Sentinels And Exceptions  - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


All = Sentinel("All", "all values")


class RollbackWarning(WarningMessage):
    """A warning which is raised when a trait event fails to revert changes"""
    pass


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Helpers - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def parse_trait_names(owner, names, tags=None):
    if names is All:
        return owner.trait_names(**(tags or {}))
    elif isinstance(names, str):
        names = [names]
    for n in names:
        if not owner.has_trait(n):
            raise TraitError("%s has no trait named %r" % (describe("the", owner), n))
    return names


def condition(method=None, **options):
    def setup(method):
        return Condition(method, **options)
    if method is not None:
        return setup(method)
    else:
        return setup


class Condition(object):

    def __init__(self, method, **options):
        self.method, self.options = method, options

    def get(self, obj):
        return self.__get__(obj, type(obj))

    def __get__(self, obj, cls):
        if obj is None:
            return self
        else:
            return types.MethodType(self.__call__, obj)

    def __call__(self, instance, *args, **kwargs):
        if isinstance(self.method, classmethod):
            condition = types.MethodType(self.method, type(self))
        elif not isinstance(self.method, staticmethod):
            condition = types.MethodType(self.method, self)
        else:
            condition = self.method
        return instance.on(condition=condition,
            *args, **dict(self.options, **kwargs))

    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.method)


class ObserverMapping(object):

    def __init__(self):
        self._mapping = {}
        self._statuses = set()
        self._types = set()
        self._names = set()

    def add(self, name, etype, status, condition, callback):
        m = self._mapping
        m.setdefault(status, {})
        m[status].setdefault(name, {})
        m[status][name].setdefault(etype, [])
        l = m[status][name][etype]
        conditional_callback = (condition, callback)
        if conditional_callback not in l:
            l.append(conditional_callback)
            self._added(name, etype, status)

    def _added(self, name, etype, status):
        self._names.add(name)
        self._types.add(etype)
        self._statuses.add(status)

    def get(self, event):
        result = []
        s, n, e = self._to_components(event)
        type_mapping = self._mapping.get(s, {}).get(n, {})
        if len(type_mapping):
            for cls in e.event_types():
                result.extend(type_mapping.get(cls, []))
        return result

    def delete(self, event, condition=None, callback=None):
        pass


    def has(self, event):
        return self._has(*self._to_components(event))

    def _has(self, name, etype, status):
        return status in self._statuses and name in self._names and issubclass(etype, tuple(self._types))

    @staticmethod
    def _to_components(event):
        return event.name, type(event), event.status


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Main Stately Object - - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class Stately(object, metaclass=Metaclass):

    def __init__(self):
        self._observers = ObserverMapping()
        self.initialize_state()

    def initialize_state(self):
        state = {}
        self._state_object = state
        for k, t in self.traits().items():
            t.default(self, state)

    def __getattr__(self, name):
        try:
            self._state_object[name]
        except:
            raise AttributeError("%s has no attribute %r" % (
                describe("the", self, capital=True), name))

    @classmethod
    def traits(cls, **tags):
        result = {}
        for k, v in inspect.getmembers(cls):
            if isinstance(v, Trait) and v.tags_match(**tags):
                result[k] = v
        return result

    @classmethod
    def has_trait(cls, name):
        return isinstance(getattr(cls, name, None), Trait)

    @classmethod
    def trait_names(cls, **tags):
        result = []
        for k, v in inspect.getmembers(cls):
            if isinstance(v, Trait) and v.tags_match(**tags):
                result.append(k)
        return result

    def trait_values(self, **tags):
        return {k: self._state_object[k] for k in self.trait_names(**tags)}

    def update(self, **attributes):
        with self.postponed_events():
            for k, v in attributes.items():
                if not self.has_trait(k):
                    raise TraitError("%s has no trait %r" (describe("the", self), k))
                else:
                    setattr(self, k, v)

    def on(self, names=All, etype=Event, status="done", condition=None, callback=None):

        if etype is All:
            etype = Event

        if callable(names):
            names, callback = All, names
        names = parse_trait_names(self, names)

        def setup(callback):
            for name in names:
                self._observers.add(name, etype, status, condition, callback)
            return callback

        if callback is not None:
            return setup(callback)
        else:
            return setup

    def condition(self, function=None, **options):
        def setup(function):
            return Condition(function, **options).get(self)
        if function is not None:
            return setup(function)
        else:
            return setup

    def observers(self, name=All, etype=All, status=All):
        return [observer for observer, condition in self._observers.get(name, etype, status)]

    @contextmanager
    def postponed_events(self, *include):
        with self.intercepted_events(*include) as hold:
            yield hold
        done = []
        try:
            for event in hold:
                self.perform_event(event)
                done.append(event)
        except:
            try:
                event.rollback()
            except Exception as error:
                warn("The event %r caused an exception and failed to "
                    "rollback - %s" % (event, error), RollbackWarning)
            for event in done[::-1]:
                try:
                    event.rollback()
                except Exception as error:
                    raise RuntimeError("Failed to rollback %s - %s" % (event, error))

    @contextmanager
    def intercepted_events(self, *include):
        queue = []
        def hold(event):
            if include and not isinstance(event, include):
                return type(self).perform_event(self, event)
            else:
                queue.append(event)
        self.perform_event = hold
        try:
            yield queue
        except:
            raise
        finally:
            del self.perform_event

    def actualize_event(self, event, *args, **kwargs):
        result = None
        for _result in event(self, *args, **kwargs):
            self.event_occurance(event)
            if _result is not None:
                result = _result
        return result

    def event_occurance(self, event):
        for observer, rule in self._observers.get(event):
            if not callable(rule) or rule(event.data):
                observer(event.data)

    # @contextmanager
    # def staged_execution(self, *include):
    #     with self.intercepted_stages(*include) as stages:
    #         yield
    #     for s in stages:
    #         # an error at any stage will prevent all
    #         # those following it from being executed
    #         pass

    # @contextmanager
    # def intercepted_stages(self, *include):

    #     def is_parent(cls, cls_or_tuple):
    #         if isinstance(cls_or_tuple, tuple):
    #             cls_or_tuple = (cls_or_tuple,)
    #         for c in cls_or_tuple:
    #             if not issubclass(cls, c):
    #                 return False
    #         else:
    #             return True

    #     def yield_stage(event, status):
    #         return is_parent(type(event), include) and status != event.status

    #     with self.intercepted_events(*include) as events:
    #         def staging(events):
    #             yield list(events)
    #             generators = [e(self) for e in events]
    #             while len(events):
    #                 result = []
    #                 for i in range(len(generators)):
    #                     g = generators[len(result)]
    #                     e = events[len(result)]
    #                     try:
    #                         status = e.status
    #                         while not yield_stage(e, status):
    #                             next(g)
    #                     except StopIteration:
    #                         del generators[len(result)]
    #                         del events[len(result)]
    #                     else:
    #                         result.append(dict(e))
    #                 if result:
    #                     yield result
    #         yield staging(events)
