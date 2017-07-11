import sys
import types
import inspect
from inspect import getmembers
from contextlib import contextmanager
from metasetup import MetaConfigurable, Configurable

from ..utils import describe, Sentinel


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Python < 3.6 - PEP 487 Descriptor Compatibility - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


if sys.version_info >= (3, 6):
    Metaclass = MetaConfigurable
else:
    class Metaclass(MetaConfigurable):
        def __init__(cls, name, bases, classdict):
            super(Metaclass, cls).__init__(name, bases, classdict)
            # we create an attribute here in order
            # to speed up subclass initialization
            cls._has_descriptors = []
            for k, v in classdict.items():
                if isinstance(v, Descriptor):
                    cls._has_descriptors.append(k)
                    v.__set_name__(cls, k)
            for c in cls.mro():
                if hasattr(c, "_has_descriptors"):
                    for name in c._has_descriptors:
                        getattr(c, name).__init_subclass__(cls)


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Base Object For Descriptors - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class Descriptor(object):

    def __set_name__(self, cls, name):
        self.owner = cls
        self.name = name

    def __init_subclass__(self, cls):
        pass

    def __init_instance__(self, obj):
        pass


class HasDescriptors(Configurable, metaclass=Metaclass):

    def __init__(self):
        for k, v in getmembers(type(self)):
            if isinstance(v, Descriptor):
                v.__init_instance__(self)



Undefined = Sentinel("Undefined", "no value")


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Data Descriptor Owner Base - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class ObjectModel(HasDescriptors):

    def __init__(self, model=None):
        if isinstance(model, ObjectModel):
            model = model._object_model
        self._object_model = model or {}
        super(ObjectModel, self).__init__()

    @classmethod
    def has_data(cls, name):
        return isinstance(getattr(cls, name, None), DataModel)

    def has_data_value(self, name):
        return name in self._object_model
    
    @classmethod
    def data_names(cls, **tags):
        result = []
        for k, v in inspect.getmembers(cls):
            if isinstance(v, DataModel) and v.tags_match(**tags):
                result.append(k)
        return result
    
    @classmethod
    def data_defaults(cls, **tags):
        model = {}
        for k, t in cls.data(**tags).items():
            default = t.default
            if default is not Undefined:
                model[k] = default
        return state
    
    @classmethod
    def data(cls, **tags):
        result = {}
        for k, v in inspect.getmembers(cls):
            if isinstance(v, DataModel) and v.tags_match(**tags):
                result[k] = v
        return result


# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -
# Base Data Descriptor  - - - - - - - - - - - - - - - - - - - - -
# - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - - -


class DataError(Exception):
    """An error raise in relation to a DataModel"""
    pass


class DataModel(Descriptor):

    writable = True
    documentation = ""
    _constructor = None
    _constructor_args = ()
    _constructor_kwargs = {}
    _default = Undefined

    def __init__(self, default=Undefined, constructor=None, writable=None):
        if default is not Undefined:
            self._default = default
        if constructor is not None:
            if not (callable(constructor) or isinstance(constructor, str)):
                raise TypeError("A 'constructor' must be callable or string.")
            self._constructor = constructor
        if writable is not None:
            self.writable = writable
        self.tags = {}

    def docs(self, text):
        self.documentation = text
        return self

    def __call__(self, *args, **kwargs):
        self._constructor_args = args
        self._constructor_kwargs = kwargs
        return self

    def default(self, obj=None):
        if self._default is Undefined and self._constructor is not None:
            if obj is not None and isinstance(self._constructor, str):
                constructor =  getattr(obj, self._constructor)
            else:
                constructor = self._constructor
            return constructor(*self._constructor_args, **self._constructor_kwargs)
        else:
            return self._default

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
        try:
            return obj._object_model[self.name]
        except KeyError:
            # just in time default generation generally
            # occurs when data is required to generate
            # the default of some other data
            default = self.default(obj)
            self.set_value(obj, default)
            return default

    def set_value(self, obj, val):
        if self.writable:
            obj._object_model[self.name] = val
        else:
            raise DataError("Data for the attribute %r of %s is not writable"
                % (self.name, describe("an", obj)))

    def del_value(self, obj):
        if self.writable:
            del obj._object_model[self.name]
        else:
            raise DataError("Data for the attribute %r of %s is not writable"
                % (self.name, describe("an", obj)))

    def get_value_or(self, obj, default):
        return obj._object_model.get(self.name, default)
