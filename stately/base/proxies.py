from .model import Descriptor
from ..utils import Exceptions, last_traceback, raises

class ProxyDescriptor(Descriptor):

    def __init__(self, descriptor, *args, **kwargs):
        self._descriptor = descriptor
        super(ProxyDescriptor, self).__init__(*args, **kwargs)

    def __set_name__(self, cls, name):
        self._descriptor.__set_name__(cls, name)

    def __init_subclass__(self, cls):
        self._descriptor.__init_subclass__(cls)

    def __init_instance__(self, obj):
        self._descriptor.__init_instance__(obj)

    def __setattr__(self, name, value):
        setattr(self._descriptor, name, value)

    def __getattr__(self, name):
        return getattr(self._descriptor, name)

    def __delattr__(self, name):
        delattr(self._descriptor, name)


class ProxyManyDescriptors(Descriptor):

    def __init__(self, *descriptors, **kwargs):
        self._descriptors = descriptors
        super(ProxyManyDescriptors, self).__init__(**kwargs)

    def __set_name__(self, cls, name):
        for d in self._descriptors:
            d.__set_name__(cls, name)

    def __init_subclass__(self, cls):
        for d in self._descriptors:
            d.__init_subclass__(cls)

    def __init_instance__(self, obj):
        for d in self._descriptors:
            d.__init_instance__(obj)

    def __set__(self, obj, val):
        errors = []
        for d in self._descriptors:
            try:
                d.__set__(obj, val)
            except Exception as e:
                tb = last_traceback()
                errors.append(e)
            else:
                break
        else:
            if len(errors) == 1:
                raise errors[0]
            else:
                raises(Exceptions(*errors), None, tb)

    def __get__(self, obj, cls):
        errors = []
        for d in self._descriptors:
            try:
                return d.__get__(obj, cls)
            except Exception as e:
                tb = last_traceback()
                errors.append(e)
        else:
            if len(errors) == 1:
                raise errors[0]
            else:
                raises(Exceptions(*errors), None, tb)

    def __delete__(self, obj):
        errors = []
        for d in self._descriptors:
            try:
                return d.__delete__(obj)
            except Exception as error:
                tb = last_traceback()
                errors.append(e)
        else:
            if len(errors) == 1:
                raise errors[0]
            else:
                raises(Exceptions(*errors), None, tb)