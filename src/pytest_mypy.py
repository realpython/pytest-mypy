"""Mypy static type checker plugin for Pytest"""

import json
import os
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Dict, List, Optional, TextIO
import warnings

import attr
from filelock import FileLock  # type: ignore
import mypy.api
import pytest  # type: ignore


PYTEST_MAJOR_VERSION = int(pytest.__version__.partition(".")[0])
mypy_argv = []
nodeid_name = "mypy"


def default_file_error_formatter(item, results, errors):
    """Create a string to be displayed when mypy finds errors in a file."""
    return "\n".join(errors)


file_error_formatter = default_file_error_formatter


def pytest_addoption(parser):
    """Add options for enabling and running mypy."""
    group = parser.getgroup("mypy")
    group.addoption("--mypy", action="store_true", help="run mypy on .py files")
    group.addoption(
        "--mypy-ignore-missing-imports",
        action="store_true",
        help="suppresses error messages about imports that cannot be resolved",
    )
    group.addoption(
        "--mypy-config-file",
        action="store",
        type=str,
        help="adds custom mypy config file",
    )


XDIST_WORKERINPUT_ATTRIBUTE_NAMES = (
    "workerinput",
    # xdist < 2.0.0:
    "slaveinput",
)


def _get_xdist_workerinput(config_node):
    workerinput = None
    for attr_name in XDIST_WORKERINPUT_ATTRIBUTE_NAMES:
        workerinput = getattr(config_node, attr_name, None)
        if workerinput is not None:
            break
    return workerinput


def _is_master(config):
    """
    True if the code running the given pytest.config object is running in
    an xdist master node or not running xdist at all.
    """
    return _get_xdist_workerinput(config) is None


def pytest_configure(config):
    """
    Initialize the path used to cache mypy results,
    register a custom marker for MypyItems,
    and configure the plugin based on the CLI.
    """
    if _is_master(config):

        # Get the path to a temporary file and delete it.
        # The first MypyItem to run will see the file does not exist,
        # and it will run and parse mypy results to create it.
        # Subsequent MypyItems will see the file exists,
        # and they will read the parsed results.
        with NamedTemporaryFile(delete=True) as tmp_f:
            config._mypy_results_path = tmp_f.name

        # If xdist is enabled, then the results path should be exposed to
        # the workers so that they know where to read parsed results from.
        if config.pluginmanager.getplugin("xdist"):

            class _MypyXdistPlugin:
                def pytest_configure_node(self, node):  # xdist hook
                    """Pass config._mypy_results_path to workers."""
                    _get_xdist_workerinput(node)[
                        "_mypy_results_path"
                    ] = node.config._mypy_results_path

            config.pluginmanager.register(_MypyXdistPlugin())

    config.addinivalue_line(
        "markers",
        f"{MypyItem.MARKER}: mark tests to be checked by mypy.",
    )
    if config.getoption("--mypy-ignore-missing-imports"):
        mypy_argv.append("--ignore-missing-imports")

    mypy_config_file = config.getoption("--mypy-config-file")
    if mypy_config_file:
        mypy_argv.append(f"--config-file={mypy_config_file}")


def pytest_collect_file(file_path, parent):
    """Create a MypyFileItem for every file mypy should run on."""
    if file_path.suffix in {".py", ".pyi"} and any(
        [
            parent.config.option.mypy,
            parent.config.option.mypy_config_file,
            parent.config.option.mypy_ignore_missing_imports,
        ],
    ):
        # Do not create MypyFile instance for a .py file if a
        # .pyi file with the same name already exists;
        # pytest will complain about duplicate modules otherwise
        if file_path.suffix == ".pyi" or not file_path.with_suffix(".pyi").is_file():
            return MypyFile.from_parent(parent=parent, path=file_path)
    return None


if PYTEST_MAJOR_VERSION < 7:  # pragma: no cover
    _pytest_collect_file = pytest_collect_file

    def pytest_collect_file(path, parent):  # type: ignore
        try:
            # https://docs.pytest.org/en/7.0.x/deprecations.html#py-path-local-arguments-for-hooks-replaced-with-pathlib-path
            return _pytest_collect_file(Path(str(path)), parent)
        except TypeError:
            # https://docs.pytest.org/en/7.0.x/deprecations.html#fspath-argument-for-node-constructors-replaced-with-pathlib-path
            return MypyFile.from_parent(parent=parent, fspath=path)


class MypyFile(pytest.File):

    """A File that Mypy will run on."""

    @classmethod
    def from_parent(cls, *args, **kwargs):
        """Override from_parent for compatibility."""
        # pytest.File.from_parent did not exist before pytest 5.4.
        return getattr(super(), "from_parent", cls)(*args, **kwargs)

    def collect(self):
        """Create a MypyFileItem for the File."""
        yield MypyFileItem.from_parent(parent=self, name=nodeid_name)
        # Since mypy might check files that were not collected,
        # pytest could pass even though mypy failed!
        # To prevent that, add an explicit check for the mypy exit status.
        if not any(isinstance(item, MypyStatusItem) for item in self.session.items):
            yield MypyStatusItem.from_parent(
                parent=self,
                name=nodeid_name + "-status",
            )


class MypyItem(pytest.Item):

    """A Mypy-related test Item."""

    MARKER = "mypy"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_marker(self.MARKER)

    def collect(self):
        """
        Partially work around https://github.com/pytest-dev/pytest/issues/8016
        for pytest < 6.0 with --looponfail.
        """
        yield self

    @classmethod
    def from_parent(cls, *args, **kwargs):
        """Override from_parent for compatibility."""
        # pytest.Item.from_parent did not exist before pytest 5.4.
        return getattr(super(), "from_parent", cls)(*args, **kwargs)

    def repr_failure(self, excinfo):
        """
        Unwrap mypy errors so we get a clean error message without the
        full exception repr.
        """
        if excinfo.errisinstance(MypyError):
            return excinfo.value.args[0]
        return super().repr_failure(excinfo)


class MypyFileItem(MypyItem):

    """A check for Mypy errors in a File."""

    def runtest(self):
        """Raise an exception if mypy found errors for this item."""
        results = MypyResults.from_session(self.session)
        abspath = os.path.abspath(str(self.fspath))
        errors = results.abspath_errors.get(abspath)
        if errors:
            if not all(
                error.partition(":")[2].partition(":")[0].strip() == "note"
                for error in errors
            ):
                raise MypyError(file_error_formatter(self, results, errors))
            # This line cannot be easily covered on mypy < 0.990:
            warnings.warn("\n" + "\n".join(errors), MypyWarning)  # pragma: no cover

    def reportinfo(self):
        """Produce a heading for the test report."""
        return (
            self.fspath,
            None,
            self.config.invocation_dir.bestrelpath(self.fspath),
        )


class MypyStatusItem(MypyItem):

    """A check for a non-zero mypy exit status."""

    def runtest(self):
        """Raise a MypyError if mypy exited with a non-zero status."""
        results = MypyResults.from_session(self.session)
        if results.status:
            raise MypyError(f"mypy exited with status {results.status}.")


@attr.s(frozen=True, kw_only=True)
class MypyResults:

    """Parsed results from Mypy."""

    _abspath_errors_type = Dict[str, List[str]]

    opts = attr.ib(type=List[str])
    stdout = attr.ib(type=str)
    stderr = attr.ib(type=str)
    status = attr.ib(type=int)
    abspath_errors = attr.ib(type=_abspath_errors_type)
    unmatched_stdout = attr.ib(type=str)

    def dump(self, results_f: TextIO) -> None:
        """Cache results in a format that can be parsed by load()."""
        return json.dump(vars(self), results_f)

    @classmethod
    def load(cls, results_f: TextIO) -> "MypyResults":
        """Get results cached by dump()."""
        return cls(**json.load(results_f))

    @classmethod
    def from_mypy(
        cls,
        items: List[MypyFileItem],
        *,
        opts: Optional[List[str]] = None,
    ) -> "MypyResults":
        """Generate results from mypy."""

        if opts is None:
            opts = mypy_argv[:]
        abspath_errors = {
            os.path.abspath(str(item.fspath)): [] for item in items
        }  # type: MypyResults._abspath_errors_type

        stdout, stderr, status = mypy.api.run(
            opts + [os.path.relpath(key) for key in abspath_errors.keys()]
        )

        unmatched_lines = []
        for line in stdout.split("\n"):
            if not line:
                continue
            path, _, error = line.partition(":")
            abspath = os.path.abspath(path)
            try:
                abspath_errors[abspath].append(error)
            except KeyError:
                unmatched_lines.append(line)

        return cls(
            opts=opts,
            stdout=stdout,
            stderr=stderr,
            status=status,
            abspath_errors=abspath_errors,
            unmatched_stdout="\n".join(unmatched_lines),
        )

    @classmethod
    def from_session(cls, session) -> "MypyResults":
        """Load (or generate) cached mypy results for a pytest session."""
        results_path = (
            session.config._mypy_results_path
            if _is_master(session.config)
            else _get_xdist_workerinput(session.config)["_mypy_results_path"]
        )
        with FileLock(results_path + ".lock"):
            try:
                with open(results_path, mode="r") as results_f:
                    results = cls.load(results_f)
            except FileNotFoundError:
                results = cls.from_mypy(
                    [item for item in session.items if isinstance(item, MypyFileItem)],
                )
                with open(results_path, mode="w") as results_f:
                    results.dump(results_f)
        return results


class MypyError(Exception):
    """
    An error caught by mypy, e.g a type checker violation
    or a syntax error.
    """


class MypyWarning(pytest.PytestWarning):
    """A non-failure message regarding the mypy run."""


def pytest_terminal_summary(terminalreporter, config):
    """Report stderr and unrecognized lines from stdout."""
    try:
        with open(config._mypy_results_path, mode="r") as results_f:
            results = MypyResults.load(results_f)
    except FileNotFoundError:
        # No MypyItems executed.
        return
    if results.unmatched_stdout or results.stderr:
        terminalreporter.section("mypy")
        if results.unmatched_stdout:
            color = {"red": True} if results.status else {"green": True}
            terminalreporter.write_line(results.unmatched_stdout, **color)
        if results.stderr:
            terminalreporter.write_line(results.stderr, yellow=True)
    os.remove(config._mypy_results_path)
