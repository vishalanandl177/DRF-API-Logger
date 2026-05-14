Scaling
=======

Architecture for high-traffic Django REST Framework deployments.

How the Logger Works
--------------------

The middleware captures request/response data synchronously but processes it
asynchronously:

1. Middleware captures data during the request/response cycle
2. Data is placed in a thread-safe ``Queue`` (non-blocking)
3. A background daemon thread bulk-inserts from the queue into the database
4. On shutdown (SIGINT/SIGTERM), remaining queue items are flushed

This architecture means:

- API response times are unaffected by logging
- Database writes are batched for efficiency
- No data is lost on graceful shutdown

Multi-Process Deployments (Gunicorn/uWSGI)
------------------------------------------

Each worker process runs its own logger thread. This is by design — each thread
manages its own queue and database connection, avoiding cross-process locking.

.. code-block:: bash

   # Gunicorn: each worker gets its own logger thread
   gunicorn myapp.wsgi:application --workers 4

With 4 workers and ``DRF_LOGGER_QUEUE_MAX_SIZE = 100``, you'll see up to 4
worker-local queues that wake for bulk inserts around 100 rows each. A
dedicated log database handles this without contention on your application
database.

Prometheus-style metrics are also process-local. Scrape each worker/process
separately or use OpenTelemetry/APM export when you need aggregated
service-level telemetry.

Horizontal Scaling
------------------

When running multiple application servers behind a load balancer:

1. **Use a shared log database** — all servers write to the same logs DB
2. **Enable request tracing** — correlate requests across servers

.. code-block:: python

   DRF_API_LOGGER_DEFAULT_DATABASE = 'logs_db'
   DRF_API_LOGGER_ENABLE_TRACING = True
   DRF_API_LOGGER_TRACING_ID_HEADER_NAME = 'X-Request-ID'

3. **Use OpenTelemetry** for distributed tracing across services

.. code-block:: python

   DRF_API_LOGGER_ENABLE_OTEL = True

OpenTelemetry with APM Backends
-------------------------------

Export spans to your APM (Jaeger, Datadog, Grafana Tempo):

.. code-block:: python

   # settings.py
   DRF_API_LOGGER_ENABLE_OTEL = True
   DRF_API_LOGGER_ENABLE_PROFILING = True

Span attributes include:

- ``http.method``, ``http.url``, ``http.status_code``
- ``drf.execution_time_ms``
- ``db.query_count``, ``db.total_time_ms`` (when profiling enabled)
- ``drf.profiling.view_and_serialization_ms``

Storage Estimation
------------------

Approximate storage per log entry:

- Without profiling: ~500 bytes (minimal body) to ~10 KB (large payloads)
- With profiling: adds ~200 bytes of JSON
- Average: ~1–2 KB per entry with body size limits

**Example for 10K requests/minute:**

- 10K * 2 KB = 20 MB/minute = ~28 GB/day
- With 7-day retention: ~200 GB

Use payload size limits and data retention to control storage growth.
