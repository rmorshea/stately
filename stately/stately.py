import types
import inspect
import functools
from contextlib import contextmanager
from warnings import warn, WarningMessage

from .base import State, HasStates, Undefined, StateError, Event
from .engine import before, after, between, lock, unlock, locked
from .utils import Sentinel, describe


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Sentinels And Exceptions  - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


All = Sentinel("All", "all values")


class RollbackWarning(WarningMessage):
    """A warning which is raised when a state event fails to revert changes"""
    pass


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Main Stately Object - - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class Stately(HasStates):

    def __init__(self):
        self._observers = ObserverMapping()
        super(Stately, self).__init__()

    def on(self, names=All, etype=All, status=None, condition=None, callback=None):

        if etype is All:
            etype = Event

        if callable(names):
            names, callback = All, names
        names = parse_state_names(self, names)

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

    def observers(self, name=All, etype=All, status=None):
        return [o for c, o in self._observers.get_by_components(name, etype, status)]

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
            self._event_advanced(event)
            if _result is not None:
                result = _result
        self._event_advanced(event)
        return result

    def _event_advanced(self, event):
        for rule, observer in self._observers.get(event):
            if rule is None or rule(event):
                # we avoid using the `locked` context
                # manager due to unnecessary overhead
                hold = lock(event)
                observer(event)
                unlock(event, hold)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Stately Data  - - - - - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class Data(State):

    def validate(self, value):
        value = self.coerce(value)
        self.authorize(value)
        return value

    def coerce(self, value):
        return value

    def authorize(self, value):
        pass

    def __set__(self, obj, val):
        self.event_outcome("Set", obj, val)

    def __delete__(self, obj):
        self.event_outcome("Del", obj)

    def event_outcome(self, name, obj, *args, **kwargs):
        return obj.actualize_event(self.event(name), *args, **kwargs)

    def event(self, name, *args, **kwargs):
        return getattr(self, name)(self, *args, **kwargs)

    class Set(Event):

        subtypename = "change"
        state_names = ("new", "old")

        def pending(self, obj, val):
            self.old = self.get_value_or(obj, Undefined)

        @between("pending", "working")
        def validating(self, obj, val):
            self.new = self.state.validate(val)

        def working(self, obj, val):
            self.set_value(obj, self.new)

    class Del(Event):

        subtypename = "deletion"

        def pending(self, obj):
            self.old = self.get_value_or(obj, Undefined)

        def working(self, obj):
            self.del_value(obj)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Helpers - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


def parse_state_names(owner, names, tags=None):
    if names is All:
        return owner.state_names(**(tags or {}))
    elif isinstance(names, str):
        names = [names]
    for n in names:
        if not owner.has_state(n):
            raise StateError("%s has no state named %r" % (describe("the", owner), n))
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
        self.mapping = {}

    def add(self, name, etype, status, condition, callback):
        mapping = self.mapping
        mapping.setdefault(etype, {})
        mapping[etype].setdefault(name, {})
        mapping[etype][name].setdefault(status, [])
        if callback not in mapping[etype][name][status]:
            mapping[etype][name][status].append((condition, callback))

    def get(self, event):
        return self.get_by_components(event.state.name, event.status, type(event))

    def get_by_components(self, name, status, etype):
        result = []
        mapping = self.mapping
        for cls in etype.mro():
            result.extend(mapping.get(cls, {}).get(name, {}).get(status, []))
        return result

    def delete(self, event, condition=None, callback=None):
        pass

    def has(self, event):
        return self.has_by_components(event.state.name, event.status, type(event))

    def has_by_components(self, name, status, etype):
        return (etype in self.mapping and
            name in self.mapping[etype] and
            status in self.mapping[etype][name])
