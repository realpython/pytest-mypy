import signal
import textwrap

import pytest


@pytest.fixture(
    params=[
        True,  # xdist enabled, active
        False,  # xdist enabled, inactive
        None,  # xdist disabled
    ],
)
def xdist_args(request):
    if request.param is None:
        return ['-p', 'no:xdist']
    return ['-n', 'auto'] if request.param else []


@pytest.mark.parametrize('pyfile_count', [1, 2])
def test_mypy_success(testdir, pyfile_count, xdist_args):
    """Verify that running on a module with no type errors passes."""
    testdir.makepyfile(
        **{
            'pyfile_' + str(pyfile_i): '''
                def pyfunc(x: int) -> int:
                    return x * 2
            '''
            for pyfile_i in range(pyfile_count)
        }
    )
    result = testdir.runpytest_subprocess(*xdist_args)
    result.assert_outcomes()
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    mypy_file_checks = pyfile_count
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(passed=mypy_checks)
    assert result.ret == 0


def test_mypy_pyi(testdir, xdist_args):
    """
    Verify that a .py file will be skipped if
    a .pyi file exists with the same filename.
    """
    # The incorrect signature below should be ignored
    # as the .pyi file takes priority
    testdir.makefile(
        '.py', pyfile='''
            def pyfunc(x: int) -> str:
                return x * 2
        '''
    )

    testdir.makefile(
        '.pyi', pyfile='''
            def pyfunc(x: int) -> int: ...
        '''
    )

    result = testdir.runpytest_subprocess(*xdist_args)
    result.assert_outcomes()
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(passed=mypy_checks)
    assert result.ret == 0


def test_mypy_error(testdir, xdist_args):
    """Verify that running on a module with type errors fails."""
    testdir.makepyfile('''
        def pyfunc(x: int) -> str:
            return x * 2
    ''')
    result = testdir.runpytest_subprocess(*xdist_args)
    result.assert_outcomes()
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(failed=mypy_checks)
    result.stdout.fnmatch_lines([
        '2: error: Incompatible return value*',
    ])
    assert result.ret != 0


def test_mypy_ignore_missings_imports(testdir, xdist_args):
    """
    Verify that --mypy-ignore-missing-imports
    causes mypy to ignore missing imports.
    """
    module_name = 'is_always_missing'
    testdir.makepyfile('''
        try:
            import {module_name}
        except ImportError:
            pass
    '''.format(module_name=module_name))
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(failed=mypy_checks)
    result.stdout.fnmatch_lines([
        "2: error: Cannot find *module named '{module_name}'".format(
            module_name=module_name,
        ),
    ])
    assert result.ret != 0
    result = testdir.runpytest_subprocess(
        '--mypy-ignore-missing-imports',
        *xdist_args
    )
    result.assert_outcomes(passed=mypy_checks)
    assert result.ret == 0


def test_mypy_marker(testdir, xdist_args):
    """Verify that -m mypy only runs the mypy tests."""
    testdir.makepyfile('''
        def test_fails():
            assert False
    ''')
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    test_count = 1
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(failed=test_count, passed=mypy_checks)
    assert result.ret != 0
    result = testdir.runpytest_subprocess('--mypy', '-m', 'mypy', *xdist_args)
    result.assert_outcomes(passed=mypy_checks)
    assert result.ret == 0


def test_non_mypy_error(testdir, xdist_args):
    """Verify that non-MypyError exceptions are passed through the plugin."""
    message = 'This is not a MypyError.'
    testdir.makepyfile(conftest='''
        def pytest_configure(config):
            plugin = config.pluginmanager.getplugin('mypy')

            class PatchedMypyFileItem(plugin.MypyFileItem):
                def runtest(self):
                    raise Exception('{message}')

            plugin.MypyFileItem = PatchedMypyFileItem
    '''.format(message=message))
    result = testdir.runpytest_subprocess(*xdist_args)
    result.assert_outcomes()
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    mypy_file_checks = 1  # conftest.py
    mypy_status_check = 1
    result.assert_outcomes(
        failed=mypy_file_checks,  # patched to raise an Exception
        passed=mypy_status_check,  # conftest.py has no type errors.
    )
    result.stdout.fnmatch_lines(['*' + message])
    assert result.ret != 0


def test_mypy_stderr(testdir, xdist_args):
    """Verify that stderr from mypy is printed."""
    stderr = 'This is stderr from mypy.'
    testdir.makepyfile(conftest='''
        import mypy.api

        def _patched_run(*args, **kwargs):
            return '', '{stderr}', 1

        mypy.api.run = _patched_run
    '''.format(stderr=stderr))
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    result.stdout.fnmatch_lines([stderr])


def test_mypy_unmatched_stdout(testdir, xdist_args):
    """Verify that unexpected output on stdout from mypy is printed."""
    stdout = 'This is unexpected output on stdout from mypy.'
    testdir.makepyfile(conftest='''
        import mypy.api

        def _patched_run(*args, **kwargs):
            return '{stdout}', '', 1

        mypy.api.run = _patched_run
    '''.format(stdout=stdout))
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    result.stdout.fnmatch_lines([stdout])


def test_api_mypy_argv(testdir, xdist_args):
    """Ensure that the plugin can be configured in a conftest.py."""
    testdir.makepyfile(conftest='''
        def pytest_configure(config):
            plugin = config.pluginmanager.getplugin('mypy')
            plugin.mypy_argv.append('--version')
    ''')
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    assert result.ret == 0


def test_api_nodeid_name(testdir, xdist_args):
    """Ensure that the plugin can be configured in a conftest.py."""
    nodeid_name = 'UnmistakableNodeIDName'
    testdir.makepyfile(conftest='''
        def pytest_configure(config):
            plugin = config.pluginmanager.getplugin('mypy')
            plugin.nodeid_name = '{}'
    '''.format(nodeid_name))
    result = testdir.runpytest_subprocess('--mypy', '--verbose', *xdist_args)
    result.stdout.fnmatch_lines(['*conftest.py::' + nodeid_name + '*'])
    assert result.ret == 0


def test_mypy_indirect(testdir, xdist_args):
    """Verify that uncollected files checked by mypy cause a failure."""
    testdir.makepyfile(bad='''
        def pyfunc(x: int) -> str:
            return x * 2
    ''')
    testdir.makepyfile(good='''
        import bad
    ''')
    result = testdir.runpytest_subprocess('--mypy', *xdist_args, 'good.py')
    assert result.ret != 0


def test_api_error_formatter(testdir, xdist_args):
    """Ensure that the plugin can be configured in a conftest.py."""
    testdir.makepyfile(bad='''
        def pyfunc(x: int) -> str:
            return x * 2
    ''')
    testdir.makepyfile(conftest='''
        def custom_file_error_formatter(item, results, errors):
            return '\\n'.join(
                '{path}:{error}'.format(
                    path=item.fspath,
                    error=error,
                )
                for error in errors
            )

        def pytest_configure(config):
            plugin = config.pluginmanager.getplugin('mypy')
            plugin.file_error_formatter = custom_file_error_formatter
    ''')
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    result.stdout.fnmatch_lines([
        '*/bad.py:2: error: Incompatible return value*',
    ])
    assert result.ret != 0


def test_setup_cfg(testdir, xdist_args):
    """Ensure that the plugin allows configuration with setup.cfg."""
    testdir.makefile('.cfg', setup='''
        [mypy]
        disallow_untyped_defs = True
    ''')
    testdir.makepyfile(conftest='''
        def pyfunc(x):
            return x * 2
    ''')
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    result.stdout.fnmatch_lines([
        '1: error: Function is missing a type annotation',
    ])
    assert result.ret != 0


def test_looponfail(testdir):
    """Ensure that the plugin works with --looponfail."""

    pass_source = textwrap.dedent(
        """\
        def pyfunc(x: int) -> int:
            return x * 2
        """,
    )
    fail_source = textwrap.dedent(
        """\
        def pyfunc(x: int) -> str:
            return x * 2
        """,
    )
    pyfile = testdir.makepyfile(fail_source)
    looponfailroot = testdir.mkdir("looponfailroot")
    looponfailroot_pyfile = looponfailroot.join(pyfile.basename)
    pyfile.move(looponfailroot_pyfile)
    pyfile = looponfailroot_pyfile
    testdir.makeini(
        textwrap.dedent(
            """\
            [pytest]
            looponfailroots = {looponfailroots}
            """.format(
                looponfailroots=looponfailroot,
            ),
        ),
    )

    child = testdir.spawn_pytest(
        "--mypy --looponfail " + str(pyfile),
        expect_timeout=30.0,
    )

    def _expect_session():
        child.expect("==== test session starts ====")

    def _expect_failure():
        _expect_session()
        child.expect("==== FAILURES ====")
        child.expect(pyfile.basename + " ____")
        child.expect("2: error: Incompatible return value")
        # These only show with mypy>=0.730:
        # child.expect("==== mypy ====")
        # child.expect("Found 1 error in 1 file (checked 1 source file)")
        child.expect("2 failed")
        child.expect("#### LOOPONFAILING ####")
        _expect_waiting()

    def _expect_waiting():
        child.expect("#### waiting for changes ####")
        child.expect("Watching")

    def _fix():
        pyfile.write(pass_source)
        _expect_changed()
        _expect_success()

    def _expect_changed():
        child.expect("MODIFIED " + str(pyfile))

    def _expect_success():
        for _ in range(2):
            _expect_session()
            # These only show with mypy>=0.730:
            # child.expect("==== mypy ====")
            # child.expect("Success: no issues found in 1 source file")
            child.expect("2 passed")
        _expect_waiting()

    def _break():
        pyfile.write(fail_source)
        _expect_changed()
        _expect_failure()

    _expect_failure()
    _fix()
    _break()
    _fix()
    child.kill(signal.SIGTERM)
