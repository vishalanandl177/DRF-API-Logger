Metrics
=============

DRF API Logger can expose optional first-party metrics for logger health,
background pipeline behavior, API request timing, and security-signal counts.
The feature is disabled by default and does not add database migrations.

Metrics are designed for Prometheus-style systems while preserving the package
privacy model:

- no request bodies, response bodies, headers, cookies, tokens, raw URLs, query
  strings, request IDs, trace IDs, user IDs, IPs, object IDs, SQL queries, or
  exception messages are used as metric labels;
- route labels come from Django's resolved route pattern or safe resolver
  metadata, not ``request.path``;
- requests that do not resolve to a Django route use fixed
  ``route="unresolved"`` and ``view_name="unresolved"`` labels instead of raw
  404 paths;
- all recorder calls collapse to a no-op when metrics are disabled or the
  exporter is unavailable.

Installation
------------

Prometheus support is optional:

.. code-block:: bash

   pip install "drf-api-logger[prometheus]"

Without the extra, the package still imports and normal API logging continues
to work. If Prometheus metrics are enabled without ``prometheus_client``, Django
system checks report a configuration error.

Logger and Pipeline Metrics
---------------------------

Start with logger and pipeline metrics. These show whether DRF API Logger itself
is adding overhead or falling behind:

.. code-block:: python

   DRF_API_LOGGER_METRICS_ENABLED = True
   DRF_API_LOGGER_METRICS_EXPORTER = "prometheus"
   DRF_API_LOGGER_METRICS_GROUPS = ["logger", "pipeline"]

Useful signals include:

- request-path logger overhead;
- payload capture, masking, serialization, and enqueue duration;
- log events enqueued, processed, skipped, or dropped;
- queue backlog;
- configured queue batch threshold;
- queue utilization ratio;
- worker up/down state;
- worker starts observed in the current process;
- batch flush duration and batch size;
- storage write duration;
- storage write failures.

``DRF_LOGGER_QUEUE_MAX_SIZE`` remains the bulk insert batch threshold. It is not
a hard queue capacity; the queue is intentionally unbounded so request threads
do not block on database pressure. Metrics expose backlog and batch threshold
so operators can alert when backlog grows continuously.

API Metrics
-----------

Enable API-level request metrics only when the application does not already
collect equivalent Django/OpenTelemetry HTTP server metrics:

.. code-block:: python

   DRF_API_LOGGER_METRICS_ENABLED = True
   DRF_API_LOGGER_API_METRICS_ENABLED = True

API metrics can observe requests even when ``DRF_API_LOGGER_DATABASE`` and
``DRF_API_LOGGER_SIGNAL`` are disabled. This mode records safe timing and route
metadata only; it does not build database log payloads or emit
``API_LOGGER_SIGNAL``.

API metrics include:

- request count and duration;
- active in-flight requests;
- request body size from ``Content-Length`` when available;
- non-streaming response body size without force-reading streaming responses;
- slow-request counts using ``DRF_API_LOGGER_SLOW_API_ABOVE``;
- exception counts by safe exception class;
- throttle counts for HTTP 429 responses.

Profiling Metrics
-----------------

Profiling metrics are emitted only when profiling is enabled and profiling data
exists:

.. code-block:: python

   DRF_API_LOGGER_ENABLE_PROFILING = True
   DRF_API_LOGGER_METRICS_ENABLED = True
   DRF_API_LOGGER_METRICS_GROUPS = ["logger", "pipeline", "profiling"]

These metrics expose SQL duration, query count, duplicate query count, likely
N+1 signals, view/serialization duration, and middleware timing. They summarize
the existing profiling payload and never expose SQL text as labels.

What You Can Do With These Metrics
----------------------------------

These metrics are most useful when they answer operational questions that are
hard to answer from individual log rows alone.

Protect API logging reliability
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Use queue, worker, and storage metrics to detect when logging is falling behind
before API log rows are lost or delayed:

.. code-block:: text

   drf_api_logger_queue_depth{queue_name="database"}

.. code-block:: text

   rate(drf_api_logger_log_events_dropped_total[5m])

.. code-block:: text

   rate(drf_api_logger_storage_write_failures_total[5m])

These signals help answer questions such as:

- Is the background worker alive?
- Is the database insert pipeline falling behind traffic?
- Are logs being skipped by policy or dropped by a handler?
- Did a migration or database outage break log persistence?

Measure logger overhead
~~~~~~~~~~~~~~~~~~~~~~~

Track whether logging, masking, serialization, or enqueueing has become a
meaningful part of request latency:

.. code-block:: text

   histogram_quantile(
     0.95,
     sum by (le, route) (
       rate(drf_api_logger_request_overhead_seconds_bucket[5m])
     )
   )

If this increases for a route, compare it with payload capture and masking
duration:

.. code-block:: text

   histogram_quantile(
     0.95,
     sum by (le, location) (
       rate(drf_api_logger_payload_capture_duration_seconds_bucket[5m])
     )
   )

This helps decide whether a large response body, expensive masking, or queue
pressure is responsible.

Find slow or SQL-heavy endpoints
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

API and profiling metrics highlight endpoints that are slow because of view
work, SQL work, or repeated queries:

.. code-block:: text

   histogram_quantile(
     0.95,
     sum by (le, route) (
       rate(drf_api_logger_http_request_duration_seconds_bucket[5m])
     )
   )

Average SQL query count by route:

.. code-block:: text

   sum by (route) (rate(drf_api_logger_request_sql_queries_sum[5m]))
   /
   sum by (route) (rate(drf_api_logger_request_sql_queries_count[5m]))

Likely N+1 query signals:

.. code-block:: text

   rate(drf_api_logger_n_plus_one_suspected_total[15m])

These are useful for prioritizing endpoint tuning and confirming that a fix
actually reduced query count or view duration.

Spot abuse and suspicious activity
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

Security metrics are detect-only. They do not block requests, but they give
operators low-cardinality counters for suspicious patterns:

.. code-block:: text

   sum by (rule_id, route) (
     rate(drf_api_logger_security_rule_matches_total[5m])
   )

Examples:

- authentication abuse: ``DRFSEC-001`` and ``DRFSEC-002``;
- token failure bursts: ``DRFSEC-003``;
- route scans and unresolved 404 noise: ``DRFSEC-008`` with
  ``route="unresolved"``;
- object ID enumeration hints: ``DRFSEC-009``;
- SQLi, XSS, path traversal, or log-injection payload patterns:
  ``DRFSEC-006`` and ``DRFSEC-010``;
- export or high-volume response behavior: ``DRFSEC-013`` and
  ``DRFSEC-014``.

For example, to alert on warning-level security activity:

.. code-block:: text

   sum by (category, severity, route) (
     rate(drf_api_logger_security_alerts_total[5m])
   )

Keep dashboards safe by design
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

All examples above use route patterns, status buckets, rule IDs, categories, and
other bounded values. Avoid raw paths, IDs, IPs, request bodies, response bodies,
SQL text, and exception messages in dashboards and alerts. Use masked log rows,
trace context, or Sentry for per-request investigation.

Safe Labels
-----------

Default labels:

.. code-block:: python

   DRF_API_LOGGER_METRICS_LABELS = [
       "method",
       "route",
       "view_name",
       "status_class",
   ]

Do not configure high-cardinality or sensitive labels. System checks reject
unsafe labels such as ``request_id``, ``trace_id``, ``user_id``, ``client_ip``,
``raw_path``, ``query_string``, ``token``, ``object_id``, ``request_body``, and
``response_body``.

Prometheus Endpoint
-------------------

DRF API Logger can provide an optional endpoint, but it is disabled by default.
Expose it only on an internal path protected by your network, gateway, service
mesh, or authentication layer:

.. code-block:: python

   DRF_API_LOGGER_METRICS_PROMETHEUS_ENDPOINT_ENABLED = True

Add it under an internal prefix:

.. code-block:: python

   from django.urls import include, path

   urlpatterns = [
       path("internal/drf-api-logger/", include("drf_api_logger.metrics.urls")),
   ]

The default included path is ``metrics/``, producing
``/internal/drf-api-logger/metrics/`` in the example above. Do not expose this
endpoint publicly; it can reveal route names, latency distributions, error
rates, worker health, and security signal counts.

System Checks
-------------

Run Django checks after enabling metrics:

.. code-block:: bash

   python manage.py check

Checks validate missing Prometheus dependencies, unsafe labels, endpoint
exposure warnings, and unsafe security body-inspection limits.

Operations Notes
----------------

- Keep API metrics disabled when another HTTP metrics instrumenter already
  records request count and duration.
- Prefer logger and pipeline metrics first; they are specific to DRF API Logger.
- In Gunicorn or uWSGI multi-process deployments, configure Prometheus
  multiprocess support according to ``prometheus_client`` documentation.
- Alert on growing queue backlog, dropped logs, failed writes, and worker down
  state.
- Treat metrics as operational aggregates, not investigation evidence. Use
  masked logs, traces, or Sentry context for per-request debugging.
