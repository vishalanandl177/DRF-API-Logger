Compliance Readiness
====================

DRF API Logger can be used in regulated environments, but compliance depends on
deployment configuration, database controls, retention policies, and the data
your APIs send through the logger. This guide covers the package-level controls
that help reduce production risk.

Data Minimization
-----------------

Use the request and response body size settings to avoid storing unnecessary
payloads:

.. code-block:: python

   DRF_API_LOGGER_MAX_REQUEST_BODY_SIZE = 32768
   DRF_API_LOGGER_MAX_RESPONSE_BODY_SIZE = 65536

Set either value to ``0`` when the body should never be stored. Oversized bodies
are replaced with a truncation marker that records the observed byte size and
configured limit.

Sensitive Data Masking
----------------------

The logger masks sensitive keys recursively in request bodies, response bodies,
headers, and URL query parameters. Default coverage includes passwords, tokens,
authorization headers, cookies, API keys, session IDs, CSRF tokens, and common
secret field names.

Add organization-specific fields with:

.. code-block:: python

   DRF_API_LOGGER_EXCLUDE_KEYS = [
       'ssn',
       'credit_card',
       'patient_id',
       'customer_secret',
   ]

Matching is case-insensitive and treats hyphens and underscores equivalently, so
``X-API-Key`` and ``x_api_key`` are both masked.

Custom Redaction
----------------

For domain-specific policies, use a custom handler to transform or drop log
records before they enter the background queue:

.. code-block:: python

   DRF_API_LOGGER_CUSTOM_HANDLER = 'myapp.logging.redact_api_log'

   def redact_api_log(data):
       data['headers'].pop('AUTHORIZATION', None)
       if data['api'].endswith('/health/'):
           return None
       return data

Returning ``None`` intentionally drops that log entry.

Request Correlation Controls
----------------------------

Request correlation is disabled by default. When
``DRF_API_LOGGER_ENABLE_CORRELATION`` is enabled, request IDs, trace IDs, route
metadata, and allowlisted opaque context are exposed through request attributes,
logging context, and signal payloads. The package does not persist correlation
metadata to ``APILogsModel`` and does not add migrations, model fields, admin
columns, database indexes, or synthetic database payload fields.

For privacy-sensitive deployments:

- Treat ``request_id`` and ``trace_id`` as high-cardinality operational IDs.
- Send only route, URL name, namespace, app name, and status class to metrics
  labels through ``low_cardinality``.
- Use opaque values for ``actor_id``, ``tenant_id``, ``api_consumer_id``, and
  ``client_id``.
- Do not return names, emails, tokens, session IDs, or regulated identifiers
  from ``DRF_API_LOGGER_CORRELATION_CONTEXT_FUNC``.

Observability Export Controls
-----------------------------

When exporting DRF API Logger signal data to observability systems:

- Send only ``low_cardinality`` values to metrics labels.
- Do not export headers, request bodies, response bodies, authorization values,
  cookies, tokens, emails, usernames, or direct customer identifiers.
- Use request IDs and trace IDs only as operational correlation IDs.
- Use Sentry context for debugging metadata, not payload storage.
- Keep external exporter credentials outside DRF API Logger settings.

Metrics and Security Signal Controls
------------------------------------

First-party metrics and security signals are disabled by default. When enabled,
they are designed for low-cardinality operational aggregates, not payload or
identity storage.

For compliance-sensitive deployments:

- Keep request IDs, trace IDs, user IDs, tenant IDs, IP addresses, object IDs,
  raw URLs, query strings, headers, cookies, tokens, SQL queries, request
  bodies, response bodies, and exception messages out of metric labels.
- Use route patterns, URL names, method, and status class for metrics labels.
- Keep the optional Prometheus endpoint internal-only and protected.
- Keep security signals in detect-only mode.
- Keep response-body inspection disabled unless there is a documented
  operational need.
- Keep request-body inspection bounded with a finite
  ``DRF_API_LOGGER_SECURITY_BODY_INSPECTION["max_body_bytes"]`` value.

Policy Controls
---------------

Policy controls support data minimization by endpoint. Use them to skip
logging, strip headers or bodies, add endpoint-specific mask keys, and prevent
signal exports for sensitive routes.

For compliance-sensitive deployments:

- Configure ``log: False`` for endpoints that should not produce logs.
- Configure ``headers: False`` and body stripping for regulated payloads.
- Use ``mask_keys`` for tenant-specific or domain-specific identifiers.
- Keep policy reasons generic and free of personal data.
- Treat policy callables as request-path code and keep them deterministic.

Storage Controls
----------------

For production and compliance-sensitive systems:

- Use ``DRF_API_LOGGER_DEFAULT_DATABASE`` to write logs to a dedicated database.
- Enable encryption at rest and backups on the database platform.
- Limit database and Django admin access with least-privilege roles.
- Define retention and deletion jobs for old log rows. The package includes
  ``python manage.py prune_api_logs --days 30 --dry-run`` and
  ``python manage.py prune_api_logs --days 30 --batch-size 1000`` for
  dry-run-first, batched deletion.
- Avoid storing request or response bodies for endpoints that handle regulated
  data unless there is a documented business need.

Profiling Controls
------------------

Profiling is disabled by default. If enabled in high-traffic production systems,
sample it:

.. code-block:: python

   DRF_API_LOGGER_ENABLE_PROFILING = True
   DRF_API_LOGGER_PROFILING_SQL_TRACKING = True
   DRF_API_LOGGER_PROFILING_SAMPLE_RATE = 0.1

This keeps request-level performance visibility while reducing overhead and
stored diagnostic volume.

Operational Checks
------------------

Monitor the logger worker backlog through ``LOGGER_THREAD.get_status()`` and
alert when ``queue_backlog`` grows continuously. A rising backlog usually means
the logging database cannot keep up with write volume.

Compliance Mapping
------------------

The package provides controls that support common privacy and security programs:

.. list-table::
   :header-rows: 1
   :widths: 30 70

   * - Requirement Area
     - Package Support
   * - Data minimization
     - Body limits, truncation markers, custom handler drops
   * - Sensitive data protection
     - Recursive masking for bodies, headers, and URL query parameters
   * - Access control
     - Dedicated log database support through Django database aliases
   * - Retention
     - Timestamped log model suitable for scheduled retention jobs
   * - Auditability
     - Request metadata, status code, execution time, tracing IDs, and profiling data

These controls do not by themselves certify GDPR, HIPAA, PCI DSS, SOC 2, or ISO
27001 compliance. Treat them as implementation controls inside your broader
governance, risk, and compliance process.
