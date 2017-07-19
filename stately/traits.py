import functools
from warnings import WarningMessage
from contextlib import contextmanager

from .utils import describe, describe_them, conjunction

from .base.proxies import ProxyManyDescriptors
from .base.events import EventModel, before, after, between
from .base.model import ObjectModel, TraitModel, TraitError, Undefined


# ---------------------------------------------------------------
# Trait Descriptor, Event, and Owner -----------------------------
# ---------------------------------------------------------------


class RollbackWarning(WarningMessage):
    """A warning which is raised when a trait event fails to revert changes"""
    pass


class Event(EventModel):

    def __init__(self, trait, **attrs):
        super(Event, self).__init__(trait=trait, name=trait.name, **attrs)
        self.trait = trait

    def model(self, obj):
        return self.trait.model(obj)


class HasTraits(ObjectModel):

    @contextmanager
    def delayed_events(self, *include):
        with self.intercepted_events(*include) as hold:
            yield hold
        done = []
        try:
            for event in hold:
                self.actualize_event(event)
                done.append(event)
        except Exception as failure:
            try:
                event.rollback(self)
            except Exception as error:
                # because this event failed to resolve, it may not be
                # able to properly rollback, thus we warn, not raise.
                warn("The event %r caused an exception and failed to "
                    "rollback - %s" % (event, error), RollbackWarning)
            for completed_event in done[::-1]:
                completed_event.rollback(self)
            raise failure

    @contextmanager
    def intercepted_events(self, *include):
        queue = []
        _actualize_event = self.actualize_event
        def hold(event):
            if include and not isinstance(event, include):
                return _actualize_event(event)
            else:
                queue.append(event)
        self.actualize_event = hold
        try:
            yield queue
        except:
            raise
        finally:
            del self.actualize_event

    def actualize_event(self, event):
        raise NotImplementedError("HasTraits subclasses "
            "must define how they will handle events.")


class Trait(TraitModel):

    def validate(self, obj, val):
        if self.can_coerce(obj, val):
            value = self.coerce(obj, val)
        self.authorize(obj, val)
        return val

    def can_coerce(self, obj, val):
        return False

    def coerce(self, obj, val):
        raise NotImplementedError()

    def authorize(self, obj, val):
        pass

    def set_value(self, obj, val):
        self.event_outcome("Set", obj, new=val)

    def del_value(self, obj):
        self.event_outcome("Del", obj)

    def event_outcome(self, name, obj, **attrs):
        return obj.actualize_event(self.event(name, **attrs))

    def event(self, name, **attrs):
        etype = getattr(self, name)
        if not issubclass(etype, Event):
            raise TypeError("%r is not an Event of %s." % (name, describe("a", self)))
        return etype(self, **attrs)

    class Set(Event):

        subtypename = "set"

        def pending(self, obj):
            self.old = self.model(obj).get(self.name, Undefined)

        @between("pending", "working")
        def validating(self, obj):
            self.new = self.trait.validate(obj, self.new)

        def working(self, obj):
            self.model(obj)[self.name] = self.new

        def rollback(self, obj):
            if self.old is not Undefined:
                self.model(obj)[self.name] = self.old

    class Del(Event):

        subtypename = "del"

        def pending(self, obj):
            self.old = self.model(obj).get(self.name, Undefined)

        def working(self, obj):
            del self.model(obj)[self.name]

        def rollback(self, obj):
            if self.old is not Undefined:
                self.model(obj)[self.name] = self.old

    def __or__(self, other):
        if isinstance(other, Union):
            return Union(self, *other.descriptors)
        elif isinstance(other, Trait):
            return Union(self, other)
        else:
            raise TypeError("Cannot form a Union between non-Trait types")


# ---------------------------------------------------------------
# Basic Trait Subclasses -----------------------------------------
# ---------------------------------------------------------------


class Union(ProxyManyDescriptors):
    
    def __or__(self, other):
        if isinstance(other, Trait):
            return Union(*(self.descriptors + other.descriptors))
        elif isinstance(other, Trait):
            return Union(*(self.descriptors + (other,)))
        else:
            raise TypeError("Cannot form a Union between non-Trait types")


class Type(Trait):

    datatype = None

    def __init__(self, datatype=None, *args, **kwargs):
        super(Type, self).__init__(*args, **kwargs)
        if datatype is not None:
            if self.datatype is None or issubclass(datatype, self.datatype):
                self.datatype = datatype
            else:
                raise TypeError("%s is not a subclass of %s" % (describe("A", datatype), describe("the", self.datatype)))
        elif self.datatype is None:
            raise TypeError("%s has no given 'datatype'" % describe("The", type(self)))

    def constructor(self, *args, **kwargs):
        datatype = self.datatype
        if isinstance(datatype, tuple):
            datatype = datatype[0] 
        return datatype(*args, **kwargs)

    def info(self):
        if isinstance(self.datatype, tuple):
            text = conjunction("or", *describe_them("a", self.datatype))
        else:
            text = describe("a", self.datatype)
        if self.allow_none:
            text = "None, " + text
        return text



class Subclass(Type):

    def authorize(self, obj, val):
        if not issubclass(val, self.datatype):
            msg = "%s's %r attribute can be %s, not %s"
            raise TraitError(msg % (describe("An", obj, "object"),
                self.name, describe("a", self.datatype, "subclass"),
                describe("the", val)))


class Instance(Type):

    def authorize(self, obj, val):
        if not isinstance(val, self.datatype):
            msg = "%s's %r attribute can be %s, not %s"
            raise TraitError(msg % (describe("An", obj, "object"),
                self.name, describe("a", self.datatype),
                describe("the", val)))


class This(Instance):

    constructor = "__class__"
