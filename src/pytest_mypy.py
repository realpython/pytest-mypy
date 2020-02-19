"""Mypy static type checker plugin for Pytest"""

import json
import os
from tempfile import NamedTemporaryFile

from filelock import FileLock  # type: ignore
import mypy.api
import pytest  # type: ignore


mypy_argv = []
nodeid_name = 'mypy'


def pytest_addoption(parser):
    """Add options for enabling and running mypy."""
    group = parser.getgroup('mypy')
    group.addoption(
        '--mypy', action='store_true',
        help='run mypy on .py files')
    group.addoption(
        '--mypy-ignore-missing-imports', action='store_true',
        help="suppresses error messages about imports that cannot be resolved")


def _is_master(config):
    """
    True if the code running the given pytest.config object is running in
    an xdist master node or not running xdist at all.
    """
    return not hasattr(config, 'slaveinput')


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
        # the slaves so that they know where to read parsed results from.
        if config.pluginmanager.getplugin('xdist'):
            class _MypyXdistPlugin:
                def pytest_configure_node(self, node):  # xdist hook
                    """Pass config._mypy_results_path to workers."""
                    node.slaveinput['_mypy_results_path'] = \
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
    """Create a MypyItem for every file mypy should run on."""
    if path.ext == '.py' and any([
            parent.config.option.mypy,
            parent.config.option.mypy_ignore_missing_imports,
    ]):
        item = MypyItem(path, parent)
        if nodeid_name:
            item = MypyItem(
                path,
                parent,
                nodeid='::'.join([item.nodeid, nodeid_name]),
            )
        return item
    return None


class MypyItem(pytest.Item, pytest.File):

    """A File that Mypy Runs On."""

    MARKER = 'mypy'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.add_marker(self.MARKER)

    def runtest(self):
        """Raise an exception if mypy found errors for this item."""
        results = _cached_json_results(
            results_path=(
                self.config._mypy_results_path
                if _is_master(self.config) else
                self.config.slaveinput['_mypy_results_path']
            ),
            results_factory=lambda:
                _mypy_results_factory(
                    abspaths=[
                        os.path.abspath(str(item.fspath))
                        for item in self.session.items
                        if isinstance(item, MypyItem)
                    ],
                )
        )
        abspath = os.path.abspath(str(self.fspath))
        errors = results['abspath_errors'].get(abspath)
        if errors:
            raise MypyError('\n'.join(errors))

    def reportinfo(self):
        """Produce a heading for the test report."""
        return (
            self.fspath,
            None,
            self.config.invocation_dir.bestrelpath(self.fspath),
        )

    def repr_failure(self, excinfo):
        """
        Unwrap mypy errors so we get a clean error message without the
        full exception repr.
        """
        if excinfo.errisinstance(MypyError):
            return excinfo.value.args[0]
        return super().repr_failure(excinfo)


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
