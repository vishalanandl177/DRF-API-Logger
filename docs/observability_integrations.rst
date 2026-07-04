Safe Observability Integrations
===============================

DRF API Logger can feed metrics, traces, and error context through signal
listeners. The package does not start exporters, expose a metrics endpoint, or
send data to external systems by itself. Applications own their Prometheus,
OpenTelemetry, Sentry, Loki, Elasticsearch, or hosted monitoring setup.

Prerequisites
-------------

Enable signal logging and request correlation:

.. code-block:: python

   DRF_API_LOGGER_SIGNAL = True
   DRF_API_LOGGER_ENABLE_CORRELATION = True
   DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT = True
   DRF_API_LOGGER_CORRELATION_REQUEST_ID_HEADERS = ["X-Request-ID", "X-Correlation-ID"]
   DRF_API_LOGGER_CORRELATION_TRACE_ID_HEADERS = ["traceparent", "X-Trace-ID"]

The signal payload can include:

- ``correlation``: high-cardinality request IDs, trace IDs, and allowlisted
  opaque context.
- ``low_cardinality``: route, URL name, app name, namespace, and status class
  values safe for metrics labels.

Prometheus Metrics
------------------

Install and configure Prometheus in the application, then use DRF API Logger's
helper from a signal listener:

.. code-block:: python

   from prometheus_client import Counter, Histogram

   from drf_api_logger import API_LOGGER_SIGNAL
   from drf_api_logger.observability import record_prometheus_metrics

   API_REQUESTS = Counter(
       "drf_api_logger_requests_total",
       "DRF API Logger observed requests",
       ["route", "url_name", "app_name", "namespace", "status_class", "method"],
   )
   API_DURATION = Histogram(
       "drf_api_logger_request_duration_seconds",
       "DRF API Logger observed request duration",
       ["route", "url_name", "app_name", "namespace", "status_class", "method"],
       buckets=[0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10],
   )

   def export_api_metrics(**kwargs):
       record_prometheus_metrics(kwargs, API_REQUESTS, API_DURATION)

   API_LOGGER_SIGNAL.listen += export_api_metrics

The helper only uses low-cardinality labels. It does not place ``request_id``,
``trace_id``, ``actor_id``, ``tenant_id``, ``api_consumer_id``, or ``client_id``
in Prometheus labels. Treat those IDs as debugging context, not metrics labels.

OpenTelemetry Span Attributes
-----------------------------

When the application already has OpenTelemetry configured, annotate the current
span from a signal listener:

.. code-block:: python

   from opentelemetry import trace

   from drf_api_logger import API_LOGGER_SIGNAL
   from drf_api_logger.observability import annotate_opentelemetry_span

   def annotate_current_span(**kwargs):
       span = trace.get_current_span()
       annotate_opentelemetry_span(span, kwargs)

   API_LOGGER_SIGNAL.listen += annotate_current_span

By default, high-cardinality request and trace IDs are not added as span
attributes. If the application's trace policy allows those values, pass
``include_high_cardinality=True`` explicitly:

.. code-block:: python

   annotate_opentelemetry_span(
       span,
       kwargs,
       include_high_cardinality=True,
   )

Sentry Error Context
--------------------

For Sentry SDK 2.x, enrich the current scope with safe tags and context:

.. code-block:: python

   import sentry_sdk

   from drf_api_logger import API_LOGGER_SIGNAL
   from drf_api_logger.observability import configure_sentry_scope

   def enrich_sentry_scope(**kwargs):
       scope = sentry_sdk.Scope.get_current_scope()
       configure_sentry_scope(scope, kwargs)

   API_LOGGER_SIGNAL.listen += enrich_sentry_scope

Sentry tags receive only low-cardinality values. Sentry context can include
request IDs, trace IDs, and opaque IDs for debugging, but it never includes
request headers, request body, or response body.

Safety Rules
------------

- Keep high-cardinality values out of metrics labels.
- Keep payloads, headers, cookies, authorization values, and direct identities
  out of observability exports.
- Keep exporter ownership in the application, not in DRF API Logger.
- Prefer route patterns and URL names over raw URLs.
- Use ``DRF_API_LOGGER_SKIP_URL_NAME`` or ``DRF_API_LOGGER_SKIP_NAMESPACE`` to
  avoid recording health checks, metrics endpoints, admin paths, and noisy
  internal endpoints.
