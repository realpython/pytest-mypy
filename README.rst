pytest-mypy
===================================

Mypy static type checker plugin for pytest

.. image:: https://img.shields.io/pypi/v/pytest-mypy.svg
   :target: https://pypi.org/project/pytest-mypy/
   :alt: See Latest Release on PyPI

Features
--------

* Runs the mypy static type checker on your source files as part of your pytest test runs.
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
Alternatively, the plugin can be configured in a ``conftest.py`` to invoke mypy with extra options:

.. code-block:: python

    def pytest_configure(config):
        plugin = config.pluginmanager.getplugin('mypy')
        plugin.mypy_argv.append('--check-untyped-defs')

You can restrict your test run to only perform mypy checks and not any other tests by using the `-m` option:

.. code-block:: bash

    py.test --mypy -m mypy test_*.py

License
-------

Distributed under the terms of the `MIT`_ license, "pytest-mypy" is free and open source software

Issues
------

If you encounter any problems, please `file an issue`_ along with a detailed description.

Meta
----

Daniel Bader – `@dbader_org`_ – https://dbader.org – mail@dbader.org

https://github.com/realpython/pytest-mypy


.. _`MIT`: http://opensource.org/licenses/MIT
.. _`file an issue`: https://github.com/realpython/pytest-mypy/issues
.. _`pip`: https://pypi.python.org/pypi/pip/
.. _`PyPI`: https://pypi.python.org/pypi
.. _`mypy`: http://mypy-lang.org/
.. _`pytest-flake8`: https://pypi.python.org/pypi/pytest-flake8
.. _`flake8`: https://pypi.python.org/pypi/flake8
.. _`@dbader_org`: https://twitter.com/dbader_org
