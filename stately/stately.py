import types

from .base.model import Descriptor
from .utils import Sentinel, describe, decoration
from .data import HasData, Data, Event


# ---------------------------------------------------------------
# Helpers -------------------------------------------------------
# ---------------------------------------------------------------


def parse_data_names(owner, names, tags=None):
    if names is All:
        return owner.data_names(**(tags or {}))
    elif isinstance(names, str):
        names = [names]
    if isinstance(names, dict):
        return owner.data_names(**names)
    for n in names:
        if not owner.has_data(n):
            raise DataError("%s has no data named %r" % (describe("the", owner), n))
    return names


def parse_typenames(typenames):
    if typenames is All:
        return [Event.typename]
    elif isinstance(typenames, str):
        return [typenames]
    elif isinstance(typenames, (list, tuple)):
        return [Event.typename] if All in typenames else typenames
    else:
        raise TypeError("Expected a list, str, or All, not %r" % typenames)


def parse_statuses(statuses):
    if statuses is None or isinstance(statuses, str):
        return [statuses]
    elif isinstance(statuses, (list, tuple)):
        return statuses
    else:
        raise TypeError("Expected a str, list, or None, not %r" % statuses)


# ---------------------------------------------------------------
# Sentinels -----------------------------------------------------
# ---------------------------------------------------------------


All = Sentinel("All", "all values")


# ---------------------------------------------------------------
# Main Stately Object -------------------------------------------
# ---------------------------------------------------------------


class Stately(HasData):

    def __init__(self, *args, **kwargs):
        self._observers = ObserverMapping()
        super(Stately, self).__init__(*args, **kwargs)

    def observe(self, names=All, typenames=All, statuses=None, observer=None):

        def setup(observer):
            for n in parse_data_names(self, names):
                for t in parse_typenames(typenames):
                    for s in parse_statuses(statuses):
                        self._observers.add(n, t, s, observer)
            return observer

        if observer is not None:
            return setup(observer)
        else:
            return setup

    def condition(self, condition=None, **kwargs):

        def setup(condition):
            return Condition(condition, **kwargs).__get__(self, type(self))

        if condition is not None:
            return setup(condition)
        else:
            return setup

    def observers(self, name=All, etype=All, status=None):
        return [o for c, o in self._observers.get_by_components(name, etype, status)]

    def actualize_event(self, event):
        result = None
        for _result in event(self):
            self._event_advanced(event)
            if _result is not None:
                result = _result
        self._event_advanced(event)
        return result

    def _event_advanced(self, event):
        for observer in self._observers.get(event):
            # we avoid using the `locked` context
            # manager due to unnecessary overhead
            observer(self, event)


# ---------------------------------------------------------------
# Stately Decorators --------------------------------------------
# ---------------------------------------------------------------


class Condition(Descriptor):

    def __init__(self, method, **options):
        self.method = method
        self.options = options

    def __call__(self, *args, **kwargs):
        return self.method(*args, **kwargs)

    def bind(self, obj):
        return self.__get__(obj, obj.__class__)

    def __get__(self, obj, cls):
        if obj is not None:
            return types.MethodType(self.observe, obj)
        else:
            return self

    def observe(self, obj, *args, **kwargs):

        observe = obj.observe(*args, **dict(self.options, **kwargs))

        def setup(callback):
            return observe(Observer(callback, self.method))

        return setup


condition = decoration(Condition)


class Observer(Descriptor):

    def __init__(self, callback, condition, *args, **kwargs):
        if condition is All:
            condition = None
        if isinstance(callback, str):
            _callback = callback
            def callback(owner, event):
                return getattr(owner.__class__, _callback)(owner, event)
        if isinstance(condition, str):
            _condition = condition
            def condition(owner, event):
                return getattr(owner.__class__, _condition)(owner, event)
        self.callback = callback
        self.condition = condition
        self.args = args
        self.kwargs = kwargs

    def __get__(self, obj, cls):
        if obj is not None:
            return types.MethodType(self.callback, obj)
        else:
            return self

    def __call__(self, *args, **kwargs):
        if self.condition is None or self.condition(*args, **kwargs):
            return self.callback(*args, **kwargs)

    def __eq__(self, other):
        if isinstance(other, Observer):
            return other.condition == self.condition and self.callback == other.callback
        else:
            condition, callback = other
            return condition == self.condition and callback == self.callback

    def __init_instance__(self, obj):
        obj.observe(*self.args, **self.kwargs)(self)


observe = decoration(Observer)


# ---------------------------------------------------------------
# Observer Storage ----------------------------------------------
# ---------------------------------------------------------------


class ObserverMapping(object):

    def __init__(self):
        self.mapping = {}
        self.inversion = {}

    def add(self, name, typename, status, observer):
        mapping = self.mapping
        mapping.setdefault(typename, {})
        mapping[typename].setdefault(name, {})
        mapping[typename][name].setdefault(status, [])
        if observer not in mapping[typename][name][status]:
            mapping[typename][name][status].append(observer)
        self.inversion.setdefault(id(observer), [])
        self.inversion[id(observer)].append((name, typename, status))

    def get(self, event):
        return self.get_by_components(*self._to_components(event))

    def get_by_components(self, name, typenames, status):
        result = []
        mapping = self.mapping
        for typename in typenames:
            result.extend(mapping.get(typename, {}).get(name, {}).get(status, []))
        return result

    def delete(self, observer):
        for n, t, s in self.inversion(id(observer)):
            self.delete_by_components(n, t, s, observer)

    def delete_by_components(self, name, typename, status, observer=None):
        tmap = self.mapping
        try:
            nmap = tmap[typename]
            smap = nmap[name]
            l = smap[status]
        except KeyError:
            pass
        else:
            try:
                if observer is None:
                    del l[:]
                else:
                    l.remove(observer)
            except ValueError:
                pass
            else:
                # clean up after the deletion
                if len(l) == 0:
                    del nmap[status]
                    if len(nmap) == 0:
                        del tmap[name]

    def _to_components(self, event):
        return event.data.name, event.typename_lineage, event.status
