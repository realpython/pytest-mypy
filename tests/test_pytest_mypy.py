import signal
import sys
import textwrap

import mypy.version
from packaging.version import Version
import pytest

import pytest_mypy


MYPY_VERSION = Version(mypy.version.__version__)
PYTHON_VERSION = Version(
    ".".join(
        str(token)
        for token in [
            sys.version_info.major,
            sys.version_info.minor,
            sys.version_info.micro,
        ]
    )
)


@pytest.fixture(
    params=[
        True,  # xdist enabled, active
        False,  # xdist enabled, inactive
        None,  # xdist disabled
    ],
)
def xdist_args(request):
    if request.param is None:
        return ["-p", "no:xdist"]
    return ["-n", "auto"] if request.param else []


@pytest.mark.parametrize("pyfile_count", [1, 2])
def test_mypy_success(testdir, pyfile_count, xdist_args):
    """Verify that running on a module with no type errors passes."""
    testdir.makepyfile(
        **{
            "pyfile_{0}".format(
                pyfile_i,
            ): """
                def pyfunc(x: int) -> int:
                    return x * 2
            """
            for pyfile_i in range(pyfile_count)
        },
    )
    result = testdir.runpytest_subprocess(*xdist_args)
    result.assert_outcomes()
    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    mypy_file_checks = pyfile_count
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(passed=mypy_checks)
    assert result.ret == pytest.ExitCode.OK


def test_mypy_pyi(testdir, xdist_args):
    """
    Verify that a .py file will be skipped if
    a .pyi file exists with the same filename.
    """
    # The incorrect signature below should be ignored
    # as the .pyi file takes priority
    testdir.makepyfile(
        pyfile="""
            def pyfunc(x: int) -> str:
                return x * 2
        """,
    )

    testdir.makefile(
        ".pyi",
        pyfile="""
            def pyfunc(x: int) -> int: ...
        """,
    )

    result = testdir.runpytest_subprocess(*xdist_args)
    result.assert_outcomes()
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(passed=mypy_checks)
    assert result.ret == pytest.ExitCode.OK


def test_mypy_error(testdir, xdist_args):
    """Verify that running on a module with type errors fails."""
    testdir.makepyfile(
        """
            def pyfunc(x: int) -> str:
                return x * 2
        """,
    )
    result = testdir.runpytest_subprocess(*xdist_args)
    result.assert_outcomes()
    assert "_mypy_results_path" not in result.stderr.str()
    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(failed=mypy_checks)
    result.stdout.fnmatch_lines(["2: error: Incompatible return value*"])
    assert "_mypy_results_path" not in result.stderr.str()
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_mypy_annotation_unchecked(testdir, xdist_args, tmp_path, monkeypatch):
    """Verify that annotation-unchecked warnings do not manifest as an error."""
    testdir.makepyfile(
        """
            def pyfunc(x):
                y: int = 2
                return x * y
        """,
    )
    result = testdir.runpytest_subprocess(*xdist_args)
    result.assert_outcomes()
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    outcomes = {"passed": mypy_checks}
    result.assert_outcomes(**outcomes)
    result.stdout.fnmatch_lines(["*MypyWarning*"])
    assert result.ret == pytest.ExitCode.OK


def test_mypy_ignore_missings_imports(testdir, xdist_args):
    """
    Verify that --mypy-ignore-missing-imports
    causes mypy to ignore missing imports.
    """
    module_name = "is_always_missing"
    testdir.makepyfile(
        """
            try:
                import {module_name}
            except ImportError:
                pass
        """.format(
            module_name=module_name,
        ),
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(failed=mypy_checks)
    result.stdout.fnmatch_lines(
        [
            "2: error: Cannot find *module named *{module_name}*".format(
                module_name=module_name,
            ),
        ],
    )
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result = testdir.runpytest_subprocess("--mypy-ignore-missing-imports", *xdist_args)
    result.assert_outcomes(passed=mypy_checks)
    assert result.ret == pytest.ExitCode.OK


def test_mypy_config_file(testdir, xdist_args):
    """Verify that --mypy-config-file works."""
    testdir.makepyfile(
        """
            def pyfunc(x):
                return x * 2
        """,
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(passed=mypy_checks)
    assert result.ret == pytest.ExitCode.OK
    mypy_config_file = testdir.makeini(
        """
            [mypy]
            disallow_untyped_defs = True
        """,
    )
    result = testdir.runpytest_subprocess(
        "--mypy-config-file",
        mypy_config_file,
        *xdist_args,
    )
    result.assert_outcomes(failed=mypy_checks)


def test_mypy_marker(testdir, xdist_args):
    """Verify that -m mypy only runs the mypy tests."""
    testdir.makepyfile(
        """
            def test_fails():
                assert False
        """,
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    test_count = 1
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(failed=test_count, passed=mypy_checks)
    assert result.ret == pytest.ExitCode.TESTS_FAILED
    result = testdir.runpytest_subprocess("--mypy", "-m", "mypy", *xdist_args)
    result.assert_outcomes(passed=mypy_checks)
    assert result.ret == pytest.ExitCode.OK


def test_non_mypy_error(testdir, xdist_args):
    """Verify that non-MypyError exceptions are passed through the plugin."""
    message = "This is not a MypyError."
    testdir.makepyfile(
        conftest="""
            def pytest_configure(config):
                plugin = config.pluginmanager.getplugin('mypy')

                class PatchedMypyFileItem(plugin.MypyFileItem):
                    def runtest(self):
                        raise Exception('{message}')

                plugin.MypyFileItem = PatchedMypyFileItem
        """.format(
            message=message,
        ),
    )
    result = testdir.runpytest_subprocess(*xdist_args)
    result.assert_outcomes()
    assert result.ret == pytest.ExitCode.NO_TESTS_COLLECTED
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    mypy_file_checks = 1  # conftest.py
    mypy_status_check = 1
    result.assert_outcomes(
        failed=mypy_file_checks,  # patched to raise an Exception
        passed=mypy_status_check,  # conftest.py has no type errors.
    )
    result.stdout.fnmatch_lines(["*" + message])
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_mypy_stderr(testdir, xdist_args):
    """Verify that stderr from mypy is printed."""
    stderr = "This is stderr from mypy."
    testdir.makepyfile(
        conftest="""
            import mypy.api

            def _patched_run(*args, **kwargs):
                return '', '{stderr}', 1

            mypy.api.run = _patched_run
        """.format(
            stderr=stderr,
        ),
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    result.stdout.fnmatch_lines([stderr])


def test_mypy_unmatched_stdout(testdir, xdist_args):
    """Verify that unexpected output on stdout from mypy is printed."""
    stdout = "This is unexpected output on stdout from mypy."
    testdir.makepyfile(
        conftest="""
            import mypy.api

            def _patched_run(*args, **kwargs):
                return '{stdout}', '', 1

            mypy.api.run = _patched_run
        """.format(
            stdout=stdout,
        ),
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    result.stdout.fnmatch_lines([stdout])


def test_api_mypy_argv(testdir, xdist_args):
    """Ensure that the plugin can be configured in a conftest.py."""
    testdir.makepyfile(
        conftest="""
            def pytest_configure(config):
                plugin = config.pluginmanager.getplugin('mypy')
                plugin.mypy_argv.append('--version')
        """,
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    assert result.ret == pytest.ExitCode.OK


def test_api_nodeid_name(testdir, xdist_args):
    """Ensure that the plugin can be configured in a conftest.py."""
    nodeid_name = "UnmistakableNodeIDName"
    testdir.makepyfile(
        conftest="""
            def pytest_configure(config):
                plugin = config.pluginmanager.getplugin('mypy')
                plugin.nodeid_name = '{}'
        """.format(
            nodeid_name,
        ),
    )
    result = testdir.runpytest_subprocess("--mypy", "--verbose", *xdist_args)
    result.stdout.fnmatch_lines(["*conftest.py::" + nodeid_name + "*"])
    assert result.ret == pytest.ExitCode.OK


@pytest.mark.xfail(
    Version("0.971") <= MYPY_VERSION,
    raises=AssertionError,
    reason="https://github.com/python/mypy/issues/13701",
)
@pytest.mark.parametrize(
    "module_name",
    [
        "__init__",
        "good",
    ],
)
def test_mypy_indirect(testdir, xdist_args, module_name):
    """Verify that uncollected files checked by mypy cause a failure."""
    testdir.makepyfile(
        bad="""
            def pyfunc(x: int) -> str:
                return x * 2
        """,
    )
    pyfile = testdir.makepyfile(
        **{
            module_name: """
                import bad
            """,
        },
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args, str(pyfile))
    mypy_file_checks = 1
    mypy_status_check = 1
    result.assert_outcomes(passed=mypy_file_checks, failed=mypy_status_check)
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_api_error_formatter(testdir, xdist_args):
    """Ensure that the plugin can be configured in a conftest.py."""
    testdir.makepyfile(
        bad="""
            def pyfunc(x: int) -> str:
                return x * 2
        """,
    )
    testdir.makepyfile(
        conftest="""
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
        """,
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    result.stdout.fnmatch_lines(["*/bad.py:2: error: Incompatible return value*"])
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_pyproject_toml(testdir, xdist_args):
    """Ensure that the plugin allows configuration with pyproject.toml."""
    testdir.makefile(
        ".toml",
        pyproject="""
            [tool.mypy]
            disallow_untyped_defs = true
        """,
    )
    testdir.makepyfile(
        conftest="""
            def pyfunc(x):
                return x * 2
        """,
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    result.stdout.fnmatch_lines(["1: error: Function is missing a type annotation*"])
    assert result.ret == pytest.ExitCode.TESTS_FAILED


def test_setup_cfg(testdir, xdist_args):
    """Ensure that the plugin allows configuration with setup.cfg."""
    testdir.makefile(
        ".cfg",
        setup="""
            [mypy]
            disallow_untyped_defs = True
        """,
    )
    testdir.makepyfile(
        conftest="""
            def pyfunc(x):
                return x * 2
        """,
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    result.stdout.fnmatch_lines(["1: error: Function is missing a type annotation*"])
    assert result.ret == pytest.ExitCode.TESTS_FAILED


@pytest.mark.parametrize("module_name", ["__init__", "test_demo"])
def test_looponfail(testdir, module_name):
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
    pyfile = testdir.makepyfile(**{module_name: fail_source})
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
        expect_timeout=60.0,
    )

    def _expect_session():
        child.expect("==== test session starts ====")

    def _expect_failure():
        _expect_session()
        child.expect("==== FAILURES ====")
        child.expect(pyfile.basename + " ____")
        child.expect("2: error: Incompatible return value")
        child.expect("==== mypy ====")
        child.expect("Found 1 error in 1 file (checked 1 source file)")
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
            child.expect("==== mypy ====")
            child.expect("Success: no issues found in 1 source file")
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


def test_mypy_results_from_mypy_with_opts():
    """MypyResults.from_mypy respects passed options."""
    mypy_results = pytest_mypy.MypyResults.from_mypy([], opts=["--version"])
    assert mypy_results.status == 0
    assert mypy_results.abspath_errors == {}
    assert str(MYPY_VERSION) in mypy_results.stdout


def test_mypy_no_output(testdir, xdist_args):
    """No terminal summary is shown if there is no output from mypy."""
    testdir.makepyfile(
        # Mypy prints a success message to stderr by default:
        # "Success: no issues found in 1 source file"
        # Clear stderr and unmatched_stdout to simulate mypy having no output:
        conftest="""
            import pytest

            @pytest.hookimpl(trylast=True)
            def pytest_configure(config):
                pytest_mypy = config.pluginmanager.getplugin("mypy")
                mypy_config_stash = config.stash[pytest_mypy.stash_key["config"]]
                with open(mypy_config_stash.mypy_results_path, mode="w") as results_f:
                    pytest_mypy.MypyResults(
                        opts=[],
                        stdout="",
                        stderr="",
                        status=0,
                        abspath_errors={},
                        unmatched_stdout="",
                    ).dump(results_f)
        """,
    )
    result = testdir.runpytest_subprocess("--mypy", *xdist_args)
    mypy_file_checks = 1
    mypy_status_check = 1
    mypy_checks = mypy_file_checks + mypy_status_check
    result.assert_outcomes(passed=mypy_checks)
    assert result.ret == pytest.ExitCode.OK
    assert f"= {pytest_mypy.terminal_summary_title} =" not in str(result.stdout)


def test_py_typed(testdir):
    """Mypy recognizes that pytest_mypy is typed."""
    name = "typed"
    testdir.makepyfile(**{name: "import pytest_mypy"})
    result = testdir.run("mypy", f"{name}.py")
    assert result.ret == 0
