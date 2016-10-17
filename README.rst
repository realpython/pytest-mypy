pytest-mypy
===================================

.. image:: https://travis-ci.org/dbader/pytest-mypy.svg?branch=master
    :target: https://travis-ci.org/dbader/pytest-mypy
    :alt: See Build Status on Travis CI

Mypy static type checker plugin for Pytest

----

Features
--------

* Runs the mypy static type checker on your source files as part of your Pytest test runs.
* Does for `mypy`_ what the `pytest-flake8`_ plugin does for `flake8`_.
* This is a work in progress – pull requests appreciated.


Installation
------------

You can install "pytest-mypy" via `pip`_ from `PyPI`_:

.. code-block:: bash

    $ pip install pytest-mypy

Usage
-----

You can enable pytest-mypy with the ``--mypy`` flag:

.. code-block:: bash

    $ py.test --mypy test_*.py

Mypy supports `reading configuration settings <http://mypy.readthedocs.io/en/latest/config_file.html>`_ from a ``mypy.ini`` file.
This is currently the only way to configure mypy through pytest-mypy.
In the future pytest-mypy may offer a passthrough for command line
options.

Contributing
------------
Contributions are very welcome. Tests can be run with `tox`_, please ensure
the coverage at least stays the same before you submit a pull request.

Development Environment Setup
-----------------------------
Here's how to install pytest-mypy in development mode so you can test your
changes locally:

.. code-block:: bash

    $ pyvenv venv
    $ source venv/bin/activate
    $ python setup.py develop
    $ venv/bin/py.test --mypy example_test.py

How to publish a new version to PyPI
------------------------------------

.. code-block:: bash

    $ pip install twine wheel
    $ python setup.py sdist bdist_wheel
    $ twine upload dist/*

License
-------

Distributed under the terms of the `MIT`_ license, "pytest-mypy" is free and open source software

Issues
------

If you encounter any problems, please `file an issue`_ along with a detailed description.

Meta
----

Daniel Bader – `@dbader_org`_ – https://dbader.org – mail@dbader.org

https://github.com/dbader/pytest-mypy


.. _`MIT`: http://opensource.org/licenses/MIT
.. _`file an issue`: https://github.com/dbader/pytest-mypy/issues
.. _`tox`: https://tox.readthedocs.io/en/latest/
.. _`pip`: https://pypi.python.org/pypi/pip/
.. _`PyPI`: https://pypi.python.org/pypi
.. _`mypy`: http://mypy-lang.org/
.. _`pytest-flake8`: https://pypi.python.org/pypi/pytest-flake8
.. _`flake8`: https://pypi.python.org/pypi/flake8
.. _`@dbader_org`: https://twitter.com/dbader_org
