import os
import ast
import copy
import logging
from metasetup import Settings, ArgumentParser

from stately.utils import (describe, class_attribute_lineage,
    dictmerge, str_to_bool, fullname, flatten)
from stately import Instance, observe, condition, Stately, Undefined

from .singleton import Singleton


@condition(typenames="set event")
def change(owner, event):
    return event.old != event.new


class Application(Singleton):

    # Marks this as the root singleton class.
    # Any subclass which creates an instance
    # is available via the `instance` method
    # of this Application class.
    _singleton_ = True

    # -------------------------------------------------------
    # Attributes --------------------------------------------
    # -------------------------------------------------------

    name = None
    summary = None
    details = None

    # -------------------------------------------------------
    # Logging -----------------------------------------------
    # -------------------------------------------------------

    logger = Instance(logging.Logger, "_init_logger")

    def _init_logger(self):
        cls = self.__class__
        name = cls.__module__ + "." + cls.__name__
        return logging.Logger(name, self.logger_level)

    logger_level = Instance(int).tag(allow_none=True) | Instance(str)

    @observe(change, "logger_level")
    def _update_logger_level(self, event):
        self.logger.setLevel(event.new)

    @observe(change, {"log": lambda tag: instance(tag, (str, int))})
    def _log_event(self, event):
        level = getattr(event, "level", "debug")
        self.log(level, event.info())

    def log(self, level, msg, *args, **kwargs):
        self.logger.log(level, msg, *args, **kwargs)

    
    # -------------------------------------------------------
    # Settings ----------------------------------------------
    # -------------------------------------------------------

    loaders = ("env_settings", "cli_settings")

    def configure(self, failure_level=None, *args, **kwargs):
        keys = self.data_names(setting=True)
        settings = super(Application, self).configure(keys=keys, *args, **kwargs)
        if failure_level is not None:
            for k in settings:
                if k not in keys:
                    cls = type(self)
                    msg = "The setting '%s.%s.%s' does not exist."
                    self.log(failure_level, msg, cls.__module__, cls.__name__, k)

    # Evironment Variables
    # --------------------

    envvars = {
        "DEBUG_LOG_LEVEL": {"logger_level": logging.DEBUG},
        "LOG_LEVEL": "logger_level"
    }

    @classmethod
    def env_settings(cls):
        """Get environment settings."""
        settings = Settings()
        envvars = cls.attr_lineage("envvars", Application)
        for key, value in dictmerge(envvars, reverse=True).items():
            var = os.environ.get(key)
            if value is not None:
                if isinstance(value, str):
                    settings[value] = var
                elif isinstance(value, dict):
                    for k, v in value.items():
                        settings[k] = v
                elif callable(value):
                    value(cls, settings, var)
                else:
                    raise TypeError("%r has an impropper environment variable spec" % cls)
        return settings

    # Command Line Settings
    # ---------------------

    flags = {
        "--log-level": "logger_level",
        "--debug": dict(dest="logger_level", const=logging.DEBUG, action="store_const"),
    }

    @classmethod
    def cli_settings(cls):
        parser = cls.cli_argparser()
        settings = parser.parse_settings()
        namespace = parser.parse_args()

        flags = dictmerge(cls.attr_lineage("flags", Application), reverse=True)

        for value in flags.values():
            if isinstance(value, dict):
                value = value["dest"]
            arg = getattr(namespace, value)
            if arg is not Undefined:
                settings[value] = arg

        return settings

    @classmethod
    def cli_argparser(cls):
        parser = ArgumentParser(cls.name, description=cls.summary, epilog=cls.details)
        cls._add_cli_arguments(parser)
        return parser

    @classmethod
    def _add_cli_arguments(cls, parser):
        parser.add_settings(cls.__module__, cls.__name__)
        for flags in cls.attr_lineage("flags", Application):
            for flag, value in flags.items():
                if isinstance(value, str):
                    parser.add_argument(flag, dest=value, help="settings for %s.%s.%s"
                        % (cls.__module__, cls.__name__, value), default=Undefined)
                elif isinstance(value, dict):
                    parser.add_argument(flag, **value)


    # -------------------------------------------------------
    # Utils -------------------------------------------------
    # -------------------------------------------------------

    @classmethod
    def attr_lineage(cls, name, base=None):
        return (l[1] for l in class_attribute_lineage(cls, name, base=base))


def logger():
    if Application.exists():
        return Application.instance().logger
