import logging

from stately.utils import describe
from stately import Instance, observe, condition

from .single import Singleton


def logger():
    if Application.exists():
        return Application.instance().logger


class Application(Singleton):

    # marks this as the root singleton class
    # any subclass which creates an instance
    # is available via the `instance` method
    _singleton_ = True

    logger = Instance(logging.Logger, constructor="_default_logger")

    def _default_logger(self):
        cls = self.__class__
        name = cls.__module__ + "." + cls.__name__
        return logging.Logger(name, self.logger_level)

    logger_level = Instance(int)(0) | Instance("str")

    @observe(lambda e: e.old != e.new, "logger_level", "set event")
    def _update_logger_level(self, event):
        self.logger.setLevel(event.new)

    def log_events(self, method, *args, **kwargs):
        def log(owner, event):
            getattr(owner.logger, method)(str(event))
        self.observe(*args, **kwargs)(log)
