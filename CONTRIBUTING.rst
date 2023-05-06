Contributing
============

Contributions are very welcome. Tests can be run with `tox <https://tox.readthedocs.io/en/latest/>`_.
Please ensure the coverage at least stays the same before you submit a pull request.

Development Environment Setup
-----------------------------

Here's how to install pytest-mypy in development mode so you can test your changes locally:

.. code-block:: bash

    tox --devenv venv
    venv/bin/pytest --mypy test_example.py

How to publish a new version to PyPI
------------------------------------

Push a tag, and the release will be published automatically.
To publish manually:

.. code-block:: bash

    tox -e publish -- upload
