Operations Guide
================

This guide covers production operation for DRF API Logger database logging,
retention, and health checks.

Supported Runtime Matrix
------------------------

DRF API Logger 1.4.0 supports:

- Python 3.10+
- Django 4.2+
- Django REST Framework 3.16+

The GitHub Actions workflow tests representative Django versions from this
support range before publishing package artifacts.

Production Doctor Command
-------------------------

Run ``drf_api_logger_doctor`` before enabling database logging in production
and after deployment changes that affect logging, storage, retention, masking,
payload limits, or profiling.

.. code-block:: bash

   python manage.py drf_api_logger_doctor

The command is read-only. It validates logging mode, database alias readiness,
DRF API Logger migrations, the log table, queue settings, background worker
status, payload limits, masking configuration, and profiling settings. It does
not create tables, run migrations, prune rows, or inspect stored request or
response payloads.

Use JSON output in CI or deployment checks:

.. code-block:: bash

   python manage.py drf_api_logger_doctor --format json

Fail a deployment on warnings or errors:

.. code-block:: bash

   python manage.py drf_api_logger_doctor --fail-level warning
   python manage.py drf_api_logger_doctor --fail-level error

Use ``--database`` when ``DRF_API_LOGGER_DEFAULT_DATABASE`` points to a
dedicated log database and the deployment check must inspect that alias
explicitly:

.. code-block:: bash

   python manage.py drf_api_logger_doctor --database logs_db --format json

Result levels:

``OK``
   The checked condition is valid for the current configuration.

``WARNING``
   The package can run, but the setting or runtime state deserves operator
   attention before production use.

``ERROR``
   The package is likely misconfigured for the selected logging mode. Fix the
   issue before relying on production database logging.

Deployment Checklist
--------------------

Before enabling database logging in production:

- Run ``python manage.py migrate drf_api_logger`` on the configured log
  database.
- Run ``python manage.py drf_api_logger_doctor --fail-level warning``.
- Keep finite body limits with ``DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE`` and
  ``DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE``.
- Add application-specific secrets to ``DRF_API_LOGGER_EXCLUDE_KEYS``.
- Skip health and metrics endpoints with ``DRF_API_LOGGER_SKIP_URL_NAME`` or
  ``DRF_API_LOGGER_SKIP_NAMESPACE``.
- Schedule ``prune_api_logs`` with a dry run first.
- Monitor ``queue_backlog``, ``dropped_count``, and ``failed_insert_count``.

Database Growth
---------------

The ``drf_api_logs`` table grows with logged request volume. High-traffic
applications should plan retention before enabling database logging in
production.

Recommended production controls:

- Use ``DRF_API_LOGGER_DEFAULT_DATABASE`` to write logs to a dedicated database.
- Add indexes that match your admin and reporting queries.
- Keep payload limits conservative with ``DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE``
  and ``DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE``.
- Prune or archive old rows on a fixed schedule.

Retention Command
-----------------

Use ``prune_api_logs`` for dry-run-first, batched deletion.

Preview rows older than 30 days:

.. code-block:: bash

   python manage.py prune_api_logs --days 30 --dry-run

Delete rows older than 30 days:

.. code-block:: bash

   python manage.py prune_api_logs --days 30 --batch-size 1000

Preview or delete rows before a fixed date:

.. code-block:: bash

   python manage.py prune_api_logs --before 2026-06-01 --dry-run
   python manage.py prune_api_logs --before 2026-06-01

Use ``--database`` when your log table is stored outside Django's default
database alias:

.. code-block:: bash

   python manage.py prune_api_logs --days 90 --database logs_db --dry-run
   python manage.py prune_api_logs --days 90 --database logs_db --batch-size 1000

Scheduling Retention
--------------------

Schedule pruning through your normal operations tooling, such as cron,
systemd timers, Kubernetes CronJobs, Celery beat, or a managed scheduler.

Example cron entry:

.. code-block:: text

   15 2 * * * /app/.venv/bin/python /app/manage.py prune_api_logs --days 30 --batch-size 1000

Always validate the command manually with ``--dry-run`` before scheduling it in
production.

Queue Health Checks
-------------------

When database logging is enabled, request threads enqueue log records and a
background worker flushes them in batches. Monitor the worker status to detect
database write pressure or dropped log records.

.. code-block:: python

   from drf_api_logger.apps import LOGGER_THREAD

   def drf_logger_status():
       if LOGGER_THREAD is None:
           return {"enabled": False}
       return {"enabled": True, **LOGGER_THREAD.get_status()}

Important fields:

``queue_backlog``
   Number of rows waiting to be inserted. A value that grows continuously means
   the logging database cannot keep up with write volume.

``dropped_count``
   Number of records dropped before queueing, usually because a custom handler
   returned ``None`` or the row could not be constructed.

``failed_insert_count``
   Number of rows that failed during bulk insert attempts.

``inserted_count``
   Number of rows successfully inserted by the current worker.

Request Correlation Operations
------------------------------

``DRF_API_LOGGER_ENABLE_CORRELATION`` is designed for joining DRF API Logger
events with application logs, traces, and metrics without changing database
storage. It does not add model fields, migrations, admin columns, or database
indexes, and queued database log rows keep the existing payload shape.

Recommended operating pattern:

- Send ``low_cardinality`` signal metadata to metrics labels, such as route,
  URL name, and status class.
- Keep high-cardinality ``request_id`` and ``trace_id`` values in logs or trace
  systems, not metrics label sets.
- Use ``DRF_API_LOGGER_ENABLE_LOGGING_CONTEXT`` when application log records
  inside the view should include the same request correlation metadata.
- Return only opaque IDs from ``DRF_API_LOGGER_CORRELATION_CONTEXT_FUNC``.

Observability Integration Operations
------------------------------------

DRF API Logger observability helpers are adapters for signal payloads. The
application remains responsible for exporter setup, scrape endpoints, collector
configuration, Sentry initialization, and access control.

Recommended operating pattern:

- Expose Prometheus metrics from the application using its existing metrics
  endpoint.
- Use only low-cardinality labels from ``low_cardinality`` plus HTTP method.
- Add trace or request IDs to logs and spans only when the observability policy
  permits high-cardinality attributes.
- Keep request and response payloads out of metrics, traces, and Sentry context.
- Skip health checks and metrics endpoints with ``DRF_API_LOGGER_SKIP_URL_NAME``
  or ``DRF_API_LOGGER_SKIP_NAMESPACE``.

First-Party Metrics Operations
------------------------------

The optional first-party metrics recorder is disabled by default. Enable it when
the application wants DRF API Logger to report its own overhead and background
pipeline health:

.. code-block:: python

   DRF_API_LOGGER_METRICS_ENABLED = True
   DRF_API_LOGGER_METRICS_GROUPS = ["logger", "pipeline"]

Prefer logger and pipeline metrics first. These show request-path overhead,
payload capture and masking duration, queue backlog, queue utilization, dropped
logs, processed logs, worker state, worker starts, flush duration, batch size,
storage write duration, and storage write failures.

Enable API metrics only when another Django or OpenTelemetry instrumenter is
not already recording HTTP request count and duration:

.. code-block:: python

   DRF_API_LOGGER_API_METRICS_ENABLED = True

If the optional Prometheus endpoint is enabled, mount it under an internal
prefix and protect it at the network or authentication layer:

.. code-block:: python

   DRF_API_LOGGER_METRICS_PROMETHEUS_ENDPOINT_ENABLED = True

The endpoint can reveal route names, latency distributions, error rates, queue
health, and security signal counts. Do not expose it publicly.

API metrics also expose active requests, request body size from
``Content-Length``, non-streaming response body size, slow-request counts,
exception counts, and HTTP 429 throttle counts. Keep them off when another
instrumenter already owns HTTP server metrics.

``DRF_LOGGER_QUEUE_MAX_SIZE`` remains a bulk insert batch threshold, not a hard
queue capacity. Alert on backlog that grows continuously rather than treating
the batch threshold as a maximum queue size.

ASGI Operations
---------------

ASGI deployments use the same ``APILoggerMiddleware`` configuration as sync
deployments. The middleware is async-capable and awaits Django's async response
chain directly when Django runs in ASGI mode.

Recommended operating pattern:

- Keep database logging on the background queue; request coroutines should not
  perform bulk database insertion.
- Monitor ``queue_backlog``, ``dropped_count``, and ``failed_insert_count`` in
  ASGI deployments the same way as sync deployments.
- Enable request correlation with ``contextvars`` when application logs need
  per-request context inside async views.
- Validate with Django ``AsyncClient`` or the package's
  ``tests/test_asgi_middleware.py`` before rollout.
- Compare baseline, signal-only, database, and profiling modes for average,
  p95, and p99 latency in the target application.

Policy Control Operations
-------------------------

Use ``DRF_API_LOGGER_POLICY`` to keep noisy, sensitive, or internal endpoints
out of database logs or signal exports. Keep policy matching deterministic and
bounded because policy evaluation runs on the request path.

Recommended operating pattern:

- Use ``log: False`` for health checks, metrics endpoints, and endpoints that
  should never produce API logger rows or signal exports.
- Use ``headers: False``, ``request_body: False``, and ``response_body: False``
  for sensitive routes that still need timing and status metadata.
- Use ``mask_keys`` for endpoint-specific identifiers that are not globally
  sensitive in the rest of the application.
- Use ``signal: False`` when signal listeners export externally and a request
  should remain local to database logging.

Database Indexes
----------------

The model indexes ``method`` and ``status_code``. For larger installations,
consider adding indexes for your query patterns, for example:

.. code-block:: sql

   CREATE INDEX idx_api_logs_added_on ON drf_api_logs(added_on);
   CREATE INDEX idx_api_logs_api_method ON drf_api_logs(api, method);

Validate index choices against your actual database, table size, and query
plans.
