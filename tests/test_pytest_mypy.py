def test_mypy_success(testdir):
    """Verify that running on a module with no type errors passes."""
    testdir.makepyfile('''
        def myfunc(x: int) -> int:
            return x * 2
    ''')
    result = testdir.runpytest_subprocess()
    result.assert_outcomes()
    result = testdir.runpytest_subprocess('--mypy')
    result.assert_outcomes(passed=1)
    assert result.ret == 0


def test_mypy_error(testdir):
    """Verify that running on a module with type errors fails."""
    testdir.makepyfile('''
        def myfunc(x: int) -> str:
            return x * 2
    ''')
    result = testdir.runpytest_subprocess()
    result.assert_outcomes()
    result = testdir.runpytest_subprocess('--mypy')
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        '2: error: Incompatible return value*',
    ])
    assert result.ret != 0


def test_mypy_ignore_missings_imports(testdir):
    """
    Verify that --mypy-ignore-missing-imports
    causes mypy to ignore missing imports.
    """
    testdir.makepyfile('''
        import pytest_mypy
    ''')
    result = testdir.runpytest_subprocess('--mypy')
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines([
        "1: error: Cannot find *module named 'pytest_mypy'",
    ])
    assert result.ret != 0
    result = testdir.runpytest_subprocess('--mypy-ignore-missing-imports')
    result.assert_outcomes(passed=1)
    assert result.ret == 0


def test_mypy_marker(testdir):
    """Verify that -m mypy only runs the mypy tests."""
    testdir.makepyfile('''
        def test_fails():
            assert False
    ''')
    result = testdir.runpytest_subprocess('--mypy')
    result.assert_outcomes(failed=1, passed=1)
    assert result.ret != 0
    result = testdir.runpytest_subprocess('--mypy', '-m', 'mypy')
    result.assert_outcomes(passed=1)
    assert result.ret == 0


def test_non_mypy_error(testdir):
    """Verify that non-MypyError exceptions are passed through the plugin."""
    message = 'This is not a MypyError.'
    testdir.makepyfile('''
        import pytest_mypy

        def _patched_runtest(*args, **kwargs):
            raise Exception('{message}')

        pytest_mypy.MypyItem.runtest = _patched_runtest
    '''.format(message=message))
    result = testdir.runpytest_subprocess()
    result.assert_outcomes()
    result = testdir.runpytest_subprocess('--mypy')
    result.assert_outcomes(failed=1)
    result.stdout.fnmatch_lines(['*' + message])
    assert result.ret != 0


def test_mypy_stderr(testdir):
    """Verify that stderr from mypy is printed."""
    stderr = 'This is stderr from mypy.'
    testdir.makepyfile(conftest='''
        import mypy.api

        def _patched_run(*args, **kwargs):
            return '', '{stderr}', 1

        mypy.api.run = _patched_run
    '''.format(stderr=stderr))
    result = testdir.runpytest_subprocess('--mypy')
    result.stdout.fnmatch_lines([stderr])


def test_mypy_unmatched_stdout(testdir):
    """Verify that unexpected output on stdout from mypy is printed."""
    stdout = 'This is unexpected output on stdout from mypy.'
    testdir.makepyfile(conftest='''
        import mypy.api

        def _patched_run(*args, **kwargs):
            return '{stdout}', '', 1

        mypy.api.run = _patched_run
    '''.format(stdout=stdout))
    result = testdir.runpytest_subprocess('--mypy')
    result.stdout.fnmatch_lines([stdout])


def test_api_mypy_argv(testdir):
    """Ensure that the plugin can be configured in a conftest.py."""
    testdir.makepyfile(conftest='''
        def pytest_configure(config):
            plugin = config.pluginmanager.getplugin('mypy')
            plugin.mypy_argv.append('--version')
    ''')
    result = testdir.runpytest_subprocess('--mypy')
    assert result.ret == 0
