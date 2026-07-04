Tutorials and Community Snippets
================================

These examples are safe to adapt for blog posts, Stack Overflow answers,
internal runbooks, and video tutorials. They avoid direct identities and real
secrets.

Log All DRF API Requests Safely
-------------------------------

Use this setup when the team wants DRF request/response logs in Django admin:

.. code-block:: python

   INSTALLED_APPS = [
       # ...
       "drf_api_logger",
   ]

   MIDDLEWARE = [
       # ...
       "drf_api_logger.middleware.api_logger_middleware.APILoggerMiddleware",
   ]

   DRF_API_LOGGER_DATABASE = True
   DRF_API_LOGGER_EXCLUDE_KEYS = [
       "password",
       "token",
       "access",
       "refresh",
       "secret",
       "api_key",
       "client_secret",
   ]
   DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = 32768
   DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = 65536

.. code-block:: bash

   python manage.py migrate

Find Slow APIs
--------------

Start by flagging slow API calls:

.. code-block:: python

   DRF_API_LOGGER_SLOW_API_ABOVE = 200

For a deeper diagnosis, enable sampled profiling:

.. code-block:: python

   DRF_API_LOGGER_ENABLE_PROFILING = True
   DRF_API_LOGGER_PROFILING_SQL_TRACKING = True
   DRF_API_LOGGER_PROFILING_SAMPLE_RATE = 0.1

Review SQL time and query count in the admin detail page. High query count with
high SQL time usually points to an N+1 pattern. Few queries with high SQL time
usually points to indexes, query plans, or database pressure.

Mask Secrets
------------

Default masking covers common credential-bearing keys and headers. Add
application-specific keys:

.. code-block:: python

   DRF_API_LOGGER_EXCLUDE_KEYS = [
       "password",
       "token",
       "access",
       "refresh",
       "secret",
       "api_key",
       "client_secret",
       "account_identifier",
       "billing_reference",
   ]

Example masked payload:

.. code-block:: python

   {
       "username": "example_user",
       "api_key": "***FILTERED***",
       "billing_reference": "***FILTERED***",
   }

Schedule Retention
------------------

Run a dry run first:

.. code-block:: bash

   python manage.py prune_api_logs --days 30 --dry-run

Then schedule batched deletion through cron, Kubernetes CronJob, Celery beat, or
the deployment platform scheduler:

.. code-block:: bash

   python manage.py prune_api_logs --days 30 --batch-size 1000

Debug with Trace IDs
--------------------

Generate trace IDs automatically:

.. code-block:: python

   DRF_API_LOGGER_ENABLE_TRACING = True

Or use an upstream request ID:

.. code-block:: python

   DRF_API_LOGGER_ENABLE_TRACING = True
   DRF_API_LOGGER_TRACING_ID_HEADER_NAME = "X-Request-ID"

Log the same ID in application code:

.. code-block:: python

   import logging

   logger = logging.getLogger(__name__)

   def example_view(request):
       tracing_id = getattr(request, "tracing_id", "missing")
       logger.info("example_view started", extra={"tracing_id": tracing_id})

Correlate Logs Without Persisting IDs
-------------------------------------

Use request correlation when application logs, gateway IDs, and metrics need to
line up, but the log table should keep its existing schema.

.. code-block:: python

   DRF_API_LOGGER_SIGNAL = True
   DRF_API_LOGGER_ENABLE_CORRELATION = True
   DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT = True
   DRF_API_LOGGER_CORRELATION_REQUEST_ID_HEADERS = ["X-Request-ID", "X-Correlation-ID"]
   DRF_API_LOGGER_CORRELATION_TRACE_ID_HEADERS = ["traceparent", "X-Trace-ID"]

.. code-block:: python

   from drf_api_logger import API_LOGGER_SIGNAL

   def send_metrics(**kwargs):
       labels = kwargs.get("low_cardinality", {})
       metrics.count(
           "drf_api_logger.request",
           tags={
               "route": labels.get("route"),
               "status_class": labels.get("status_class"),
           },
       )

   API_LOGGER_SIGNAL.listen += send_metrics

Correlation adds ``correlation`` and ``low_cardinality`` to signal payloads and
sets request attributes such as ``request.api_logger_request_id``. It does not
add model fields, migrations, admin columns, database indexes, or extra queued
database payload fields.

Community Snippets
------------------

Stack Overflow answer shape:

.. code-block:: text

   Install drf-api-logger, add drf_api_logger to INSTALLED_APPS, add APILoggerMiddleware to MIDDLEWARE, set DRF_API_LOGGER_DATABASE = True, configure DRF_API_LOGGER_EXCLUDE_KEYS and body limits, then run python manage.py migrate.

Blog outline:

.. code-block:: text

   1. Why custom DRF logging middleware leaks secrets and adds request latency.
   2. Install drf-api-logger.
   3. Enable database logging with masking and body limits.
   4. Use admin filters to find failed or slow APIs.
   5. Enable sampled profiling for SQL diagnosis.
   6. Schedule prune_api_logs for retention.

Video script outline:

.. code-block:: text

   Show a DRF endpoint, enable drf-api-logger, make a request with example payload data, inspect the masked log row in Django admin, enable slow API threshold, then finish with retention and tracing settings.
