"""Mypy static type checker plugin for Pytest"""

import pytest
import mypy.api


def pytest_addoption(parser):
    """Add options for enabling and running mypy."""
    group = parser.getgroup('mypy')
    group.addoption(
        '--mypy', action='store_true',
        help='run mypy on .py files')
    group.addoption(
        '--mypy-ignore-missing-imports', action='store_true',
        help="suppresses error messages about imports that cannot be resolved")


def pytest_collect_file(path, parent):
    """Create a MypyItem for every file mypy should run on."""
    config = parent.config
    mypy_config = []

    if config.option.mypy_ignore_missing_imports:
        mypy_config.append("--ignore-missing-imports")

    if path.ext == '.py' and any([
            config.option.mypy,
            config.option.mypy_ignore_missing_imports,
    ]):
        return MypyItem(path, parent, mypy_config)


def pytest_configure(config):
    """Register a custom marker for MypyItems."""
    config.addinivalue_line(
        "markers",
        "mypy: mark tests to be checked by mypy.",
    )


class MypyError(Exception):
    """
    An error caught by mypy, e.g a type checker violation
    or a syntax error.
    """
    pass


class MypyItem(pytest.Item, pytest.File):

    """A File that Mypy Runs On."""

    def __init__(self, path, parent, config):
        super().__init__(path, parent)
        self.path = path
        self.mypy_config = config
        self.add_marker("mypy")

    def reportinfo(self):
        """Produce a heading for the test report."""
        return self.fspath, None, ' '.join(['mypy', self.name])

    def runtest(self):
        """
        Run mypy on the given file.
        """

        # Construct a fake command line argv and let mypy do its
        # own options parsing.
        mypy_argv = [
            str(self.path),
            '--incremental',
        ]

        mypy_argv += self.mypy_config

        stdout, _, _ = mypy.api.run(args=mypy_argv)

        if stdout:
            raise MypyError(stdout)

    def repr_failure(self, excinfo):
        """
        Unwrap mypy errors so we get a clean error message without the
        full exception repr.
        """
        if excinfo.errisinstance(MypyError):
            return excinfo.value.args[0]
        return super().repr_failure(excinfo)
