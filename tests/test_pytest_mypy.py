def test_mypy_success(testdir):
    testdir.makepyfile('''
        def myfunc(x: int) -> int:
            return x * 2

        def test_myfunc():
            assert myfunc(12)
    ''')

    result = testdir.runpytest_subprocess('--mypy', '-v')

    assert result.ret == 0


def test_mypy_error(testdir):
    testdir.makepyfile('''
        def myfunc(x: int) -> str:
            return x * 2

        def test_myfunc():
            assert myfunc(12)
    ''')

    result = testdir.runpytest_subprocess('--mypy', '-v')

    result.stdout.fnmatch_lines([
        'test_mypy_error.py:2: error: Incompatible return value*',
    ])
    assert result.ret != 0
