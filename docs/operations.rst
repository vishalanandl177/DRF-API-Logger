Operations Guide
================

This guide covers production operation for DRF API Logger database logging,
retention, and health checks.

Supported Runtime Matrix
------------------------

DRF API Logger 1.2.3 supports:

- Python 3.10+
- Django 4.2+
- Django REST Framework 3.16+

The GitHub Actions workflow tests representative Django versions from this
support range before publishing package artifacts.

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

Database Indexes
----------------

The model indexes ``method`` and ``status_code``. For larger installations,
consider adding indexes for your query patterns, for example:

.. code-block:: sql

   CREATE INDEX idx_api_logs_added_on ON drf_api_logs(added_on);
   CREATE INDEX idx_api_logs_api_method ON drf_api_logs(api, method);

Validate index choices against your actual database, table size, and query
plans.
