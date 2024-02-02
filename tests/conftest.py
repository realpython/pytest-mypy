import mypy.version

pytest_plugins = "pytester"


def pytest_report_header():
    return f"mypy: {mypy.version.__version__}"
