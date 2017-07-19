import sys
import types
import inspect
from inspect import getmembers
from contextlib import contextmanager
from metasetup import MetaConfigurable, Configurable, Bunch

from ..utils import describe, Sentinel, decoration


Undefined = Sentinel("Undefined", "no value")


# ---------------------------------------------------------------
# Python < 3.6 - PEP 487 Descriptor Compatibility ---------------
# ---------------------------------------------------------------

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


# ---------------------------------------------------------------
# Base Object For Descriptors -----------------------------------
# ---------------------------------------------------------------


class Descriptor(object):

    def heritage(self, attr):
        """Get an attribute of a descriptor, with the same name, on a parent of my class"""
        for cls in self.owner.mro()[1:]:
            descriptor = getattr(cls, self.name, None)
            if isinstance(descriptor, Descriptor):
                if hasattr(descriptor, attr):
                    return getattr(descriptor, attr)
        else:
            raise AttributeError("There is no descriptor named %r in the lineage "
                "of %r that has an attribute %r." % (self.name, self.owner, attr))

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


# ---------------------------------------------------------------
# Objects Settings Loaders --------------------------------------
# ---------------------------------------------------------------


class Loadable(HasDescriptors):

    loaders = ()

    def __init__(self):
        super(Loadable, self).__init__()

    def loads(self):
        for c in type(self).mro():
            if issubclass(c, Loadable) and "loaders" in vars(c):
                for loader in c.loaders:
                    yield getattr(self, loader)

    def settings(self, *args, **kwargs):
        settings = super(Loadable, self).settings(*args, **kwargs)
        for loader in self.loads():
            subsettings = loader()
            if subsettings is not None:
                settings.merge(subsettings)
        return settings


# ---------------------------------------------------------------
# Trait Descriptor Owner Base ------------------------------------
# ---------------------------------------------------------------


class ObjectModel(Loadable):

    def __init__(self, model=None):
        if isinstance(model, ObjectModel):
            model = model._model
        self._model = model or {}
        super(ObjectModel, self).__init__()

    @classmethod
    def has_trait(cls, name):
        return isinstance(getattr(cls, name, None), TraitModel)

    def trait_values(self, **tags):
        model = {}
        for n in self.trait_names(**tags):
            model[n] = getattr(self, n)
        return model

    def has_trait_value(self, name):
        return name in self._model
    
    @classmethod
    def trait_names(cls, **tags):
        result = []
        for k, v in inspect.getmembers(cls):
            if isinstance(v, TraitModel) and v.has_tags(**tags):
                result.append(k)
        return result
    
    @classmethod
    def trait_defaults(cls, **tags):
        model = {}
        for k, t in cls.traits(**tags).items():
            default = t.default
            if default is not Undefined:
                model[k] = default
        return state
    
    @classmethod
    def traits(cls, **tags):
        result = {}
        for k, v in inspect.getmembers(cls):
            if isinstance(v, TraitModel) and v.tags_match(**tags):
                result[k] = v
        return result


# ---------------------------------------------------------------
# Base Trait Descriptor ------------------------------------------
# ---------------------------------------------------------------


class TraitError(Exception):
    """An error raise in relation to a TraitModel"""
    pass


class TraitModel(Descriptor):

    tags = {
        "writable": True,
        "allow_none": False,
    }

    constructor = None

    def __init__(self, constructor=None, *args, **kwargs):
        if constructor is not None:
            self.constructor = constructor
        self.constructor_args = (args, kwargs)
        self.tags = Bunch(self.__class__.tags)

    def default(self, obj=None):
        if self.constructor is not None:
            args, kwargs = self.constructor_args
            if obj is not None and isinstance(self.constructor, str):
                return getattr(obj, self.constructor)(*args, **kwargs)
            else:
                return self.constructor(*args, **kwargs)
        else:
            return Undefined

    def tag(self, **tags):
        self.tags.update(**tags)
        return self

    def has_tags(self, **tags):
        my_tags = self.tags
        for k, v in tags.items():
            if k in my_tags:
                if callable(v) and not v(my_tags[k]):
                    return False
                elif v != my_tags[k]:
                    return False
        else:
            return tags == my_tags

    def info(self):
        info = "any value"
        if not self.allow_none:
            info += " except None"
        return info

    # Methods Shouldn't Need To Be Overridden
    # ---------------------------------------

    def __get__(self, obj, cls):
        if obj is not None:
            return self.get_value(obj)
        else:
            return self

    def __set__(self, obj, val):
        if self.tags.writable:
            if val is None:
                if self.tags.allow_none:
                    self.model(obj)[self.name] = val
                else:
                    raise TraitError("%s's %r attribute can be %s"
                        % (describe("An", obj, "object"), self.name, self.info()))
            else:
                self.set_value(obj, val)
        else:
            raise TraitError("%s's %r attribute is not writable"
                % (describe("An", obj, "object"), self.name))

    def __delete__(self, obj):
        if self.tags.writable:
            self.del_value(obj)
        else:
            raise TraitError("%s's %r attribute is not writable"
                % (describe("An", obj, "object"), self.name))

    # Methods To Overrite In Subclasses
    # ---------------------------------

    def get_value(self, obj):
        try:
            return self.model(obj)[self.name]
        except KeyError:
            # just in time default generation generally
            # occurs when information about an object is
            # required to generate the default of a trait
            default = self.default(obj)
            self.set_value(obj, default)
            return default

    def set_value(self, obj, val):
        self.model(obj)[self.name] = val

    def del_value(self, obj):
        del self.model(obj)[self.name]

    def model(self, obj):
        "Return the underlying model of the given object"
        return obj._model
