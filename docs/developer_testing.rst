Developer Testing Guide
=======================

Use this guide when contributing to DRF API Logger.

Setup
-----

.. code-block:: bash

   git clone https://github.com/vishalanandl177/DRF-API-Logger.git
   cd DRF-API-Logger
   python -m venv .venv

On Windows:

.. code-block:: powershell

   .venv\Scripts\activate
   python -m pip install -r requirements-dev.txt

On macOS or Linux:

.. code-block:: bash

   source .venv/bin/activate
   python -m pip install -r requirements-dev.txt

Required Checks
---------------

Run the fast smoke suite:

.. code-block:: bash

   python test_runner_simple.py

Run the full Django suite:

.. code-block:: bash

   python -m django test tests --settings=tests.test_settings --verbosity=1

Run coverage:

.. code-block:: bash

   coverage run --source=drf_api_logger -m django test tests --settings=tests.test_settings --verbosity=1
   coverage report

Run the dependency matrix:

.. code-block:: bash

   tox

Build and validate package metadata:

.. code-block:: bash

   python -m build --sdist --wheel
   python -m twine check dist/*

Test Matrix
-----------

The CI workflow tests representative supported combinations:

- Python 3.10, Django 4.2, DRF 3.16
- Python 3.11, Django 4.2, DRF 3.16
- Python 3.12, Django 5.2, DRF 3.16
- Python 3.13, Django 6.0, DRF 3.17

This matrix is representative coverage, not the complete Django 4.2+ support
list.

Coverage Expectations
---------------------

Add or update tests for every behavior change. Cover the touched surface:

- Middleware request and response behavior.
- Sensitive data masking in bodies, responses, headers, and URL query
  parameters.
- Signal listener behavior and exception isolation.
- Observability helper behavior for Prometheus labels, OpenTelemetry span
  attributes, Sentry context, optional dependency safety, and high-cardinality
  label prevention.
- Background queue flushing, stats, shutdown, and database alias handling.
- Admin display, filters, CSV export, and profiling diagnosis.
- Management commands such as ``prune_api_logs``.
- Backward compatibility for defaults and payloads.

Operational Test Surfaces
-------------------------

Retention command:

.. code-block:: bash

   python manage.py prune_api_logs --days 30 --dry-run
   python manage.py prune_api_logs --days 30 --batch-size 1000

Queue health:

.. code-block:: python

   from drf_api_logger.apps import LOGGER_THREAD

   status = LOGGER_THREAD.get_status() if LOGGER_THREAD else {"enabled": False}

Review Gates
------------

Before a pull request is ready:

- Confirm tests pass locally.
- Confirm package metadata builds and passes ``twine check``.
- Confirm README and ``docs/`` are updated together for behavior, settings,
  support policy, security posture, or operational guidance changes.
- Confirm no generated artifacts are staged.
