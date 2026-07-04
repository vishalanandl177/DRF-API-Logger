Quickstart Recipes
==================

These recipes are safe starting points for Django REST Framework projects that
need request/response logging, masking, slow API visibility, profiling,
retention, or trace IDs.

Install
-------

.. code-block:: bash

   pip install drf-api-logger

Add the app and middleware:

.. code-block:: python

   INSTALLED_APPS = [
       # ...
       "drf_api_logger",
   ]

   MIDDLEWARE = [
       # ...
       "drf_api_logger.middleware.api_logger_middleware.APILoggerMiddleware",
   ]

Safe Database Logging
---------------------

Use database logging when Django admin visibility and searchable historical API
logs are required.

.. code-block:: python

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

Production-safe defaults:

- Keep masking enabled and add application-specific sensitive keys.
- Set request and response body limits before sending production traffic.
- Skip health checks, metrics, and other noisy endpoints.
- Restrict Django admin access to trusted staff users.
- Schedule retention before the table grows without bound.

Signal-Only Logging
-------------------

Use signal-only logging when an application needs to forward API log events to a
controlled internal sink without writing DRF API Logger database rows.

.. code-block:: python

   DRF_API_LOGGER_SIGNAL = True

.. code-block:: python

   import json
   from drf_api_logger import API_LOGGER_SIGNAL

   def write_api_event(**kwargs):
       safe_event = {
           "api": kwargs["api"],
           "method": kwargs["method"],
           "status_code": kwargs["status_code"],
           "execution_time": kwargs["execution_time"],
           "tracing_id": kwargs.get("tracing_id"),
       }
       print(json.dumps(safe_event))

   API_LOGGER_SIGNAL.listen += write_api_event

Profiling Slow APIs
-------------------

Use a slow API threshold first:

.. code-block:: python

   DRF_API_LOGGER_SLOW_API_ABOVE = 200

Enable sampled profiling when SQL diagnosis is needed:

.. code-block:: python

   DRF_API_LOGGER_ENABLE_PROFILING = True
   DRF_API_LOGGER_PROFILING_SQL_TRACKING = True
   DRF_API_LOGGER_PROFILING_SAMPLE_RATE = 0.1

Request Tracing
---------------

Generate trace IDs automatically:

.. code-block:: python

   DRF_API_LOGGER_ENABLE_TRACING = True

Or accept an upstream request ID:

.. code-block:: python

   DRF_API_LOGGER_ENABLE_TRACING = True
   DRF_API_LOGGER_TRACING_ID_HEADER_NAME = "X-Request-ID"

Request Correlation Without New DB Columns
------------------------------------------

Use correlation when the application needs request IDs, W3C ``traceparent``
trace IDs, route metadata, or metrics labels without adding fields to the
``drf_api_logs`` table.

.. code-block:: python

   DRF_API_LOGGER_SIGNAL = True
   DRF_API_LOGGER_ENABLE_CORRELATION = True
   DRF_API_LOGGER_CORRELATION_REQUEST_ID_HEADERS = ["X-Request-ID", "X-Correlation-ID"]
   DRF_API_LOGGER_CORRELATION_TRACE_ID_HEADERS = ["traceparent", "X-Trace-ID"]
   DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT = True

Correlation data is exposed on the request object, in
``drf_api_logger.logging_context.get_correlation_context()``, and in signal
payload keys named ``correlation`` and ``low_cardinality``. It is not written to
``APILogsModel`` and does not require migrations, model fields, admin columns,
or database indexes.

.. code-block:: python

   from drf_api_logger import API_LOGGER_SIGNAL

   def send_api_metrics(**kwargs):
       labels = kwargs.get("low_cardinality", {})
       metrics.count(
           "drf_api_logger.request",
           tags={
               "route": labels.get("route"),
               "status_class": labels.get("status_class"),
           },
       )

   API_LOGGER_SIGNAL.listen += send_api_metrics

For extra context, return only opaque IDs from an allowlisted callback:

.. code-block:: python

   DRF_API_LOGGER_CORRELATION_CONTEXT_FUNC = "myapp.logging.api_logger_context"

   def api_logger_context(request):
       return {
           "actor_id": getattr(request.user, "pk", None),
           "tenant_id": getattr(request, "tenant_id", None),
           "api_consumer_id": getattr(request, "api_consumer_id", None),
           "client_id": getattr(request, "client_id", None),
       }

Safe Observability Integrations
-------------------------------

Use the observability helpers from signal listeners when your application
already owns Prometheus, OpenTelemetry, or Sentry setup:

.. code-block:: python

   from drf_api_logger import API_LOGGER_SIGNAL
   from drf_api_logger.observability import (
       annotate_opentelemetry_span,
       configure_sentry_scope,
       record_prometheus_metrics,
   )

   def export_observability(**kwargs):
       record_prometheus_metrics(kwargs, API_REQUESTS, API_DURATION)
       annotate_opentelemetry_span(current_span, kwargs)
       configure_sentry_scope(sentry_scope, kwargs)

   API_LOGGER_SIGNAL.listen += export_observability

Prometheus labels are limited to route, URL name, app name, namespace, status
class, and method. Request IDs and trace IDs are available for logs, traces, and
Sentry context, not metrics labels.

Policy Controls
---------------

Use policy controls for endpoint-specific logging decisions:

.. code-block:: python

   DRF_API_LOGGER_POLICY = {
       "rules": [
           {"url_name": "health_check", "log": False},
           {
               "route": "api/payments/",
               "request_body": False,
               "response_body": False,
               "mask_keys": ["card_number", "payment_token"],
           },
       ],
   }

Retention and Pruning
---------------------

Run a dry run before deleting rows:

.. code-block:: bash

   python manage.py prune_api_logs --days 30 --dry-run

Then schedule a batched prune command with the deployment scheduler:

.. code-block:: bash

   python manage.py prune_api_logs --days 30 --batch-size 1000

High-Traffic Baseline
---------------------

.. code-block:: python

   DRF_LOGGER_QUEUE_MAX_SIZE = 100
   DRF_LOGGER_INTERVAL = 5
   DRF_API_LOGGER_SKIP_URL_NAME = ["health-check", "metrics"]
   DRF_API_LOGGER_DEFAULT_DATABASE = "default"

Use a dedicated database alias for log storage when the project needs separate
retention, backup, or capacity planning.
