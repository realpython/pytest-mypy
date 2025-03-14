"""Mypy static type checker plugin for Pytest"""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
from tempfile import NamedTemporaryFile
import typing

from filelock import FileLock
import mypy.api
import pytest

if typing.TYPE_CHECKING:  # pragma: no cover
    from typing import (
        Any,
        Dict,
        IO,
        Iterator,
        List,
        Optional,
        Tuple,
        Union,
    )

    # https://github.com/pytest-dev/pytest/issues/7469
    from _pytest._code.code import TerminalRepr

    # https://github.com/pytest-dev/pytest/pull/12661
    from _pytest.terminal import TerminalReporter

    # https://github.com/pytest-dev/pytest-xdist/issues/1121
    from xdist.workermanage import WorkerController  # type: ignore


@dataclass(frozen=True)  # compat python < 3.10 (kw_only=True)
class MypyConfigStash:
    """Plugin data stored in the pytest.Config stash."""

    mypy_results_path: Path

    @classmethod
    def from_serialized(cls, serialized: str) -> MypyConfigStash:
        return cls(mypy_results_path=Path(serialized))

    def serialized(self) -> str:
        return str(self.mypy_results_path)


item_marker = "mypy"
mypy_argv: List[str] = []
nodeid_name = "mypy"
stash_key = {
    "config": pytest.StashKey[MypyConfigStash](),
}
terminal_summary_title = "mypy"


def default_test_name_formatter(*, item: MypyFileItem) -> str:
    path = item.path.relative_to(item.config.invocation_params.dir)
    return f"[{terminal_summary_title}] {path}"


test_name_formatter = default_test_name_formatter


def default_file_error_formatter(
    item: MypyItem,
    results: MypyResults,
    lines: List[str],
) -> str:
    """Create a string to be displayed when mypy finds errors in a file."""
    if item.config.option.mypy_report_style == "mypy":
        return "\n".join(lines)
    return "\n".join(line.partition(":")[2].strip() for line in lines)


file_error_formatter = default_file_error_formatter


def pytest_addoption(parser: pytest.Parser) -> None:
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
    styles = {
        "mypy": "modify the original mypy output as little as possible",
        "no-path": "(default) strip the path prefix from mypy errors",
    }
    group.addoption(
        "--mypy-report-style",
        choices=list(styles),
        help="change the way mypy output is reported:\n"
        + "\n".join(f"- {name}: {desc}" for name, desc in styles.items()),
    )
    group.addoption(
        "--mypy-no-status-check",
        action="store_true",
        help="ignore mypy's exit status",
    )
    group.addoption(
        "--mypy-xfail",
        action="store_true",
        help="xfail mypy errors",
    )


def _xdist_worker(config: pytest.Config) -> Dict[str, Any]:
    try:
        return {"input": _xdist_workerinput(config)}
    except AttributeError:
        return {}


def _xdist_workerinput(node: Union[WorkerController, pytest.Config]) -> Any:
    try:
        # mypy complains that pytest.Config does not have this attribute,
        # but xdist.remote defines it in worker processes.
        return node.workerinput  # type: ignore[union-attr]
    except AttributeError:  # compat xdist < 2.0
        return node.slaveinput  # type: ignore[union-attr]


class MypyXdistControllerPlugin:
    """A plugin that is only registered on xdist controller processes."""

    def pytest_configure_node(self, node: WorkerController) -> None:
        """Pass the config stash to workers."""
        _xdist_workerinput(node)["mypy_config_stash_serialized"] = node.config.stash[
            stash_key["config"]
        ].serialized()


def pytest_configure(config: pytest.Config) -> None:
    """
    Initialize the path used to cache mypy results,
    register a custom marker for MypyItems,
    and configure the plugin based on the CLI.
    """
    xdist_worker = _xdist_worker(config)
    if not xdist_worker:
        config.pluginmanager.register(MypyControllerPlugin())

        # Get the path to a temporary file and delete it.
        # The first MypyItem to run will see the file does not exist,
        # and it will run and parse mypy results to create it.
        # Subsequent MypyItems will see the file exists,
        # and they will read the parsed results.
        with NamedTemporaryFile(delete=True) as tmp_f:
            config.stash[stash_key["config"]] = MypyConfigStash(
                mypy_results_path=Path(tmp_f.name),
            )

        # If xdist is enabled, then the results path should be exposed to
        # the workers so that they know where to read parsed results from.
        if config.pluginmanager.getplugin("xdist"):
            config.pluginmanager.register(MypyXdistControllerPlugin())
    else:
        # xdist workers create the stash using input from the controller plugin.
        config.stash[stash_key["config"]] = MypyConfigStash.from_serialized(
            xdist_worker["input"]["mypy_config_stash_serialized"]
        )

    config.addinivalue_line(
        "markers",
        f"{item_marker}: mark tests to be checked by mypy.",
    )
    if config.getoption("--mypy-ignore-missing-imports"):
        mypy_argv.append("--ignore-missing-imports")

    mypy_config_file = config.getoption("--mypy-config-file")
    if mypy_config_file:
        mypy_argv.append(f"--config-file={mypy_config_file}")

    if any(
        [
            config.option.mypy,
            config.option.mypy_config_file,
            config.option.mypy_report_style,
            config.option.mypy_ignore_missing_imports,
            config.option.mypy_no_status_check,
            config.option.mypy_xfail,
        ],
    ):
        config.pluginmanager.register(MypyCollectionPlugin())


class MypyCollectionPlugin:
    """A Pytest plugin that collects MypyFiles."""

    def pytest_collect_file(
        self,
        file_path: Path,
        parent: pytest.Collector,
    ) -> Optional[MypyFile]:
        """Create a MypyFileItem for every file mypy should run on."""
        if file_path.suffix in {".py", ".pyi"}:
            # Do not create MypyFile instance for a .py file if a
            # .pyi file with the same name already exists;
            # pytest will complain about duplicate modules otherwise
            if (
                file_path.suffix == ".pyi"
                or not file_path.with_suffix(".pyi").is_file()
            ):
                return MypyFile.from_parent(parent=parent, path=file_path)
        return None


class MypyFile(pytest.File):
    """A File that Mypy will run on."""

    def collect(self) -> Iterator[MypyItem]:
        """Create a MypyFileItem for the File."""
        yield MypyFileItem.from_parent(parent=self, name=nodeid_name)
        # Since mypy might check files that were not collected,
        # pytest could pass even though mypy failed!
        # To prevent that, add an explicit check for the mypy exit status.
        if not self.session.config.option.mypy_no_status_check and not any(
            isinstance(item, MypyStatusItem) for item in self.session.items
        ):
            yield MypyStatusItem.from_parent(
                parent=self,
                name=nodeid_name + "-status",
            )


class MypyItem(pytest.Item):
    """A Mypy-related test Item."""

    def __init__(self, *args: Any, **kwargs: Any):
        super().__init__(*args, **kwargs)
        self.add_marker(item_marker)

    def repr_failure(
        self,
        excinfo: pytest.ExceptionInfo[BaseException],
        style: Optional[str] = None,
    ) -> Union[str, TerminalRepr]:
        """
        Unwrap mypy errors so we get a clean error message without the
        full exception repr.
        """
        if excinfo.errisinstance(MypyError):
            return str(excinfo.value.args[0])
        return super().repr_failure(excinfo)


def _error_severity(line: str) -> Optional[str]:
    components = [component.strip() for component in line.split(":", 3)]
    if len(components) < 2:
        return None
    # The second component is either the line or the severity:
    # demo/note.py:2: note: By default the bodies of untyped functions are not checked
    # demo/sub/conftest.py: error: Duplicate module named "conftest"
    return components[2] if components[1].isdigit() else components[1]


class MypyFileItem(MypyItem):
    """A check for Mypy errors in a File."""

    def runtest(self) -> None:
        """Raise an exception if mypy found errors for this item."""
        results = MypyResults.from_session(self.session)
        lines = results.path_lines.get(self.path.resolve(), [])
        if lines and not all(_error_severity(line) == "note" for line in lines):
            if self.session.config.option.mypy_xfail:
                self.add_marker(
                    pytest.mark.xfail(
                        raises=MypyError,
                        reason="mypy errors are expected by --mypy-xfail.",
                    )
                )
            raise MypyError(file_error_formatter(self, results, lines))

    def reportinfo(self) -> Tuple[Path, None, str]:
        """Produce a heading for the test report."""
        return (self.path, None, test_name_formatter(item=self))


class MypyStatusItem(MypyItem):
    """A check for a non-zero mypy exit status."""

    def runtest(self) -> None:
        """Raise a MypyError if mypy exited with a non-zero status."""
        results = MypyResults.from_session(self.session)
        if results.status:
            if self.session.config.option.mypy_xfail:
                self.add_marker(
                    pytest.mark.xfail(
                        raises=MypyError,
                        reason=(
                            "A non-zero mypy exit status is expected by --mypy-xfail."
                        ),
                    )
                )
            raise MypyError(f"mypy exited with status {results.status}.")


@dataclass(frozen=True)  # compat python < 3.10 (kw_only=True)
class MypyResults:
    """Parsed results from Mypy."""

    _encoding = "utf-8"

    opts: List[str]
    args: List[str]
    stdout: str
    stderr: str
    status: int
    path_lines: Dict[Optional[Path], List[str]]

    def dump(self, results_f: IO[bytes]) -> None:
        """Cache results in a format that can be parsed by load()."""
        prepared = vars(self).copy()
        prepared["path_lines"] = {
            str(path or ""): lines for path, lines in prepared["path_lines"].items()
        }
        results_f.write(json.dumps(prepared).encode(self._encoding))

    @classmethod
    def load(cls, results_f: IO[bytes]) -> MypyResults:
        """Get results cached by dump()."""
        prepared = json.loads(results_f.read().decode(cls._encoding))
        prepared["path_lines"] = {
            Path(path) if path else None: lines
            for path, lines in prepared["path_lines"].items()
        }
        return cls(**prepared)

    @classmethod
    def from_mypy(
        cls,
        paths: List[Path],
        *,
        opts: Optional[List[str]] = None,
    ) -> MypyResults:
        """Generate results from mypy."""

        if opts is None:
            opts = mypy_argv[:]
        args = [str(path) for path in paths]

        stdout, stderr, status = mypy.api.run(opts + args)

        path_lines: Dict[Optional[Path], List[str]] = {
            path.resolve(): [] for path in paths
        }
        path_lines[None] = []
        for line in stdout.split("\n"):
            if not line:
                continue
            path = Path(line.partition(":")[0]).resolve()
            try:
                lines = path_lines[path]
            except KeyError:
                lines = path_lines[None]
            lines.append(line)

        return cls(
            opts=opts,
            args=args,
            stdout=stdout,
            stderr=stderr,
            status=status,
            path_lines=path_lines,
        )

    @classmethod
    def from_session(cls, session: pytest.Session) -> MypyResults:
        """Load (or generate) cached mypy results for a pytest session."""
        mypy_results_path = session.config.stash[stash_key["config"]].mypy_results_path
        with FileLock(str(mypy_results_path) + ".lock"):
            try:
                with open(mypy_results_path, mode="rb") as results_f:
                    results = cls.load(results_f)
            except FileNotFoundError:
                cwd = Path.cwd()
                results = cls.from_mypy(
                    [
                        item.path.relative_to(cwd)
                        for item in session.items
                        if isinstance(item, MypyFileItem)
                    ],
                )
                with open(mypy_results_path, mode="wb") as results_f:
                    results.dump(results_f)
        return results


class MypyError(Exception):
    """
    An error caught by mypy, e.g a type checker violation
    or a syntax error.
    """


class MypyControllerPlugin:
    """A plugin that is not registered on xdist worker processes."""

    def pytest_terminal_summary(
        self,
        terminalreporter: TerminalReporter,
        config: pytest.Config,
    ) -> None:
        """Report mypy results."""
        mypy_results_path = config.stash[stash_key["config"]].mypy_results_path
        try:
            with open(mypy_results_path, mode="rb") as results_f:
                results = MypyResults.load(results_f)
        except FileNotFoundError:
            # No MypyItems executed.
            return
        if not results.stdout and not results.stderr:
            return
        terminalreporter.section(terminal_summary_title)
        if results.stdout:
            if config.option.mypy_xfail:
                terminalreporter.write(results.stdout)
            else:
                for note in (
                    unreported_note
                    for path, lines in results.path_lines.items()
                    if path is not None
                    if all(_error_severity(line) == "note" for line in lines)
                    for unreported_note in lines
                ):
                    terminalreporter.write_line(note)
                if results.path_lines.get(None):
                    color = {"red": True} if results.status else {"green": True}
                    terminalreporter.write_line(
                        "\n".join(results.path_lines[None]), **color
                    )
        if results.stderr:
            terminalreporter.write_line(results.stderr, yellow=True)

    def pytest_unconfigure(self, config: pytest.Config) -> None:
        """Clean up the mypy results path."""
        config.stash[stash_key["config"]].mypy_results_path.unlink(missing_ok=True)
