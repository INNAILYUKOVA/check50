"""
Additional check50 internals exposed to extension writers in addition to the standard API
"""

import importlib
from pathlib import Path
import sys

import lib50

from . import simple

#: Directory containing the check and its associated files
check_dir = None

#: Temporary directory in which check is being run
run_dir = None

#: Boolean that indicates if a check is currently running
check_running = False


class Error(Exception):
    """Exception for internal check50 errors."""
    pass


class Register:
    """
    Class with which functions can be registered to run before / after checks.
    :data:`check50.internal.register` should be the sole instance of this class.
    """
    def __init__(self):
        def _running_callback():
            global check_running
            check_running = True

        def _not_running_callback():
            global check_running
            check_running = False

        self._before_everies = [_running_callback]
        self._after_everies = [_not_running_callback]
        self._after_checks = []

    def after_check(self, func):
        """Run func once at the end of the check, then discard func.

        :param func: callback to run after check
        :raises check50.internal.Error: if called when no check is being run"""
        if not check_running:
            raise Error("cannot register callback to run after check when no check is running")
        self._after_checks.append(func)

    def after_every(self, func):
        """Run func at the end of every check.

        :param func: callback to be run after every check
        :raises check50.internal.Error: if called when a check is being run"""
        if check_running:
            raise Error("cannot register callback to run after every check when check is running")
        self._after_everies.append(func)

    def before_every(self, func):
        """Run func at the start of every check.

        :param func: callback to be run before every check
        :raises check50.internal.Error: if called when a check is being run"""

        if check_running:
            raise Error("cannot register callback to run before every check when check is running")
        self._before_everies.append(func)

    def __enter__(self):
        for f in self._before_everies:
            f()

    def __exit__(self, exc_type, exc_val, exc_tb):
        # Only run 'afters' when check has passed
        if exc_type is not None:
            return

        # Run and remove all checks registered to run after a single check
        while self._after_checks:
            self._after_checks.pop()()

        for f in self._after_everies:
            f()


#: Sole instance of the :class:`check50.internal.Register` class
register = Register()


def load_config(check_dir):
    """
    Load configuration file from ``check_dir / ".cs50.yaml"``, applying
    defaults to unspecified values.

    :param check_dir: directory from which to load config file
    :type check_dir: str / Path
    :rtype: dict
    """

    # Defaults for top-level keys
    options = {
        "checks": "__init__.py",
        "dependencies": None,
        "translations": None
    }

    # Defaults for translation keys
    translation_options = {
        "localedir": "locale",
        "domain": "messages",
    }

    config_file = Path(check_dir) / ".cs50.yaml"

    with open(config_file) as f:
        config = lib50.config.load(f.read(), "check50")

    if isinstance(config, dict):
        options.update(config)

    if options["translations"]:
        if isinstance(options["translations"], dict):
            translation_options.update(options["translations"])
        options["translations"] = translation_options

    if isinstance(options["checks"], dict):
        # Compile simple checks
        with open(check_dir / "__init__.py", "w") as f:
            f.write(simple.compile(options["checks"]))
        options["checks"] = "__init__.py"

    return options


def import_file(name, path):
    """
    Import a file given a raw file path.

    :param name: Name of module to be imported
    :type name: str
    :param path: Path to Python file
    :type path: str / Path
    """
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod
