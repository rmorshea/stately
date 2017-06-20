import sys
import types
import inspect

from .engine import Engine
from .utils import describe, Sentinel, Metaclass, Descriptor


Undefined = Sentinel("Undefined", "no value")


class StateError(Exception):
    """An error raise by a state"""
    pass


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Base Object Has State - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class HasStates(object, metaclass=Metaclass):

    def __init__(self):
        self.force_load_state(self.state_defaults())

    def force_load_state(self, state):
        old = getattr(self, "_state_object", None)
        self._state_object = state
        return old

    @classmethod
    def has_state(cls, name):
        return isinstance(getattr(cls, name, None), State)
    
    def state(self, **tags):
        return {k: self._state_object[k] for k in self.state_names(**tags)}
    
    @classmethod
    def state_names(cls, **tags):
        result = []
        for k, v in inspect.getmembers(cls):
            if isinstance(v, BaseState) and v.tags_match(**tags):
                result.append(k)
        return result
    
    @classmethod
    def state_defaults(cls, **tags):
        state = {}
        for k, t in cls.states(**tags).items():
            t.default(state)
        return state
    
    @classmethod
    def states(cls, **tags):
        result = {}
        for k, v in inspect.getmembers(cls):
            if isinstance(v, State) and v.tags_match(**tags):
                result[k] = v
        return result


class State(Descriptor):

    mutable = True
    static_default = Undefined

    def __init__(self, default=Undefined, mutable=None):
        if default is not Undefined:
            self.static_default = default
        if mutable is not None:
            self.mutable = mutable
        self.tags = {}

    def instance_init(self, instance):
        self.default(instance._state_object)

    def default(self, state):
        if self.static_default is not Undefined:
            state[self.name] = self.static_default

    def tag(self, **metadata):
        self.tags.update(**metadata)
        return self

    def tags_match(self, **tags):
        my_tags = self.tags
        for k, v in tags.items():
            if not (k in my_tags and (v(my_tags[k]) if callable(v) else v == my_tags)):
                return False
        else:
            return True

    def __get__(self, obj, cls):
        return self if obj is None else self.get_value(obj)

    def __set__(self, obj, val):
        self.set_value(obj, val)

    def __delete__(self, obj):
        self.del_value(obj)

    def get_value(self, obj):
        return obj._state_object[self.name]

    def set_value(self, obj, val):
        if self.mutable:
            obj._state_object[self.name] = val
        else:
            raise StateError("The state %r of %s is not mutable"
                % (self.name, describe("an", obj)))

    def del_value(self, obj):
        if self.mutable:
            del obj._state_object[self.name]
        else:
            raise StateError("The state %r of %s is not mutable"
                % (self.name, describe("an", obj)))

    def get_value_or(self, obj, default):
        return obj._state_object.get(self.name, default)


class Event(Engine):
    
    blueprint = {
        None: "pending",
        "pending": "working",
        "working": "done",
        "done": None
    }

    def __init__(self, state):
        self.state = state
        if isinstance(self.state_names, str):
            self.state_names = (self.state_names,)

    @property
    def get_value(self):
        return self.state.get_value

    @property
    def set_value(self):
        return self.state.set_value

    @property
    def del_value(self):
        return self.state.del_value

    @property
    def get_value_or(self):
        return self.state.get_value_or

    def rollback(self):
        pass
