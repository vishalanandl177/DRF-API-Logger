Performance Tuning
==================

DRF API Logger keeps database writes out of request threads, but high-traffic
deployments benefit from tuning these parameters.

Queue and Batching
------------------

The logger collects entries in a thread-safe queue and bulk-inserts them into the database.
Two settings control this behavior:

.. code-block:: python

   DRF_LOGGER_QUEUE_MAX_SIZE = 100   # Wake worker when backlog reaches this size
   DRF_LOGGER_INTERVAL = 5           # Flush every N seconds regardless of queue size

**Low traffic (<100 req/min):** defaults (50 / 10s) are fine.

**Medium traffic (100–1000 req/min):** increase queue size to 100–200, reduce interval to 5s.

**High traffic (>1000 req/min):** set queue to 500+, interval to 3s. Use a dedicated database.

``DRF_LOGGER_QUEUE_MAX_SIZE`` is a batch threshold, not a bounded request queue.
Request threads enqueue and return; the background worker performs database
flushes in batches.

Dedicated Log Database
----------------------

Isolate log writes from your application database to prevent contention:

.. code-block:: python

   DRF_API_LOGGER_DEFAULT_DATABASE = 'logs_db'

   DATABASES = {
       'default': { ... },   # Application data
       'logs_db': {           # Log storage
           'ENGINE': 'django.db.backends.postgresql',
           'NAME': 'api_logs',
       },
   }

Payload Size Limits
-------------------

Large request/response bodies consume storage and slow down bulk inserts:

.. code-block:: python

   DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = 32768    # Default: 32 KB
   DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = 65536   # Default: 64 KB

Requests/responses exceeding these limits are logged with a truncation marker.
Use ``-1`` only when you intentionally want unlimited body capture.

Database Indexes
----------------

Add indexes to improve admin search and filtering performance:

.. code-block:: sql

   CREATE INDEX idx_api_logs_added_on ON drf_api_logs(added_on);
   CREATE INDEX idx_api_logs_api_method ON drf_api_logs(api, method);
   CREATE INDEX idx_api_logs_status ON drf_api_logs(status_code, added_on);
   CREATE INDEX idx_api_logs_sql_count ON drf_api_logs(sql_query_count)
       WHERE sql_query_count IS NOT NULL;

Data Retention
--------------

Periodically archive or delete old logs to keep the table performant:

.. code-block:: python

   from drf_api_logger.models import APILogsModel
   from django.utils import timezone
   from datetime import timedelta

   cutoff = timezone.now() - timedelta(days=30)
   APILogsModel.objects.filter(added_on__lt=cutoff).delete()

Profiling Overhead
------------------

SQL profiling uses ``connection.force_debug_cursor`` which adds minimal overhead
(~0.1ms per request). The overhead comes from Django recording query strings and
execution times. Memory is cleaned up via ``reset_queries()`` after each request.

To disable SQL tracking while keeping timing profiling:

.. code-block:: python

   DRF_API_LOGGER_ENABLE_PROFILING = True
   DRF_API_LOGGER_PROFILING_SQL_TRACKING = False

To profile only a sample of logged requests:

.. code-block:: python

   DRF_API_LOGGER_ENABLE_PROFILING = True
   DRF_API_LOGGER_PROFILING_SAMPLE_RATE = 0.1

Skip Noisy Endpoints
--------------------

Exclude health checks, metrics, and internal endpoints from logging:

.. code-block:: python

   DRF_API_LOGGER_SKIP_URL_NAME = ['health-check', 'readiness', 'metrics']
   DRF_API_LOGGER_SKIP_NAMESPACE = ['monitoring', 'internal']
