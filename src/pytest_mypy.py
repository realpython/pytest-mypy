"""Mypy static type checker plugin for Pytest"""

import functools
import json
import os
from tempfile import NamedTemporaryFile

from filelock import FileLock  # type: ignore
import mypy.api
import pytest  # type: ignore


mypy_argv = []
nodeid_name = 'mypy'


def default_file_error_formatter(item, results, errors):
    """Create a string to be displayed when mypy finds errors in a file."""
    return '\n'.join(errors)


file_error_formatter = default_file_error_formatter


def pytest_addoption(parser):
    """Add options for enabling and running mypy."""
    group = parser.getgroup('mypy')
    group.addoption(
        '--mypy', action='store_true',
        help='run mypy on .py files')
    group.addoption(
        '--mypy-ignore-missing-imports', action='store_true',
        help="suppresses error messages about imports that cannot be resolved")


XDIST_WORKERINPUT_ATTRIBUTE_NAMES = (
    'workerinput',
    # xdist < 2.0.0:
    'slaveinput',
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
        if config.pluginmanager.getplugin('xdist'):
            class _MypyXdistPlugin:
                def pytest_configure_node(self, node):  # xdist hook
                    """Pass config._mypy_results_path to workers."""
                    _get_xdist_workerinput(node)['_mypy_results_path'] = \
                        node.config._mypy_results_path
            config.pluginmanager.register(_MypyXdistPlugin())

    # pytest_terminal_summary cannot accept config before pytest 4.2.
    global _pytest_terminal_summary_config
    _pytest_terminal_summary_config = config

    config.addinivalue_line(
        'markers',
        '{marker}: mark tests to be checked by mypy.'.format(
            marker=MypyItem.MARKER,
        ),
    )
    if config.getoption('--mypy-ignore-missing-imports'):
        mypy_argv.append('--ignore-missing-imports')


def pytest_collect_file(path, parent):
    """Create a MypyFileItem for every file mypy should run on."""
    if path.ext in {'.py', '.pyi'} and any([
            parent.config.option.mypy,
            parent.config.option.mypy_ignore_missing_imports,
    ]):
        # Do not create MypyFile instance for a .py file if a
        # .pyi file with the same name already exists;
        # pytest will complain about duplicate modules otherwise
        if path.ext == '.pyi' or not path.new(ext='.pyi').isfile():
            return MypyFile.from_parent(parent=parent, fspath=path)
    return None


class MypyFile(pytest.File):

    """A File that Mypy will run on."""

    @classmethod
    def from_parent(cls, *args, **kwargs):
        """Override from_parent for compatibility."""
        # pytest.File.from_parent did not exist before pytest 5.4.
        return getattr(super(), 'from_parent', cls)(*args, **kwargs)

    def collect(self):
        """Create a MypyFileItem for the File."""
        yield MypyFileItem.from_parent(parent=self, name=nodeid_name)


@pytest.hookimpl(hookwrapper=True, trylast=True)
def pytest_collection_modifyitems(session, config, items):
    """
    Add a MypyStatusItem if any MypyFileItems were collected.

    Since mypy might check files that were not collected,
    pytest could pass even though mypy failed!
    To prevent that, add an explicit check for the mypy exit status.

    This should execute as late as possible to avoid missing any
    MypyFileItems injected by other pytest_collection_modifyitems
    implementations.
    """
    yield
    if any(isinstance(item, MypyFileItem) for item in items):
        items.append(
            MypyStatusItem.from_parent(parent=session, name=nodeid_name),
        )


class MypyItem(pytest.Item):

    """A Mypy-related test Item."""

    MARKER = 'mypy'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_marker(self.MARKER)

    @classmethod
    def from_parent(cls, *args, **kwargs):
        """Override from_parent for compatibility."""
        # pytest.Item.from_parent did not exist before pytest 5.4.
        return getattr(super(), 'from_parent', cls)(*args, **kwargs)

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
        results = _mypy_results(self.session)
        abspath = os.path.abspath(str(self.fspath))
        errors = results['abspath_errors'].get(abspath)
        if errors:
            raise MypyError(file_error_formatter(self, results, errors))

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
        results = _mypy_results(self.session)
        if results['status']:
            raise MypyError(
                'mypy exited with status {status}.'.format(
                    status=results['status'],
                ),
            )


def _mypy_results(session):
    """Get the cached mypy results for the session, or generate them."""
    return _cached_json_results(
        results_path=(
            session.config._mypy_results_path
            if _is_master(session.config) else
            _get_xdist_workerinput(session.config)['_mypy_results_path']
        ),
        results_factory=functools.partial(
            _mypy_results_factory,
            abspaths=[
                os.path.abspath(str(item.fspath))
                for item in session.items
                if isinstance(item, MypyFileItem)
            ],
        )
    )


def _cached_json_results(results_path, results_factory=None):
    """
    Read results from results_path if it exists;
    otherwise, produce them with results_factory,
    and write them to results_path.
    """
    with FileLock(results_path + '.lock'):
        try:
            with open(results_path, mode='r') as results_f:
                results = json.load(results_f)
        except FileNotFoundError:
            if not results_factory:
                raise
            results = results_factory()
            with open(results_path, mode='w') as results_f:
                json.dump(results, results_f)
    return results


def _mypy_results_factory(abspaths):
    """Run mypy on abspaths and return the results as a JSON-able dict."""

    stdout, stderr, status = mypy.api.run(mypy_argv + abspaths)

    abspath_errors, unmatched_lines = {}, []
    for line in stdout.split('\n'):
        if not line:
            continue
        path, _, error = line.partition(':')
        abspath = os.path.abspath(path)
        if abspath in abspaths:
            abspath_errors[abspath] = abspath_errors.get(abspath, []) + [error]
        else:
            unmatched_lines.append(line)

    return {
        'stdout': stdout,
        'stderr': stderr,
        'status': status,
        'abspath_errors': abspath_errors,
        'unmatched_stdout': '\n'.join(unmatched_lines),
    }


class MypyError(Exception):
    """
    An error caught by mypy, e.g a type checker violation
    or a syntax error.
    """


def pytest_terminal_summary(terminalreporter):
    """Report stderr and unrecognized lines from stdout."""
    config = _pytest_terminal_summary_config
    try:
        results = _cached_json_results(config._mypy_results_path)
    except FileNotFoundError:
        # No MypyItems executed.
        return
    if results['unmatched_stdout'] or results['stderr']:
        terminalreporter.section('mypy')
        if results['unmatched_stdout']:
            color = {'red': True} if results['status'] else {'green': True}
            terminalreporter.write_line(results['unmatched_stdout'], **color)
        if results['stderr']:
            terminalreporter.write_line(results['stderr'], yellow=True)
    os.remove(config._mypy_results_path)
