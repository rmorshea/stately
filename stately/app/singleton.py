from stately import Stately


class Singleton(Stately):

    _instance_ = None
    _singleton_ = True

    def __new__(cls, *args, **kwargs):
        new = super(Singleton, cls).__new__
        if new is not object.__new__:
            self = new(cls, *args, **kwargs)
        else:
            self = new(cls)
        for cls in cls.mro():
            if issubclass(cls, Singleton):
                if vars(cls).get("_singleton_", False):
                    singleton = cls
                    break
        else:
            raise RuntimeError("Bad singleton set up.")
        singleton._instance_ = self
        return self

    @classmethod
    def instance(cls):
        return cls._instance_

    @classmethod
    def delete():
        cls._instance_ = None

    @classmethod
    def exists():
        return cls._instance_ is not None
