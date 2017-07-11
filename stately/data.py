from warnings import WarningMessage
from contextlib import contextmanager

from .base.proxies import ProxyManyDescriptors
from .base.events import Event, before, after, between
from .base.model import ObjectModel, DataModel, DataError, Undefined


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Data Descriptor And Owner - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class RollbackWarning(WarningMessage):
    """A warning which is raised when a data event fails to revert changes"""
    pass


class HasData(ObjectModel):

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
        raise NotImplementedError("HasData subclasses "
            "must define how they will handle events.")


class Data(DataModel):

    def validate(self, value):
        if self.can_coerce(value):
            value = self.coerce(value)
        self.authorize(value)
        return value

    def can_coerce(self, value):
        return False

    def coerce(self, value):
        raise NotImplementedError()

    def authorize(self, value):
        pass

    def __set__(self, obj, val):
        self.event_outcome("Set", obj, new=val)

    def __delete__(self, obj):
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
            self.old = self.get_value_or(obj, Undefined)

        @between("pending", "working")
        def validating(self, obj):
            self.new = self.data.validate(self.new)

        def working(self, obj):
            self.set_value(obj, self.new)

        def rollback(self, obj):
            if self.old is not Undefined:
                self.set_value(obj, self.old)

    class Del(Event):

        subtypename = "del"

        def pending(self, obj):
            self.old = self.get_value_or(obj, Undefined)

        def working(self, obj):
            self.del_value(obj)

        def rollback(self, obj):
            if self.old is not Undefined:
                self.set_value(obj, self.old)

    def __or__(self, other):
        if isinstance(other, Union):
            return Union(self, *other._descriptors)
        elif isinstance(other, Data):
            return Union(self, other)
        else:
            raise TypeError("Cannot form a Union between non-Data types")


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Basic Data Subclasses - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class Union(ProxyManyDescriptors, DataModel):

    def __init__(self, *data, **kwargs):
        super(Union, self).__init__(*data, **kwargs)
    
    def __or__(self, other):
        if isinstance(other, Data):
            return Union(*(self._descriptors + other._descriptors))
        elif isinstance(other, Data):
            return Union(*(self._descriptors + (other,)))
        else:
            raise TypeError("Cannot form a Union between non-Data types")


class DataType(Data):

    datatype = None

    def __init__(self, datatype=None, *args, **kwargs):
        super(DataType, self).__init__(*args, **kwargs)
        if datatype is not None:
            if self.datatype is None or issubclass(datatype, self.datatype):
                self.datatype = datatype
            else:
                raise TypeError("%s is not a subclass of %s" % (describe("A", datatype), describe("the", self.datatype)))
        elif self.datatype is None:
            raise TypeError("%s has no given 'datatype'" % describe("The", type(self)))

    def _constructor(self, *args, **kwargs):
        return self.datatype(*args, **kwargs)


class Subclass(DataType):

    def authorize(self, value):
        if not issubclass(value, self.datatype):
            raise DataError("Expected %s, not %r" % (
                describe("a", self.datatype, "subclass"),
                describe("the", value)))


class Instance(DataType):

    def authorize(self, value):
        if not isinstance(value, self.datatype):
            raise DataError("Expected %s, not %r" % (
                describe("a", self.datatype),
                describe("the", value)))


class This(Instance):

    _constructor = "__class__"
