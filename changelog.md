# Changelog

## 0.5.0
* Remove MypyItem.mypy_path
* Add support for pytest-xdist
* Add a configurable name to MypyItem node IDs

See [the milestone](https://github.com/dbader/pytest-mypy/milestone/9) for details.

## 0.4.2
* Make success message green instead of red.
* Remove Python 3.8 beta/dev references.
* Stop blacklisting early 0.5x and 0.7x mypy releases.

See [the milestone](https://github.com/dbader/pytest-mypy/milestone/8) for details.

## 0.4.1
* Stop overlapping `python_version`s in `install_requires`.

## 0.4.0
* Run mypy once per session instead of once per file.
* Stop passing --incremental (which mypy now defaults to).
* Support configuring the plugin in a conftest.py.
* Add support for Python 3.8

See [the milestone](https://github.com/dbader/pytest-mypy/milestone/6) for details.

## 0.3.3
* Register `mypy` marker.
* Add a PEP-518 [build-system]
* Add dependency pins for Python 3.4.
* Add support for Python 3.7

See [the milestone](https://github.com/dbader/pytest-mypy/milestone/3) for details.

## 0.3.2
* Add `mypy` marker to run mypy checks only

## 0.3.1
* See [the milestone](https://github.com/dbader/pytest-mypy/milestone/1?closed=1) for a description of the changes in this release.

## 0.3.0
* Change `mypy` dependency to pull in `mypy` instead of `mypy-lang`
