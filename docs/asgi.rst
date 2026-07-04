ASGI-Native Logging
===================

DRF API Logger supports ASGI-native logging for Django deployments that run the
middleware inside Django's async request chain. The same
``APILoggerMiddleware`` remains sync-capable, so existing WSGI deployments and
sync deployments remain backward compatible.

What Is Native
--------------

The middleware declares both sync and async capability. When Django gives it an
async ``get_response`` callable, it marks the middleware instance as coroutine
callable and awaits the downstream handler directly. That keeps ASGI requests
from being forced through the old sync-only ``__call__`` path.

The async path preserves the existing public behavior:

- same middleware path in ``MIDDLEWARE``;
- same database and signal settings;
- same masking, content-type handling, truncation markers, policies, and
  profiling payload shape;
- same ``APILogsModel`` schema and migrations;
- same signal payload keys, with correlation metadata only when correlation is
  enabled.

Request Context Isolation
-------------------------

Request correlation uses Python ``contextvars``. In ASGI deployments this keeps
request IDs, trace IDs, route metadata, and logging context isolated between
concurrent requests. Use ``DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT = True`` when
application logs inside the view need access to the same request context.

.. code-block:: python

   DRF_API_LOGGER_SIGNAL = True
   DRF_API_LOGGER_ENABLE_CORRELATION = True
   DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT = True

Database Queue Behavior
-----------------------

Database logging still enqueues records into the existing background worker.
The request coroutine does not perform bulk database insertion. Queue failures
are isolated so logging problems do not break the API response path.

If database logging is enabled, continue to monitor:

- ``queue_backlog``
- ``dropped_count``
- ``failed_insert_count``
- ``inserted_count``

Testing ASGI Behavior
---------------------

The package tests ASGI behavior in ``tests/test_asgi_middleware.py``. Coverage
includes:

- middleware sync and async capability declarations;
- direct async middleware calls;
- Django ``AsyncClient`` integration;
- signal logging and database enqueue behavior;
- queue failure isolation;
- concurrent request context isolation with ``contextvars``.

Run the ASGI tests with:

.. code-block:: bash

   python -m django test tests.test_asgi_middleware --settings=tests.test_settings --verbosity=2

Run the compatibility suite with:

.. code-block:: bash

   python -m django test tests.test_asgi_middleware tests.test_middleware tests.test_backward_compat tests.test_correlation tests.test_integration --settings=tests.test_settings --verbosity=1

Application Smoke Test
----------------------

Applications can smoke test the ASGI signal path with Django's ``AsyncClient``:

.. code-block:: python

   import json
   from django.test import AsyncClient, override_settings
   from drf_api_logger import API_LOGGER_SIGNAL

   async def test_api_logging_signal_path():
       events = []

       def listener(**kwargs):
           events.append(kwargs)

       API_LOGGER_SIGNAL.listen += listener
       try:
           with override_settings(
               DRF_API_LOGGER_DATABASE=False,
               DRF_API_LOGGER_SIGNAL=True,
           ):
               response = await AsyncClient().post(
                   "/api/test/",
                   data=json.dumps({"password": "example-secret"}),
                   content_type="application/json",
               )

           assert response.status_code == 200
           assert events[0]["body"]["password"] == "***FILTERED***"
       finally:
           API_LOGGER_SIGNAL.listen -= listener

Performance Notes
-----------------

Measure sync and ASGI overhead in the target application before changing
production traffic. Compare these modes at minimum:

- application baseline with DRF API Logger disabled;
- signal-only logging;
- database logging with normal queue settings;
- profiling enabled, if the deployment uses profiling.

Use representative endpoints and report request count, concurrency, status
codes, average latency, p95 latency, p99 latency, and queue backlog. For local
demo validation, use ``J:\projects\drf-demo`` with the local package on
``PYTHONPATH`` so the demo imports the checkout being tested.

The repository includes ``scripts/measure_asgi_overhead.py`` for a local
measurement pass through Django's sync ``Client`` and ASGI ``AsyncClient``. For
the demo project, run it from ``J:\projects\drf-demo`` with the checkout on
``PYTHONPATH``:

.. code-block:: powershell

   $env:PYTHONPATH='J:\projects\DRF-API-Logger'
   & 'J:\projects\drf-demo\venv\Scripts\python.exe' J:\projects\DRF-API-Logger\scripts\measure_asgi_overhead.py --settings config.settings --path /api/echo/ --requests 100 --concurrency 10

Attach the JSON output to the Jira story or release notes when using it as
release-readiness evidence. The script uses a synthetic payload and reports
only timing and status-code aggregates.
