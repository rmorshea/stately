from .misc import Descriptor, Sentinel
from .actions import Stage, before, after


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Sentinels And Exceptions  - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


Undefined = Sentinel("Undefined", "no value")


class TraitError(Exception):
    """An error that concerns a :class:`Trait`"""
    pass


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Base Event Method - - - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class Event(Stage):

    order = {
        None: "pending",
        "pending": "forming",
        "forming": "working",
        "working": "done",
        "done": None
    }

    def __init__(self, trait):
        super(Event, self).__init__()
        self._trait = trait
        self.name = trait.name

    def __call__(self, instance, *args, **kwargs):
        self.instance = instance
        return super(Event, self).__call__(instance, *args, **kwargs)

    def rollback(self):
        """If possible, rollback changes incured by this event."""
        pass

    def __str__(self):
        return "%s.%s(%s)" % (
            type(self._trait).__name__, type(self).__name__,
            self._trait.owner.__name__ + "." + self.name)

    @property
    def data(self):
        return Bunch(self, type=type(self))

    @classmethod
    def event_types(cls):
        for c in cls.mro():
            if issubclass(c, Event):
                yield c


class Trait(Descriptor):

    def __init__(self):
        self.tags = {}

    def default(self, instance, state):
        pass

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

    def __set__(self, obj, value):
        return self.cause_event("Set", obj, value)

    def __delete__(self, obj):
        return self.cause_event("Del", obj)

    def cause_event(self, name, instance, *args, **kwargs):
        return instance.actualize_event(getattr(self, name)(self), *args, **kwargs)

    class Set(Event):

        def forming(self, instance, value):
            self.old = instance._state_object.get(self.name, Undefined)
            self._value = value

        def working(self, instance, value):
            instance._state_object[self.name] = self._value

        def done(self, instance, value):
            self.new = instance._state_object[self.name]

        def rollback(self):
            if self.old is Undefined:
                del self.instance._state_object[self.name]
            else:
                self.instance._state_object[self.name] = self.old

    class Del(Event):

        def forming(self, instance):
            # will fail at 'working' status if old is Undefined
            self.old = instance._state_object.get(self.name, Undefined)

        def working(self, instance):
            del instance._state_object[self.name]

        def rollback(self):
            if self.status not in ("pending", "forming"):
                self.instance._state_object[self.name] = self.old

    def __repr__(self):
        return "%s(%r)" % (type(self).__name__, self.owner.__name__ + "." + self.name)


class Data(Trait):

    klass = None
    mutable = True
    static_default = Undefined

    def __init__(self, default=Undefined, mutable=None):
        if default is not Undefined:
            self.static_default = default
        if mutable is not None:
            self.mutable = mutable
        super(Data, self).__init__()

    def default(self, instance, state):
        if self.static_default is not Undefined:
            state[self.name] = self.static_default

    def validate(self, value):
        value = self.coerce(value)
        self.validate(value)
        return value

    def coerce(self, value):
        return value

    def authenticate(self, value):
        pass

    class Set(Trait.Set):

        def forming(self, instance, value):
            if self._trait.mutable:
                value = self._trait.validate(value)
                super(Data.Set, self).forming(instance, value)
            else:
                raise RuntimeError("The trait %r is not mutable" % self._trait)
