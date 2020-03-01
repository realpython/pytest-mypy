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


def test_pytest_collection_modifyitems(testdir, xdist_args):
    """
    Verify that collected files which are removed in a
    pytest_collection_modifyitems implementation are not
    checked by mypy.

    This would also fail if a MypyStatusItem were injected
    despite there being no MypyFileItems.
    """
    testdir.makepyfile(conftest='''
        def pytest_collection_modifyitems(session, config, items):
            plugin = config.pluginmanager.getplugin('mypy')
            for mypy_item_i in reversed([
                    i
                    for i, item in enumerate(items)
                    if isinstance(item, plugin.MypyFileItem)
            ]):
                items.pop(mypy_item_i)
    ''')
    testdir.makepyfile('''
        def pyfunc(x: int) -> str:
            return x * 2

        def test_pass():
            pass
    ''')
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    test_count = 1
    result.assert_outcomes(passed=test_count)
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
    xdist_args.append('good.py')  # Nothing may come after xdist_args in py34.
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    assert result.ret != 0


def test_mypy_indirect_inject(testdir, xdist_args):
    """
    Verify that uncollected files checked by mypy because of a MypyFileItem
    injected in pytest_collection_modifyitems cause a failure.
    """
    testdir.makepyfile(bad='''
        def pyfunc(x: int) -> str:
            return x * 2
    ''')
    testdir.makepyfile(good='''
        import bad
    ''')
    testdir.makepyfile(conftest='''
        import py
        import pytest

        @pytest.hookimpl(trylast=True)  # Inject as late as possible.
        def pytest_collection_modifyitems(session, config, items):
            plugin = config.pluginmanager.getplugin('mypy')
            items.append(
                plugin.MypyFileItem(py.path.local('good.py'), session),
            )
    ''')
    testdir.mkdir('empty')
    xdist_args.append('empty')  # Nothing may come after xdist_args in py34.
    result = testdir.runpytest_subprocess('--mypy', *xdist_args)
    assert result.ret != 0
