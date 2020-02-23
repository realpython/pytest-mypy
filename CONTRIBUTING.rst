Contributing
============

Contributions are very welcome. Tests can be run with `tox <https://tox.readthedocs.io/en/latest/>`_.
Please ensure the coverage at least stays the same before you submit a pull request.

.. image:: https://travis-ci.org/dbader/pytest-mypy.svg?branch=master
    :target: https://travis-ci.org/dbader/pytest-mypy
    :alt: See Build Status on Travis CI

Development Environment Setup
-----------------------------

Here's how to install pytest-mypy in development mode so you can test your changes locally:

.. code-block:: bash

    tox --devenv venv
    venv/bin/pytest --mypy test_example.py

How to publish a new version to PyPI
------------------------------------

Push a tag, and Travis CI will publish it automatically.
To publish manually:

.. code-block:: bash

    python -m venv venv
    venv/bin/pip install pep517 twine
    venv/bin/python -m pep517.build .
    venv/bin/twine upload dist/*
