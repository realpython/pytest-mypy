"""
TODO:
    [ ] Make mypy options configurable
    [ ] Python 2.7 port?
    [ ] Proper docs
"""
import pytest
import mypy.api


def pytest_addoption(parser):
    group = parser.getgroup('mypy')
    group.addoption(
        '--mypy', action='store_true',
        help='run mypy on .py files')


def pytest_collect_file(path, parent):
    config = parent.config
    if config.option.mypy and path.ext == '.py':
        return MypyItem(path, parent)


class MypyError(Exception):
    """
    An error caught by mypy, e.g a type checker violation
    or a syntax error.
    """
    pass


class MypyItem(pytest.Item, pytest.File):
    def __init__(self, path, parent):
        super().__init__(path, parent)
        self.path = path

    def runtest(self):
        """
        Run mypy on the given file.
        """
        # TODO: This should be hidden behind a debug / verbose flag.
        print('Running mypy on', self.path)

        # Construct a fake command line argv and let mypy do its
        # own options parsing.
        mypy_argv = [
            str(self.path),
            '--incremental',
            # TODO: This is where we'd tack on other mypy options
            #       from the pytest config.
            #       Or maybe we'll just rely on mypy.ini being present?
        ]

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
