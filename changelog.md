# Changelog

## [0.6.1](https://github.com/dbader/pytest-mypy/milestone/11)
* Fix a PytestDeprecationWarning emitted by pytest>=5.4

## [0.6.0](https://github.com/dbader/pytest-mypy/milestone/10)
* Inject a test that checks the mypy exit status

## [0.5.0](https://github.com/dbader/pytest-mypy/milestone/9)
* Remove `MypyItem.mypy_path`
* Add support for pytest-xdist
* Add a configurable name to MypyItem node IDs

## [0.4.2](https://github.com/dbader/pytest-mypy/milestone/8)
* Make success message green instead of red
* Remove Python 3.8 beta/dev references
* Stop blacklisting early 0.5x and 0.7x mypy releases

## [0.4.1](https://github.com/dbader/pytest-mypy/milestone/7)
* Stop overlapping `python_version`s in `install_requires`

## [0.4.0](https://github.com/dbader/pytest-mypy/milestone/6)
* Run mypy once per session instead of once per file
* Stop passing --incremental (which mypy now defaults to)
* Support configuring the plugin in a conftest.py
* Add support for Python 3.8

## [0.3.3](https://github.com/dbader/pytest-mypy/milestone/3)
* Register `mypy` marker.
* Add a PEP 518 `[build-system]`
* Add dependency pins for Python 3.4
* Add support for Python 3.7

## [0.3.2](https://github.com/dbader/pytest-mypy/milestone/2)
* Add `mypy` marker to run mypy checks only

## [0.3.1](https://github.com/dbader/pytest-mypy/milestone/1)
* Only depend on `mypy.api`
* Add `--mypy-ignore-missing-imports`
* Invoke `mypy` with `--incremental`

## [0.3.0](https://github.com/dbader/pytest-mypy/milestone/5)
* Change `mypy` dependency to pull in `mypy` instead of `mypy-lang`
